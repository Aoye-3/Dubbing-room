from __future__ import annotations

import json
import queue
import threading
from dataclasses import asdict
from typing import Any

from .generation_service import GenerationService
from .indextts2_service import IndexTTS2Service
from .job_store import (
    create_asset,
    create_generation_job,
    create_generation_take,
    get_generation_job,
    list_generation_takes,
    select_generation_take,
    update_generation_job,
    update_generation_take,
)
from .paths import AppPaths
from .schemas import GenerationJobRecord


class GenerationJobQueue:
    def __init__(self, paths: AppPaths, generation_service: GenerationService, indextts2_service: IndexTTS2Service):
        self.paths = paths
        self.generation_service = generation_service
        self.indextts2_service = indextts2_service
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def submit(self, payload: dict[str, Any]) -> GenerationJobRecord:
        backend_id = str(payload.get("backend_id") or "")
        if backend_id not in {"voxcpm2", "indextts2"}:
            raise ValueError(f"unsupported backend_id: {backend_id}")
        params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
        input_text = str(payload.get("input_text") or params.get("input_text") or params.get("text") or "").strip()
        job = create_generation_job(
            self.paths,
            backend_id=backend_id,
            model_id=str(payload.get("model_id") or _default_model_id(backend_id)),
            mode=str(payload.get("mode") or _default_mode(backend_id)),
            input_text=input_text,
            voice_id=payload.get("voice_id") if isinstance(payload.get("voice_id"), str) else None,
            params=params,
        )
        if backend_id == "indextts2":
            create_generation_take(
                self.paths,
                job_id=job.id,
                backend_id=backend_id,
                take_index=1,
                label="Take 1",
                params=params,
            )
        self._queue.put(job.id)
        return job

    def cancel(self, job_id: str) -> GenerationJobRecord:
        job = _require_job(self.paths, job_id)
        if job.status == "queued":
            return update_generation_job(self.paths, job.id, status="cancelled", error_summary="")
        if job.status == "running":
            return update_generation_job(self.paths, job.id, error_summary="cancel requested")
        return job

    def retry(self, job_id: str) -> GenerationJobRecord:
        job = _require_job(self.paths, job_id)
        params = json.loads(job.params_json or "{}")
        return self.submit(
            {
                "backend_id": job.backend_id,
                "model_id": job.model_id,
                "mode": job.mode,
                "input_text": job.input_text,
                "voice_id": job.voice_id,
                "params": params,
            }
        )

    def _run(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                self._execute(job_id)
            finally:
                self._queue.task_done()

    def _execute(self, job_id: str) -> None:
        job = _require_job(self.paths, job_id)
        if job.status != "queued":
            return
        update_generation_job(self.paths, job.id, status="running", error_summary="")
        params = json.loads(job.params_json or "{}")
        try:
            if job.backend_id == "voxcpm2":
                record = self.generation_service.generate_audio(_voxcpm_payload(job, params))
                asset_kind = "generation_output"
            elif job.backend_id == "indextts2":
                record = self.indextts2_service.generate(_indextts2_payload(job, params))
                asset_kind = "take_output"
            else:
                raise ValueError(f"unsupported backend_id: {job.backend_id}")
            if record.status != "succeeded":
                update_generation_job(
                    self.paths,
                    job.id,
                    status="failed",
                    error_summary=record.error_summary,
                    legacy_generation_id=record.id,
                )
                self._mark_take_failed(job, record.error_summary)
                return
            output_asset_id = None
            if record.output_audio_path:
                asset = create_asset(
                    self.paths,
                    kind=asset_kind,
                    path=record.output_audio_path,
                    sample_rate=record.sample_rate,
                )
                output_asset_id = asset.id
            update_generation_job(
                self.paths,
                job.id,
                status="succeeded",
                output_asset_id=output_asset_id,
                legacy_generation_id=record.id,
                error_summary="",
            )
            if job.backend_id == "indextts2":
                self._mark_take_succeeded(job, output_asset_id)
        except Exception as exc:
            error_summary = str(exc).splitlines()[0][:500]
            update_generation_job(self.paths, job.id, status="failed", error_summary=error_summary)
            self._mark_take_failed(job, error_summary)

    def _mark_take_succeeded(self, job: GenerationJobRecord, output_asset_id: str | None) -> None:
        takes = list_generation_takes(self.paths, job.id)
        if not takes:
            return
        take = update_generation_take(self.paths, takes[0].id, status="succeeded", output_asset_id=output_asset_id)
        select_generation_take(self.paths, take.id)

    def _mark_take_failed(self, job: GenerationJobRecord, error_summary: str) -> None:
        takes = list_generation_takes(self.paths, job.id)
        if takes:
            update_generation_take(self.paths, takes[0].id, status="failed", error_summary=error_summary)


def _require_job(paths: AppPaths, job_id: str) -> GenerationJobRecord:
    job = get_generation_job(paths, job_id)
    if job is None:
        raise KeyError(f"generation job not found: {job_id}")
    return job


def _default_model_id(backend_id: str) -> str:
    return "openbmb/VoxCPM2" if backend_id == "voxcpm2" else "IndexTTS2"


def _default_mode(backend_id: str) -> str:
    return "voice_generation" if backend_id == "voxcpm2" else "line_performance"


def _voxcpm_payload(job: GenerationJobRecord, params: dict[str, Any]) -> dict[str, Any]:
    return {
        **params,
        "generation_job_id": job.id,
        "input_text": str(params.get("input_text") or job.input_text),
        "reference": params.get("reference") if isinstance(params.get("reference"), dict) else {"kind": "none"},
    }


def _indextts2_payload(job: GenerationJobRecord, params: dict[str, Any]) -> dict[str, Any]:
    return {
        **params,
        "generation_job_id": job.id,
        "text": str(params.get("text") or params.get("input_text") or job.input_text),
    }


def job_to_dict(job: GenerationJobRecord) -> dict[str, Any]:
    payload = asdict(job)
    payload["params"] = json.loads(job.params_json or "{}")
    return payload
