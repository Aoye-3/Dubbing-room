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
from voxcpm_app.generation_history import list_generations
from voxcpm_app.generation_service import GenerationService
from voxcpm_app.generation_service import VoxCPMSynthesizer
from voxcpm_app.job_queue import GenerationJobQueue
from voxcpm_app.job_store import (
    create_asset,
    create_generation_job,
    create_generation_take,
    get_generation_job,
    list_generation_takes,
)
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


class FakeIndexTTS2Service:
    def __init__(self, paths: AppPaths, *, fail_take_indexes: set[int] | None = None):
        self.paths = paths
        self.fail_take_indexes = fail_take_indexes or set()
        self.calls: list[dict] = []

    def generate_take(self, payload: dict, *, take_id: str):
        self.calls.append({"payload": payload, "take_id": take_id})
        take_index = int(payload.get("take_index", len(self.calls)))
        if take_index in self.fail_take_indexes:
            raise RuntimeError(f"take {take_index} failed")
        output_path = self.paths.tmp_dir / f"{take_id}.wav"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(f"take-{take_index}".encode("utf-8"))
        return output_path, 24000


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
    assert synth.calls[0]["min_len"] == 2
    assert synth.calls[0]["max_len"] == 4096
    assert synth.calls[0]["retry_badcase"] is True


def test_generation_service_reports_generation_job_id_to_runtime(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    coordinator = RuntimeCoordinator()

    class ObservingSynthesizer(FakeSynthesizer):
        def __init__(self):
            super().__init__()
            self.active_job_id = None

        def synthesize(self, **kwargs):
            self.active_job_id = coordinator.status("voxcpm2")["active_job_id"]
            return super().synthesize(**kwargs)

    synth = ObservingSynthesizer()
    service = GenerationService(paths, synthesizer=synth, coordinator=coordinator)

    record = service.generate_audio(generation_payload(generation_job_id="job-123"))

    assert record.status == "succeeded"
    assert synth.active_job_id == "job-123"


def test_voxcpm_synthesizer_ignores_control_for_ultimate_clone():
    class FakeModel:
        def __init__(self):
            self.calls: list[dict] = []
            self.tts_model = type("TTS", (), {"sample_rate": 48000})()

        def generate(self, **kwargs):
            self.calls.append(kwargs)
            return np.zeros(10, dtype=np.float32)

    fake_model = FakeModel()
    synth = VoxCPMSynthesizer()
    synth._model = fake_model

    sample_rate, _audio = synth.synthesize(
        input_text="Target text.",
        control_instruction="cheerful",
        reference_audio_path="speaker.wav",
        prompt_text="reference transcript",
        cfg_value=2.0,
        inference_timesteps=10,
        min_len=2,
        max_len=4096,
        normalize=False,
        denoise=False,
        retry_badcase=True,
        retry_badcase_max_times=3,
        retry_badcase_ratio_threshold=6.0,
    )

    assert sample_rate == 48000
    assert fake_model.calls[0]["text"] == "Target text."
    assert fake_model.calls[0]["prompt_wav_path"] == "speaker.wav"
    assert fake_model.calls[0]["reference_wav_path"] == "speaker.wav"


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
        indextts2 = status["items"][1]
        assert indextts2["backend_id"] == "indextts2"
        assert indextts2["busy"] is True
        assert indextts2["active_job_id"] is None
        assert indextts2["details"]["active_backend"] == "voxcpm2"
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
            assert body["type"] == "ValueError"
            assert body["code"] == "validation_error"
            assert body["details"] == {}
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


def test_backend_generation_take_api_returns_asset_and_selects_take(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    output_audio = tmp_path / "take.wav"
    output_audio.write_bytes(b"take-audio")
    asset = create_asset(paths, kind="take_output", path=output_audio, sample_rate=24000)
    job = create_generation_job(
        paths,
        backend_id="indextts2",
        model_id="IndexTTS2",
        mode="line_performance",
        input_text="queued line",
        params={"emotion_mode": "same_voice"},
    )
    take = create_generation_take(
        paths,
        job_id=job.id,
        backend_id="indextts2",
        take_index=1,
        label="Take 1",
        status="succeeded",
        output_asset_id=asset.id,
    )
    service = GenerationService(paths, synthesizer=FakeSynthesizer())
    server = _start_server(paths, service)
    try:
        listed = _request_json(server, "GET", f"/generation-jobs/{job.id}/takes")
        selected = _request_json(server, "POST", f"/generation-takes/{take.id}/select", {})
        updated_job = _request_json(server, "GET", f"/generation-jobs/{job.id}")

        assert listed["items"][0]["output_asset"]["path"] == "take.wav"
        assert selected["is_selected"] is True
        assert selected["legacy_generation_id"]
        assert updated_job["output_asset_id"] == asset.id
        assert updated_job["legacy_generation_id"] == selected["legacy_generation_id"]
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


def test_generation_job_queue_runs_multiple_indextts2_takes_and_projects_first_success(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    service = GenerationService(paths, synthesizer=FakeSynthesizer())
    index_service = FakeIndexTTS2Service(paths, fail_take_indexes={2})
    queue = GenerationJobQueue(paths, service, index_service)  # type: ignore[arg-type]

    job = queue.submit(
        {
            "backend_id": "indextts2",
            "model_id": "IndexTTS2",
            "mode": "line_performance",
            "input_text": "queued line",
            "params": {
                "text": "queued line",
                "speaker": {"kind": "upload", "path": str(_write_audio(tmp_path, "speaker.wav"))},
                "emotion_mode": "same_voice",
                "emo_alpha": 1,
                "take_count": 3,
            },
        }
    )

    completed = _wait_for_queue_job(paths, job.id, "succeeded")
    takes = list_generation_takes(paths, job.id)
    history = list_generations(paths)

    assert completed.status == "succeeded"
    assert len(takes) == 3
    assert [take.status for take in takes] == ["succeeded", "failed", "succeeded"]
    assert [take.is_selected for take in takes] == [True, False, False]
    assert takes[0].legacy_generation_id == completed.legacy_generation_id
    assert completed.output_asset_id == takes[0].output_asset_id
    assert len(history) == 1
    assert history[0].id == completed.legacy_generation_id
    assert history[0].output_audio_path is not None
    assert (tmp_path / history[0].output_audio_path).read_bytes() == b"take-1"


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


def _wait_for_queue_job(paths: AppPaths, job_id: str, status: str):
    for _ in range(50):
        job = get_generation_job(paths, job_id)
        if job is not None and job.status == status:
            return job
        time.sleep(0.1)
    raise AssertionError(f"job {job_id} did not reach {status}")


def _write_audio(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(b"audio")
    return path
