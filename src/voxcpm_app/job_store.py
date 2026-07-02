from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from uuid import uuid4

import soundfile as sf

from .audio_assets import sha256_file
from .db import initialize_database, utc_now
from .generation_history import create_generation, mark_generation_succeeded
from .paths import AppPaths
from .repositories import AssetRepository, GenerationJobRepository, GenerationTakeRepository
from .schemas import ASSET_KINDS, JOB_STATUSES, AssetRecord, GenerationJobRecord, GenerationTakeRecord


def create_asset(
    paths: AppPaths,
    *,
    kind: str,
    path: str | Path,
    mime_type: str | None = None,
    duration_seconds: float | None = None,
    sample_rate: int | None = None,
) -> AssetRecord:
    if kind not in ASSET_KINDS:
        raise ValueError(f"unsupported asset kind: {kind}")
    absolute_path = Path(path)
    if not absolute_path.is_absolute():
        absolute_path = paths.project_root / absolute_path
    if not absolute_path.exists():
        raise FileNotFoundError(f"asset file does not exist: {absolute_path}")
    if duration_seconds is None or sample_rate is None:
        try:
            info = sf.info(str(absolute_path))
            sample_rate = sample_rate or int(info.samplerate)
            duration_seconds = duration_seconds if duration_seconds is not None else float(info.duration)
        except Exception:
            pass
    record = AssetRecord(
        id=str(uuid4()),
        kind=kind,
        path=paths.project_relative(absolute_path),
        sha256=sha256_file(absolute_path),
        mime_type=mime_type or mimetypes.guess_type(absolute_path.name)[0] or "application/octet-stream",
        duration_seconds=duration_seconds,
        sample_rate=sample_rate,
        created_at=utc_now(),
        deleted_at=None,
    )
    conn = initialize_database(paths)
    try:
        return AssetRepository(conn).insert(record)
    finally:
        conn.close()


def list_assets(paths: AppPaths, *, include_deleted: bool = False) -> list[AssetRecord]:
    conn = initialize_database(paths)
    try:
        return AssetRepository(conn).list(include_deleted=include_deleted)
    finally:
        conn.close()


def get_asset(paths: AppPaths, asset_id: str) -> AssetRecord | None:
    conn = initialize_database(paths)
    try:
        return AssetRepository(conn).get(asset_id)
    finally:
        conn.close()


def create_generation_job(
    paths: AppPaths,
    *,
    backend_id: str,
    model_id: str,
    mode: str,
    input_text: str,
    voice_id: str | None = None,
    params: dict[str, object] | None = None,
    status: str = "queued",
) -> GenerationJobRecord:
    if status not in JOB_STATUSES:
        raise ValueError(f"unsupported job status: {status}")
    text = input_text.strip()
    if not text:
        raise ValueError("input_text is required")
    now = utc_now()
    record = GenerationJobRecord(
        id=str(uuid4()),
        backend_id=backend_id,
        model_id=model_id,
        mode=mode,
        status=status,
        input_text=text,
        voice_id=voice_id,
        params_json=json.dumps(params or {}, ensure_ascii=False),
        output_asset_id=None,
        error_summary="",
        legacy_generation_id=None,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    conn = initialize_database(paths)
    try:
        return GenerationJobRepository(conn).insert(record)
    finally:
        conn.close()


def list_generation_jobs(paths: AppPaths, *, include_deleted: bool = False) -> list[GenerationJobRecord]:
    conn = initialize_database(paths)
    try:
        return GenerationJobRepository(conn).list(include_deleted=include_deleted)
    finally:
        conn.close()


def get_generation_job(paths: AppPaths, job_id: str) -> GenerationJobRecord | None:
    conn = initialize_database(paths)
    try:
        return GenerationJobRepository(conn).get(job_id)
    finally:
        conn.close()


def get_generation_take(paths: AppPaths, take_id: str) -> GenerationTakeRecord | None:
    conn = initialize_database(paths)
    try:
        return GenerationTakeRepository(conn).get(take_id)
    finally:
        conn.close()


def update_generation_job(paths: AppPaths, job_id: str, **fields: object) -> GenerationJobRecord:
    if "status" in fields and fields["status"] not in JOB_STATUSES:
        raise ValueError(f"unsupported job status: {fields['status']}")
    conn = initialize_database(paths)
    try:
        return GenerationJobRepository(conn).update(job_id, **fields)
    finally:
        conn.close()


def create_generation_take(
    paths: AppPaths,
    *,
    job_id: str,
    backend_id: str,
    take_index: int,
    label: str = "",
    params: dict[str, object] | None = None,
    status: str = "queued",
    output_asset_id: str | None = None,
) -> GenerationTakeRecord:
    if status not in JOB_STATUSES:
        raise ValueError(f"unsupported take status: {status}")
    now = utc_now()
    record = GenerationTakeRecord(
        id=str(uuid4()),
        job_id=job_id,
        backend_id=backend_id,
        take_index=int(take_index),
        label=label,
        status=status,
        params_json=json.dumps(params or {}, ensure_ascii=False),
        output_asset_id=output_asset_id,
        legacy_generation_id=None,
        is_selected=False,
        error_summary="",
        created_at=now,
        updated_at=now,
    )
    conn = initialize_database(paths)
    try:
        return GenerationTakeRepository(conn).insert(record)
    finally:
        conn.close()


def list_generation_takes(paths: AppPaths, job_id: str) -> list[GenerationTakeRecord]:
    conn = initialize_database(paths)
    try:
        return GenerationTakeRepository(conn).list_for_job(job_id)
    finally:
        conn.close()


def update_generation_take(paths: AppPaths, take_id: str, **fields: object) -> GenerationTakeRecord:
    if "status" in fields and fields["status"] not in JOB_STATUSES:
        raise ValueError(f"unsupported take status: {fields['status']}")
    conn = initialize_database(paths)
    try:
        return GenerationTakeRepository(conn).update(take_id, **fields)
    finally:
        conn.close()


def select_generation_take(paths: AppPaths, take_id: str) -> GenerationTakeRecord:
    conn = initialize_database(paths)
    try:
        return GenerationTakeRepository(conn).select(take_id)
    finally:
        conn.close()


def generation_take_to_dict(paths: AppPaths, take: GenerationTakeRecord) -> dict[str, object]:
    payload = take.to_dict()
    payload["params"] = json.loads(take.params_json or "{}")
    payload["output_asset"] = None
    if take.output_asset_id:
        asset = get_asset(paths, take.output_asset_id)
        payload["output_asset"] = asset.to_dict() if asset else None
    return payload


def select_take_and_project(paths: AppPaths, take_id: str) -> GenerationTakeRecord:
    take = get_generation_take(paths, take_id)
    if take is None:
        raise KeyError(f"generation take not found: {take_id}")
    if take.status != "succeeded":
        raise ValueError("only succeeded takes can be selected")
    if not take.output_asset_id:
        raise ValueError("selected take has no output asset")
    asset = get_asset(paths, take.output_asset_id)
    if asset is None:
        raise KeyError(f"asset not found: {take.output_asset_id}")
    job = get_generation_job(paths, take.job_id)
    if job is None:
        raise KeyError(f"generation job not found: {take.job_id}")

    legacy_generation_id = job.legacy_generation_id or take.legacy_generation_id
    if not legacy_generation_id:
        legacy_generation_id = _create_selected_take_generation(paths, job, take).id

    sample_rate = int(asset.sample_rate or 0)
    mark_generation_succeeded(
        paths,
        legacy_generation_id,
        source_output_audio_path=paths.project_root / asset.path,
        sample_rate=sample_rate,
    )
    select_generation_take(paths, take_id)
    selected = update_generation_take(paths, take_id, legacy_generation_id=legacy_generation_id)
    update_generation_job(
        paths,
        job.id,
        status="succeeded",
        output_asset_id=asset.id,
        legacy_generation_id=legacy_generation_id,
        error_summary="",
    )
    return selected


def _create_selected_take_generation(
    paths: AppPaths,
    job: GenerationJobRecord,
    take: GenerationTakeRecord,
):
    params = json.loads(take.params_json or job.params_json or "{}")
    return create_generation(
        paths,
        input_text=job.input_text,
        control_instruction=json.dumps(
            {
                "engine": job.backend_id,
                "selected_take_id": take.id,
                "take_index": take.take_index,
                "params": params,
            },
            ensure_ascii=False,
        ),
        voice_id=job.voice_id,
        reference_audio_path=None,
        prompt_text=str(params.get("emo_text") or ""),
        cfg_value=float(params.get("emo_alpha", 1.0)),
        inference_timesteps=int(params.get("max_text_tokens_per_segment", 120)),
        normalize=False,
        denoise=False,
    )
