from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voxcpm_app.backend_server import build_handler
from voxcpm_app.indextts2_runtime_profile import (  # type: ignore[import-not-found]
    DEFAULT_RUNTIME_PROFILE,
    IndexTTS2RuntimeProfileStore,
)
from voxcpm_app.indextts2_service import IndexTTS2Service, SubprocessIndexTTS2Runner
from voxcpm_app.paths import AppPaths
from voxcpm_app.runtime import RuntimeBackendStatus, RuntimeCoordinator


class _ReadyRunner:
    def status(self, paths: AppPaths, *, coordinator: RuntimeCoordinator) -> RuntimeBackendStatus:
        return RuntimeBackendStatus(
            backend_id="indextts2", display_name="IndexTTS2", enabled=True, configured=True,
            loaded=False, busy=False, device="cuda", last_error="", capabilities=["emotion_text"],
        )

    def synthesize(self, paths: AppPaths, payload: dict[str, object], output_path: Path) -> int:
        raise AssertionError("configuration saving must not load or synthesize a model")


def test_runtime_profile_defaults_and_atomically_persists_only_known_fields(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    store = IndexTTS2RuntimeProfileStore(paths)

    assert store.load().profile == DEFAULT_RUNTIME_PROFILE
    saved = store.save({
        "precision": "bf16", "allow_text_emotion": False, "use_cuda_kernel": True,
        "use_deepspeed": True, "use_accel": False, "use_torch_compile": True,
    })

    assert saved.profile.precision == "bf16"
    assert saved.profile.use_deepspeed is True
    assert paths.indextts2_runtime_profile_path.read_text(encoding="utf-8")
    assert json.loads(paths.indextts2_runtime_profile_path.read_text(encoding="utf-8")) == {
        "precision": "bf16", "allow_text_emotion": False, "use_cuda_kernel": True,
        "use_deepspeed": True, "use_accel": False, "use_torch_compile": True,
    }
    assert not list(paths.app_root.glob("*.tmp"))


@pytest.mark.parametrize("payload", [
    {"precision": "fp16", "allow_text_emotion": True, "use_cuda_kernel": False, "use_deepspeed": False, "use_accel": False, "use_torch_compile": False},
    {"precision": "auto", "allow_text_emotion": 1, "use_cuda_kernel": False, "use_deepspeed": False, "use_accel": False, "use_torch_compile": False},
    {"precision": "auto", "allow_text_emotion": True, "use_cuda_kernel": False, "use_deepspeed": False, "use_accel": False, "use_torch_compile": False, "surprise": True},
])
def test_runtime_profile_rejects_invalid_or_unknown_fields(tmp_path: Path, payload: dict[str, object]):
    with pytest.raises(ValueError):
        IndexTTS2RuntimeProfileStore(AppPaths.from_project_root(tmp_path)).save(payload)


def test_requested_bf16_falls_back_to_fp32_and_low_vram_is_a_visible_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("voxcpm_app.indextts2_runtime_profile._cuda_bf16_available", lambda: (False, None))
    monkeypatch.setattr("voxcpm_app.indextts2_runtime_profile._cuda_memory_gb", lambda: (8.0, None))
    resolution = IndexTTS2RuntimeProfileStore(AppPaths.from_project_root(tmp_path)).save({
        "precision": "bf16", "allow_text_emotion": True, "use_cuda_kernel": False,
        "use_deepspeed": False, "use_accel": False, "use_torch_compile": False,
    })

    assert resolution.effective_precision == "fp32"
    assert any("BF16" in warning for warning in resolution.warnings)
    assert any("low VRAM" in warning for warning in resolution.warnings)


def test_runtime_profile_api_returns_effective_precision_and_identity_without_changing_runtime_envelope(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    service = IndexTTS2Service(paths, runner=_ReadyRunner(), coordinator=RuntimeCoordinator())
    server = _start_server(paths, service)
    try:
        response = _request(server, "GET", "/runtime-backends/indextts2/config")
        status = _request(server, "GET", "/runtime-backends")
        saved = _request(server, "POST", "/runtime-backends/indextts2/config", {
            "precision": "fp32", "allow_text_emotion": False, "use_cuda_kernel": True,
            "use_deepspeed": False, "use_accel": True, "use_torch_compile": False,
        })

        assert response["profile"]["precision"] == "auto"
        assert response["effective_precision"] in {"bf16", "fp32"}
        assert saved["profile"]["use_accel"] is True
        assert [item["backend_id"] for item in status["items"]] == ["voxcpm2", "indextts2"]
        details = status["items"][1]["details"]
        assert details["model_id"] == "IndexTTS-2.5"
        assert details["model_version"] == "2.5"
        assert details["upstream_commit"] == "a371df7d0746a0ae7fdf075798b6b04e34a0132e"
        assert details["supported_languages"] == ["ZH", "EN", "JA", "ES", "AR"]
        assert details["precision"] == "auto"
        assert "effective_precision" in details
        assert "warnings" in details
    finally:
        server.shutdown()
        server.server_close()


def test_runtime_profile_api_rejects_unknown_fields_and_corrupt_file_is_visible_warning(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    paths.app_root.mkdir(parents=True)
    paths.indextts2_runtime_profile_path.write_text("{not json", encoding="utf-8")
    server = _start_server(paths, IndexTTS2Service(paths, runner=_ReadyRunner(), coordinator=RuntimeCoordinator()))
    try:
        response = _request(server, "GET", "/runtime-backends/indextts2/config")
        assert response["profile"]["precision"] == "auto"
        assert response["warnings"]
        with pytest.raises(urllib.error.HTTPError) as raised:
            _request(server, "POST", "/runtime-backends/indextts2/config", {"precision": "auto"})
        assert raised.value.code == 400
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("source_family, model_family", [("2.0", "2.5"), ("2.5", "2.0")])
def test_runtime_status_reports_model_version_mismatch_for_complete_mixed_asset_families(
    tmp_path: Path, source_family: str, model_family: str,
):
    paths = AppPaths.from_project_root(tmp_path)
    _write_source_family(tmp_path, source_family)
    _write_model_family(tmp_path, model_family)

    status = SubprocessIndexTTS2Runner().status(paths, coordinator=RuntimeCoordinator())

    assert status.state == "model_version_mismatch"
    assert status.details is not None
    assert status.details["code"] == "model_version_mismatch"
    assert status.details["source_model_family"] == source_family
    assert status.details["checkpoint_model_family"] == model_family


def test_runtime_status_reports_missing_2_5_files_without_false_version_mismatch(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    _write_source_family(tmp_path, "2.5")
    checkpoint_dir = tmp_path / "third_party" / "index-tts" / "checkpoints-2.5"
    checkpoint_dir.mkdir(parents=True)
    (checkpoint_dir / "config.yaml").write_text("version: 2.5\n", encoding="utf-8")

    status = SubprocessIndexTTS2Runner().status(paths, coordinator=RuntimeCoordinator())

    assert status.state == "missing_checkpoints"
    assert status.details is not None
    assert status.details["code"] == "checkpoints_missing"
    assert "codec.pth" in status.last_error
    assert "multilingual_zh_ja_yue_char_del.tiktoken" in status.last_error


def _write_source_family(root: Path, family: str) -> None:
    source = root / "third_party" / "index-tts" / "indextts"
    source.mkdir(parents=True)
    filename = "infer_v2_5.py" if family == "2.5" else "infer_v2.py"
    (source / filename).write_text("# test source\n", encoding="utf-8")
    runtime_python = root / "data" / "runtimes" / "indextts2" / ".venv" / "Scripts" / "python.exe"
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_text("", encoding="utf-8")


def _write_model_family(root: Path, family: str) -> None:
    source = root / "third_party" / "index-tts"
    checkpoint_dir = source / "checkpoints-2.5"
    checkpoint_dir.mkdir(parents=True)
    if family == "2.5":
        files = ["config.yaml", "gpt.pth", "s2mel.pth", "codec.pth", "multilingual_zh_ja_yue_char_del.tiktoken", "wav2vec2bert_stats.pt"]
        config = "version: 2.5\n"
    else:
        files = ["config.yaml", "bpe.model", "gpt.pth", "s2mel.pth", "wav2vec2bert_stats.pt"]
        config = "version: 2.0\n"
    for filename in files:
        (checkpoint_dir / filename).write_text(config if filename == "config.yaml" else "", encoding="utf-8")


def _start_server(paths: AppPaths, service: IndexTTS2Service):
    from http.server import ThreadingHTTPServer
    server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(paths, indextts2_service=service))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _request(server, method: str, path: str, payload: dict[str, object] | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_address[1]}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))
