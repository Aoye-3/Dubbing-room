from __future__ import annotations

import json
import subprocess
import sys
import threading
import types
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voxcpm_app.backend_server import build_handler
from voxcpm_app.errors import AppBackendError
from voxcpm_app.indextts2_service import IndexTTS2Service, SubprocessIndexTTS2Runner, _runtime_cache_env
from voxcpm_app.indextts2_worker import run as run_indextts2_worker
from voxcpm_app.paths import AppPaths
from voxcpm_app.runtime import RuntimeBackendStatus, RuntimeCoordinator
from voxcpm_app.voice_library import create_voice, list_voices


class FakeIndexTTS2Runner:
    def __init__(self, *, error: Exception | None = None):
        self.error = error
        self.calls: list[dict] = []

    def status(self, paths: AppPaths, *, coordinator: RuntimeCoordinator) -> RuntimeBackendStatus:
        return RuntimeBackendStatus(
            backend_id="indextts2",
            display_name="IndexTTS2",
            enabled=True,
            configured=True,
            loaded=False,
            busy=coordinator.is_busy_backend("indextts2"),
            device="fake-cuda",
            last_error=coordinator.last_error("indextts2"),
            capabilities=["line_performance", "emotion_vector"],
        )

    def synthesize(self, paths: AppPaths, payload: dict, output_path: Path) -> int:
        self.calls.append(payload)
        if self.error is not None:
            raise self.error
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), np.zeros(800, dtype=np.float32), 16000)
        return 16000


def test_indextts2_generates_with_saved_voice_and_vector(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    source_voice = tmp_path / "speaker.wav"
    source_voice.write_bytes(b"speaker-bytes")
    voice = create_voice(paths, source_audio_path=source_voice, display_name="Actor A")
    runner = FakeIndexTTS2Runner()
    service = IndexTTS2Service(paths, runner=runner, coordinator=RuntimeCoordinator())

    record = service.generate(
        {
            "text": "快躲起来！是他要来了！",
            "speaker": {"kind": "saved_voice", "voice_id": voice.id},
            "emotion_mode": "vector",
            "emo_vector": {"happy": 0.1, "angry": 0.5, "sad": 0, "afraid": 0.2},
            "emo_alpha": 0.8,
            "interval_silence": 200,
            "max_text_tokens_per_segment": 120,
        }
    )

    params = json.loads(record.control_instruction)
    updated_voice = list_voices(paths)[0]
    assert record.status == "succeeded"
    assert record.voice_id == voice.id
    assert record.output_audio_path == f"data/app/generations/{record.id}.wav"
    assert (tmp_path / record.output_audio_path).exists()
    assert params["engine"] == "indextts2"
    assert params["emotion_mode"] == "vector"
    assert runner.calls[0]["emo_vector"] == [0.1, 0.5, 0.0, 0.2, 0.0, 0.0, 0.0, 0.0]
    assert updated_voice.last_used_at is not None


def test_indextts2_text_emotion_can_use_line_text(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    speaker = tmp_path / "speaker.wav"
    speaker.write_bytes(b"speaker-bytes")
    runner = FakeIndexTTS2Runner()
    service = IndexTTS2Service(paths, runner=runner, coordinator=RuntimeCoordinator())

    record = service.generate(
        {
            "text": "help me sound worried",
            "speaker": {"kind": "upload", "path": str(speaker)},
            "emotion_mode": "text_prompt",
        }
    )

    assert record.status == "succeeded"
    assert runner.calls[0]["use_emo_text"] is True
    assert runner.calls[0]["emo_text"] is None


def test_indextts2_rejects_overweighted_emotion_vector(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    speaker = tmp_path / "speaker.wav"
    speaker.write_bytes(b"speaker-bytes")
    service = IndexTTS2Service(paths, runner=FakeIndexTTS2Runner(), coordinator=RuntimeCoordinator())

    with pytest.raises(ValueError, match="sum to 0.8 or less"):
        service.generate(
            {
                "text": "hello",
                "speaker": {"kind": "upload", "path": str(speaker)},
                "emotion_mode": "vector",
                "emo_vector": {"happy": 0.5, "angry": 0.4},
            }
        )


def test_indextts2_requires_speaker_reference(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    service = IndexTTS2Service(paths, runner=FakeIndexTTS2Runner(), coordinator=RuntimeCoordinator())

    with pytest.raises(ValueError, match="speaker reference is required"):
        service.generate({"text": "hello", "emotion_mode": "same_voice"})


def test_indextts2_rejects_missing_emotion_audio_for_audio_mode(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    speaker = tmp_path / "speaker.wav"
    speaker.write_bytes(b"speaker-bytes")
    service = IndexTTS2Service(paths, runner=FakeIndexTTS2Runner(), coordinator=RuntimeCoordinator())

    with pytest.raises(ValueError, match="emotion_mode audio_prompt requires its matching emotion source"):
        service.generate(
            {
                "text": "hello",
                "speaker": {"kind": "upload", "path": str(speaker)},
                "emotion_mode": "audio_prompt",
            }
        )


def test_indextts2_rejects_multiple_emotion_sources(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    speaker = tmp_path / "speaker.wav"
    emotion = tmp_path / "emotion.wav"
    speaker.write_bytes(b"speaker-bytes")
    emotion.write_bytes(b"emotion-bytes")
    service = IndexTTS2Service(paths, runner=FakeIndexTTS2Runner(), coordinator=RuntimeCoordinator())

    with pytest.raises(ValueError, match="emotion source must be one of"):
        service.generate(
            {
                "text": "hello",
                "speaker": {"kind": "upload", "path": str(speaker)},
                "emotion_mode": "audio_prompt",
                "emotion_audio": {"kind": "upload", "path": str(emotion)},
                "emo_vector": {"angry": 0.8},
            }
        )


def test_indextts2_marks_failed_when_runner_fails(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    speaker = tmp_path / "speaker.wav"
    speaker.write_bytes(b"speaker-bytes")
    service = IndexTTS2Service(
        paths,
        runner=FakeIndexTTS2Runner(error=RuntimeError("IndexTTS2 runtime unavailable")),
        coordinator=RuntimeCoordinator(),
    )

    record = service.generate(
        {
            "text": "hello",
            "speaker": {"kind": "upload", "path": str(speaker)},
            "emotion_mode": "same_voice",
        }
    )

    assert record.status == "failed"
    assert record.output_audio_path is None
    assert record.error_summary == "IndexTTS2 runtime unavailable"


def test_runtime_coordinator_allows_only_one_gpu_lease():
    coordinator = RuntimeCoordinator()

    with coordinator.lease("voxcpm2", job_id="job-1"):
        status = coordinator.status("voxcpm2")
        assert status["busy"] is True
        assert status["active_job_id"] == "job-1"
        assert isinstance(status["started_at"], str)
        with pytest.raises(RuntimeError, match="runtime busy: voxcpm2"):
            with coordinator.lease("indextts2"):
                pass


def test_indextts2_fails_when_voxcpm2_holds_runtime_lease(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    speaker = tmp_path / "speaker.wav"
    speaker.write_bytes(b"speaker-bytes")
    coordinator = RuntimeCoordinator()
    service = IndexTTS2Service(paths, runner=FakeIndexTTS2Runner(), coordinator=coordinator)

    with coordinator.lease("voxcpm2", job_id="voxcpm-job"):
        record = service.generate(
            {
                "text": "hello",
                "speaker": {"kind": "upload", "path": str(speaker)},
                "emotion_mode": "same_voice",
            }
        )

    assert record.status == "failed"
    assert record.error_summary == "runtime busy: voxcpm2"


def test_subprocess_runner_status_lists_missing_checkpoint_files(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    source_root = tmp_path / "third_party" / "index-tts"
    runtime_python = tmp_path / "data" / "runtimes" / "indextts2" / ".venv" / "Scripts" / "python.exe"
    checkpoint_dir = source_root / "checkpoints"
    source_root.mkdir(parents=True)
    runtime_python.parent.mkdir(parents=True)
    checkpoint_dir.mkdir(parents=True)
    runtime_python.write_text("", encoding="utf-8")
    (checkpoint_dir / "config.yaml").write_text("model: fake\n", encoding="utf-8")

    status = SubprocessIndexTTS2Runner().status(paths, coordinator=RuntimeCoordinator())

    assert status.configured is False
    assert status.state == "missing_checkpoints"
    assert status.details is not None
    assert status.details["runtime_python"] == str(runtime_python)
    assert status.details["model_dir"] == str(checkpoint_dir)
    assert isinstance(status.details["missing_checkpoints"], list)
    assert "bpe.model" in status.last_error
    assert "gpt.pth" in status.last_error
    assert "s2mel.pth" in status.last_error


def test_indextts2_worker_cache_env_stays_project_local(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    env = _runtime_cache_env(paths)

    for key in ["HF_HOME", "TORCH_EXTENSIONS_DIR", "XDG_CACHE_HOME", "MPLCONFIGDIR", "NUMBA_CACHE_DIR"]:
        value = Path(env[key]).resolve()
        assert value == tmp_path.resolve() or tmp_path.resolve() in value.parents


def test_subprocess_runner_status_reports_missing_config(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    source_root = tmp_path / "third_party" / "index-tts"
    runtime_python = tmp_path / "data" / "runtimes" / "indextts2" / ".venv" / "Scripts" / "python.exe"
    checkpoint_dir = source_root / "checkpoints"
    source_root.mkdir(parents=True)
    runtime_python.parent.mkdir(parents=True)
    checkpoint_dir.mkdir(parents=True)
    runtime_python.write_text("", encoding="utf-8")

    status = SubprocessIndexTTS2Runner().status(paths, coordinator=RuntimeCoordinator())

    assert status.configured is False
    assert status.details is not None
    assert status.details["missing_config"] == [str(checkpoint_dir / "config.yaml")]
    assert "config.yaml" in status.last_error


def test_subprocess_runner_reports_outside_project_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    paths = AppPaths.from_project_root(tmp_path)
    outside_runtime = tmp_path.parent / "outside-runtime" / "python.exe"
    monkeypatch.setenv("INDEXTTS2_PYTHON", str(outside_runtime))

    status = SubprocessIndexTTS2Runner().status(paths, coordinator=RuntimeCoordinator())

    assert status.configured is False
    assert status.state == "missing_runtime"
    assert status.details is not None
    assert str(outside_runtime.resolve()) in status.details["outside_project_paths"]


def test_indextts2_worker_passes_device_to_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    class FakeIndexTTS2:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def infer(self, **kwargs):
            captured["infer"] = kwargs
            sf.write(str(kwargs["output_path"]), np.zeros(10, dtype=np.float32), 16000)

    indextts_module = types.ModuleType("indextts")
    infer_module = types.ModuleType("indextts.infer_v2")
    infer_module.IndexTTS2 = FakeIndexTTS2
    monkeypatch.setitem(sys.modules, "indextts", indextts_module)
    monkeypatch.setitem(sys.modules, "indextts.infer_v2", infer_module)

    output_path = tmp_path / "out.wav"
    result = run_indextts2_worker(
        {
            "source_root": str(tmp_path),
            "cfg_path": str(tmp_path / "config.yaml"),
            "model_dir": str(tmp_path / "checkpoints"),
            "output_path": str(output_path),
            "device": "cuda:1",
            "spk_audio_prompt": str(tmp_path / "speaker.wav"),
            "text": "hello",
            "use_accel": True,
            "use_torch_compile": True,
        }
    )

    assert result["output_path"] == str(output_path.resolve())
    assert captured["device"] == "cuda:1"
    assert captured["use_accel"] is True
    assert captured["use_torch_compile"] is True


def test_subprocess_runner_timeout_is_classified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    paths = AppPaths.from_project_root(tmp_path)
    source_root = tmp_path / "third_party" / "index-tts"
    runtime_python = tmp_path / "data" / "runtimes" / "indextts2" / ".venv" / "Scripts" / "python.exe"
    checkpoint_dir = source_root / "checkpoints"
    source_root.mkdir(parents=True)
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_text("", encoding="utf-8")
    for item in [
        "config.yaml",
        "bpe.model",
        "gpt.pth",
        "s2mel.pth",
        "wav2vec2bert_stats.pt",
        "feat1.pt",
        "feat2.pt",
        "qwen0.6bemo4-merge",
        "hf_cache/semantic_codec_model.safetensors",
        "hf_cache/campplus_cn_common.bin",
        "hf_cache/bigvgan/config.json",
        "hf_cache/bigvgan/bigvgan_generator.pt",
        "hf_cache/w2v-bert-2.0",
    ]:
        target = checkpoint_dir / item
        target.parent.mkdir(parents=True, exist_ok=True)
        if "." in target.name:
            target.write_text("fake", encoding="utf-8")
        else:
            target.mkdir(parents=True, exist_ok=True)

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("INDEXTTS2_WORKER_TIMEOUT_SECONDS", "1")

    with pytest.raises(AppBackendError) as raised:
        SubprocessIndexTTS2Runner().synthesize(
            paths,
            {"spk_audio_prompt": str(tmp_path / "speaker.wav"), "text": "hello"},
            tmp_path / "out.wav",
        )

    assert raised.value.code == "timeout"


def test_subprocess_runner_preserves_worker_error_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    paths = AppPaths.from_project_root(tmp_path)
    _create_complete_indextts2_runtime(tmp_path)

    def fake_run(*args, **kwargs):
        return types.SimpleNamespace(
            stdout=json.dumps({"ok": False, "error": "boom", "code": "worker_failed", "details": {"phase": "infer"}}),
            stderr="",
            returncode=1,
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(AppBackendError) as raised:
        SubprocessIndexTTS2Runner().synthesize(
            paths,
            {"spk_audio_prompt": str(tmp_path / "speaker.wav"), "text": "hello"},
            tmp_path / "out.wav",
        )

    assert raised.value.code == "worker_failed"
    assert raised.value.details == {"phase": "infer"}


def test_subprocess_runner_classifies_missing_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    paths = AppPaths.from_project_root(tmp_path)
    _create_complete_indextts2_runtime(tmp_path)

    def fake_run(*args, **kwargs):
        return types.SimpleNamespace(stdout=json.dumps({"ok": True}), stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(AppBackendError) as raised:
        SubprocessIndexTTS2Runner().synthesize(
            paths,
            {"spk_audio_prompt": str(tmp_path / "speaker.wav"), "text": "hello"},
            tmp_path / "missing.wav",
        )

    assert raised.value.code == "output_missing"


def test_backend_runtime_status_and_indextts2_generate_route(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    speaker = tmp_path / "speaker.wav"
    speaker.write_bytes(b"speaker-bytes")
    service = IndexTTS2Service(paths, runner=FakeIndexTTS2Runner(), coordinator=RuntimeCoordinator())
    server = _start_server(paths, service)
    try:
        status = _request_json(server, "GET", "/runtime-backends")
        record = _request_json(
            server,
            "POST",
            "/indextts2/generate",
            {"text": "hello", "speaker": {"kind": "upload", "path": str(speaker)}, "emotion_mode": "same_voice"},
        )

        assert [item["backend_id"] for item in status["items"]] == ["voxcpm2", "indextts2"]
        assert status["items"][1]["configured"] is True
        assert record["status"] == "succeeded"
        assert record["output_audio_path"].startswith("data/app/generations/")
    finally:
        server.shutdown()
        server.server_close()


def test_backend_returns_400_for_missing_indextts2_speaker(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    service = IndexTTS2Service(paths, runner=FakeIndexTTS2Runner(), coordinator=RuntimeCoordinator())
    server = _start_server(paths, service)
    try:
        with pytest.raises(urllib.error.HTTPError) as raised:
            _request_json(server, "POST", "/indextts2/generate", {"text": "hello"})
        body = json.loads(raised.value.read().decode("utf-8"))
        assert raised.value.code == 400
        assert body["error"] == "speaker reference is required"
        assert body["type"] == "ValueError"
        assert body["code"] == "validation_error"
        assert body["details"] == {}
    finally:
        server.shutdown()
        server.server_close()


def _start_server(paths: AppPaths, service: IndexTTS2Service):
    from http.server import ThreadingHTTPServer

    handler = build_handler(paths, indextts2_service=service)
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


def _create_complete_indextts2_runtime(root: Path) -> None:
    source_root = root / "third_party" / "index-tts"
    runtime_python = root / "data" / "runtimes" / "indextts2" / ".venv" / "Scripts" / "python.exe"
    checkpoint_dir = source_root / "checkpoints"
    source_root.mkdir(parents=True, exist_ok=True)
    runtime_python.parent.mkdir(parents=True, exist_ok=True)
    runtime_python.write_text("", encoding="utf-8")
    for item in [
        "config.yaml",
        "bpe.model",
        "gpt.pth",
        "s2mel.pth",
        "wav2vec2bert_stats.pt",
        "feat1.pt",
        "feat2.pt",
        "qwen0.6bemo4-merge",
        "hf_cache/semantic_codec_model.safetensors",
        "hf_cache/campplus_cn_common.bin",
        "hf_cache/bigvgan/config.json",
        "hf_cache/bigvgan/bigvgan_generator.pt",
        "hf_cache/w2v-bert-2.0",
    ]:
        target = checkpoint_dir / item
        target.parent.mkdir(parents=True, exist_ok=True)
        if "." in target.name:
            target.write_text("fake", encoding="utf-8")
        else:
            target.mkdir(parents=True, exist_ok=True)
