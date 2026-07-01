from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voxcpm_app.backend_server import build_handler
from voxcpm_app.generation_service import GenerationService
from voxcpm_app.job_queue import GenerationJobQueue
from voxcpm_app.job_store import create_generation_job
from voxcpm_app.paths import AppPaths
from voxcpm_app.runtime import RuntimeCoordinator
from voxcpm_app.voice_library import create_voice, list_voices


class FakeSynthesizer:
    def __init__(self, *, error: Exception | None = None):
        self.error = error
        self.calls: list[dict] = []

    def synthesize(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return 48000, np.zeros(2400, dtype=np.float32)


def generation_payload(**overrides):
    payload = {
        "input_text": "Hello from VoxCPM Box",
        "control_instruction": "warm and clear",
        "prompt_text": "",
        "cfg_value": 2.0,
        "inference_timesteps": 10,
        "normalize": False,
        "denoise": False,
        "reference": {"kind": "none"},
    }
    payload.update(overrides)
    return payload


def test_generation_service_generates_without_reference_and_records_history(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    synth = FakeSynthesizer()
    service = GenerationService(paths, synthesizer=synth)

    record = service.generate_audio(generation_payload())

    assert record.status == "succeeded"
    assert record.reference_audio_path is None
    assert record.output_audio_path == f"data/app/generations/{record.id}.wav"
    assert (tmp_path / record.output_audio_path).exists()
    assert synth.calls[0]["reference_audio_path"] is None
    assert synth.calls[0]["prompt_text"] == ""


def test_generation_service_copies_uploaded_reference_to_app_tmp(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    uploaded = tmp_path / "uploaded-reference.m4a"
    uploaded.write_bytes(b"reference-bytes")
    synth = FakeSynthesizer()
    service = GenerationService(paths, synthesizer=synth)

    record = service.generate_audio(
        generation_payload(reference={"kind": "upload", "path": str(uploaded)})
    )

    assert record.status == "succeeded"
    assert record.reference_audio_path is not None
    assert record.reference_audio_path.startswith("data/app/tmp/")
    assert (tmp_path / record.reference_audio_path).read_bytes() == b"reference-bytes"
    assert synth.calls[0]["reference_audio_path"] == str((tmp_path / record.reference_audio_path).resolve())


def test_generation_service_uses_saved_voice_and_updates_last_used(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    source_voice = tmp_path / "voice.wav"
    source_voice.write_bytes(b"voice-bytes")
    voice = create_voice(
        paths,
        source_audio_path=source_voice,
        display_name="Studio Voice",
        tags=["narration"],
        notes="",
    )
    synth = FakeSynthesizer()
    service = GenerationService(paths, synthesizer=synth)

    record = service.generate_audio(
        generation_payload(reference={"kind": "saved_voice", "voice_id": voice.id})
    )

    updated_voice = list_voices(paths)[0]
    assert record.status == "succeeded"
    assert record.voice_id == voice.id
    assert record.reference_audio_path == voice.audio_path
    assert updated_voice.last_used_at is not None
    assert synth.calls[0]["reference_audio_path"] == str((tmp_path / voice.audio_path).resolve())


def test_generation_service_marks_failed_history_when_synthesis_fails(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    service = GenerationService(paths, synthesizer=FakeSynthesizer(error=RuntimeError("model unavailable")))

    record = service.generate_audio(generation_payload())

    assert record.status == "failed"
    assert record.output_audio_path is None
    assert record.error_summary == "model unavailable"


def test_generated_output_can_be_saved_as_voice(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    service = GenerationService(paths, synthesizer=FakeSynthesizer())
    record = service.generate_audio(generation_payload())

    saved = create_voice(
        paths,
        source_audio_path=tmp_path / record.output_audio_path,
        display_name="Generated Voice",
        tags=["generated"],
        notes="Created from output",
        source="generated",
    )

    assert saved.source == "generated"
    assert saved.audio_path.startswith("data/app/voices/")
    assert list_voices(paths)[0].id == saved.id


def test_backend_health_and_app_service_routes(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    service = GenerationService(paths, synthesizer=FakeSynthesizer())
    server = _start_server(paths, service)
    try:
        health = _request_json(server, "GET", "/health")
        listed = _request_json(server, "POST", "/app-service", {"action": "list-voices", "payload": {}})

        assert health["ok"] is True
        assert listed == {"items": []}
    finally:
        server.shutdown()
        server.server_close()


def test_backend_runtime_status_reports_voxcpm2_busy_job(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    coordinator = RuntimeCoordinator()
    service = GenerationService(paths, synthesizer=FakeSynthesizer(), coordinator=coordinator)
    server = _start_server(paths, service)
    try:
        with coordinator.lease("voxcpm2", job_id="voxcpm-job"):
            status = _request_json(server, "GET", "/runtime-backends")

        voxcpm2 = status["items"][0]
        assert voxcpm2["backend_id"] == "voxcpm2"
        assert voxcpm2["busy"] is True
        assert voxcpm2["active_job_id"] == "voxcpm-job"
        assert isinstance(voxcpm2["started_at"], str)
    finally:
        server.shutdown()
        server.server_close()


def test_backend_returns_json_error_for_invalid_generation_request(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    service = GenerationService(paths, synthesizer=FakeSynthesizer())
    server = _start_server(paths, service)
    try:
        try:
            _request_json(server, "POST", "/generate-audio", generation_payload(input_text=""))
        except urllib.error.HTTPError as error:
            body = json.loads(error.read().decode("utf-8"))
            assert error.code == 400
            assert body["error"] == "input_text is required"
        else:
            raise AssertionError("expected HTTP 400")
    finally:
        server.shutdown()
        server.server_close()


def test_backend_generation_job_api_runs_voxcpm2_job(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    service = GenerationService(paths, synthesizer=FakeSynthesizer())
    server = _start_server(paths, service)
    try:
        job = _request_json(
            server,
            "POST",
            "/generation-jobs",
            {
                "backend_id": "voxcpm2",
                "model_id": "openbmb/VoxCPM2",
                "mode": "voice_design",
                "input_text": "queued hello",
                "params": generation_payload(input_text="queued hello"),
            },
        )
        completed = _wait_for_job(server, job["id"], "succeeded")
        jobs = _request_json(server, "GET", "/generation-jobs")

        assert job["status"] == "queued"
        assert completed["status"] == "succeeded"
        assert completed["legacy_generation_id"]
        assert completed["output_asset_id"]
        assert jobs["items"][0]["id"] == job["id"]
    finally:
        server.shutdown()
        server.server_close()


def test_generation_job_queue_can_cancel_queued_job(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    service = GenerationService(paths, synthesizer=FakeSynthesizer())
    queue = GenerationJobQueue(paths, service, None)  # type: ignore[arg-type]
    job = create_generation_job(
        paths,
        backend_id="voxcpm2",
        model_id="openbmb/VoxCPM2",
        mode="voice_design",
        input_text="cancel me",
        params=generation_payload(input_text="cancel me"),
    )

    cancelled = queue.cancel(job.id)

    assert cancelled.status == "cancelled"


def _start_server(paths: AppPaths, service: GenerationService):
    from http.server import ThreadingHTTPServer

    handler = build_handler(paths, generation_service=service)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _request_json(server, method: str, path: str, payload: dict | None = None):
    url = f"http://127.0.0.1:{server.server_address[1]}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_for_job(server, job_id: str, status: str):
    for _ in range(50):
        job = _request_json(server, "GET", f"/generation-jobs/{job_id}")
        if job["status"] == status:
            return job
        time.sleep(0.1)
    raise AssertionError(f"job {job_id} did not reach {status}")
