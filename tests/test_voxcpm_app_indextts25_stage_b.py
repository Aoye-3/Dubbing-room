from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import sys
import threading
import types
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voxcpm_app.db import initialize_database
from voxcpm_app.generation_history import create_generation, update_generation_warnings
from voxcpm_app.generation_history import list_generations
from voxcpm_app.indextts2_service import IndexTTS2Service, SubprocessIndexTTS2Session
from voxcpm_app.indextts2_worker import run_session
from voxcpm_app.job_store import (
    create_generation_job,
    create_generation_take,
    generation_take_to_dict,
    get_generation_job,
    select_take_and_project,
    update_generation_take,
)
from voxcpm_app.job_queue import GenerationJobQueue
from voxcpm_app.paths import AppPaths
from voxcpm_app.runtime import RuntimeBackendStatus, RuntimeCoordinator


def _install_fake_indextts25(monkeypatch: pytest.MonkeyPatch, captured: dict[str, object]) -> None:
    class FakeIndexTTS2:
        def __init__(self, **kwargs):
            captured.setdefault("construct", []).append(kwargs)

        def infer(self, **kwargs):
            captured.setdefault("infer", []).append(kwargs)
            if kwargs["text"] == "OOM":
                raise RuntimeError("CUDA out of memory while loading Qwen emotion")
            sf.write(kwargs["output_path"], np.zeros(10, dtype=np.float32), 24000)

    package = types.ModuleType("indextts")
    module = types.ModuleType("indextts.infer_v2_5")
    module.IndexTTS2 = FakeIndexTTS2
    monkeypatch.setitem(sys.modules, "indextts", package)
    monkeypatch.setitem(sys.modules, "indextts.infer_v2_5", module)


@pytest.mark.parametrize("language", ["ZH", "EN", "JA", "ES", "AR"])
def test_worker_jsonl_loads_25_once_and_passes_language(language: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}
    _install_fake_indextts25(monkeypatch, captured)
    output = io.StringIO()
    messages = [
        {
            "op": "init",
            "source_root": str(tmp_path),
            "cfg_path": str(tmp_path / "config.yaml"),
            "model_dir": str(tmp_path / "checkpoints"),
            "device": "cuda:1",
            "use_bf16": True,
            "use_qwen_emo": False,
        },
        {
            "op": "synthesize",
            "take_id": "take-1",
            "output_path": str(tmp_path / "one.wav"),
            "spk_audio_prompt": str(tmp_path / "speaker.wav"),
            "text": "hello",
            "language": language,
            "duration_factor": 1.25,
            "text_normalization": False,
            "emotion_mode": "same_voice",
        },
        {"op": "complete"},
    ]

    exit_code = run_session(io.StringIO("".join(json.dumps(item) + "\n" for item in messages)), output)

    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert exit_code == 0
    assert [event["event"] for event in events] == ["ready", "take_started", "take_succeeded", "complete"]
    assert len(captured["construct"]) == 1
    assert captured["construct"][0]["use_bf16"] is True
    assert captured["construct"][0]["use_qwen_emo"] is False
    infer = captured["infer"][0]
    assert infer["lang"] == language
    assert infer["duration_factor"] == 1.25
    assert infer["text_normalization"] is False
    assert "do_sample" not in infer


@pytest.mark.parametrize(
    ("emotion_mode", "specific", "expected"),
    [
        ("same_voice", {}, {"use_emo_text": False, "emo_audio_prompt": None, "emo_vector": None}),
        ("audio_prompt", {"emo_audio_prompt": "emotion.wav"}, {"emo_audio_prompt": "emotion.wav"}),
        ("vector", {"emo_vector": [0.1] * 8}, {"emo_vector": [0.1] * 8}),
        ("text_prompt", {"emo_text": "excited"}, {"use_emo_text": True, "emo_text": "excited"}),
    ],
)
def test_worker_supports_four_emotion_modes(
    emotion_mode: str,
    specific: dict[str, object],
    expected: dict[str, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}
    _install_fake_indextts25(monkeypatch, captured)
    output = io.StringIO()
    init = {
        "op": "init",
        "source_root": str(tmp_path),
        "cfg_path": "config.yaml",
        "model_dir": "checkpoints",
        "use_qwen_emo": emotion_mode == "text_prompt",
    }
    take = {
        "op": "synthesize",
        "take_id": "take-1",
        "output_path": str(tmp_path / "take.wav"),
        "spk_audio_prompt": "speaker.wav",
        "text": "hello",
        "language": "EN",
        "emotion_mode": emotion_mode,
        **specific,
    }

    run_session(io.StringIO(json.dumps(init) + "\n" + json.dumps(take) + "\n" + '{"op":"complete"}\n'), output)

    infer = captured["infer"][0]
    for key, value in expected.items():
        assert infer[key] == value


def test_worker_maps_text_emotion_oom_without_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}
    _install_fake_indextts25(monkeypatch, captured)
    output = io.StringIO()
    messages = [
        {"op": "init", "source_root": str(tmp_path), "cfg_path": "config.yaml", "model_dir": "checkpoints", "use_qwen_emo": True},
        {
            "op": "synthesize",
            "take_id": "take-1",
            "output_path": str(tmp_path / "take.wav"),
            "spk_audio_prompt": "speaker.wav",
            "text": "OOM",
            "language": "EN",
            "emotion_mode": "text_prompt",
            "emo_text": "worried",
        },
        {"op": "complete"},
    ]

    run_session(io.StringIO("".join(json.dumps(item) + "\n" for item in messages)), output)

    events = [json.loads(line) for line in output.getvalue().splitlines()]
    failed = next(event for event in events if event["event"] == "take_failed")
    assert failed["code"] == "text_emotion_memory_insufficient"
    assert len(captured["infer"]) == 1


def test_worker_emits_decoded_reference_and_runtime_warnings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    class WarningIndexTTS2:
        def __init__(self, **kwargs):
            pass

        def infer(self, **kwargs):
            import warnings

            warnings.warn("maximum mel token limit reached", RuntimeWarning)
            sf.write(kwargs["output_path"], np.zeros(10, dtype=np.float32), 24000)

    package = types.ModuleType("indextts")
    module = types.ModuleType("indextts.infer_v2_5")
    module.IndexTTS2 = WarningIndexTTS2
    monkeypatch.setitem(sys.modules, "indextts", package)
    monkeypatch.setitem(sys.modules, "indextts.infer_v2_5", module)
    speaker = tmp_path / "speaker.wav"
    sf.write(speaker, np.zeros(16 * 8000, dtype=np.float32), 8000)
    output = io.StringIO()
    init = {"op": "init", "source_root": str(tmp_path), "cfg_path": "config", "model_dir": "model"}
    take = {"op": "synthesize", "take_id": "one", "output_path": str(tmp_path / "out.wav"), "spk_audio_prompt": str(speaker), "text": "hello", "language": "EN"}

    run_session(io.StringIO(json.dumps(init) + "\n" + json.dumps(take) + "\n" + '{"op":"complete"}\n'), output)

    succeeded = next(json.loads(line) for line in output.getvalue().splitlines() if '"take_succeeded"' in line)
    assert succeeded["warnings"] == [
        {"code": "reference_audio_truncated", "message": "Speaker reference exceeds 15 seconds and may be truncated."},
        {"code": "max_mel_tokens_reached", "message": "maximum mel token limit reached"},
    ]


def test_worker_init_qwen_oom_has_text_emotion_error_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    class OomIndexTTS2:
        def __init__(self, **kwargs):
            raise RuntimeError("CUDA out of memory")

    package = types.ModuleType("indextts")
    module = types.ModuleType("indextts.infer_v2_5")
    module.IndexTTS2 = OomIndexTTS2
    monkeypatch.setitem(sys.modules, "indextts", package)
    monkeypatch.setitem(sys.modules, "indextts.infer_v2_5", module)
    output = io.StringIO()

    exit_code = run_session(
        io.StringIO(json.dumps({"op": "init", "source_root": str(tmp_path), "cfg_path": "config", "model_dir": "model", "use_qwen_emo": True}) + "\n"),
        output,
    )

    event = json.loads(output.getvalue())
    assert exit_code == 1
    assert event["event"] == "complete"
    assert event["code"] == "text_emotion_memory_insufficient"


def test_worker_eof_without_explicit_complete_is_protocol_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}
    _install_fake_indextts25(monkeypatch, captured)
    output = io.StringIO()
    messages = [
        {"op": "init", "source_root": str(tmp_path), "cfg_path": "config", "model_dir": "model"},
        {"op": "synthesize", "take_id": "one", "output_path": str(tmp_path / "out.wav"), "spk_audio_prompt": "speaker.wav", "text": "hello", "language": "EN"},
    ]

    exit_code = run_session(io.StringIO("".join(json.dumps(item) + "\n" for item in messages)), output)

    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert exit_code == 1
    assert events[-1]["event"] == "complete"
    assert events[-1]["code"] == "worker_eof"


def test_service_and_worker_forward_only_validated_expert_generation_parameters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}
    _install_fake_indextts25(monkeypatch, captured)
    service = IndexTTS2Service(AppPaths.from_project_root(tmp_path), runner=object(), coordinator=RuntimeCoordinator())
    payload = {
        "language": "ES",
        "emotion_mode": "same_voice",
        "top_p": 0.65,
        "top_k": 42,
        "temperature": 1.1,
        "length_penalty": -1.5,
        "num_beams": 4,
        "repetition_penalty": 7.5,
        "max_mel_tokens": 2100,
        "do_sample": False,
    }
    request = service._build_worker_payload(payload, text="hola", speaker_audio_path="speaker.wav")
    expert = {key: request[key] for key in ("top_p", "top_k", "temperature", "length_penalty", "num_beams", "repetition_penalty", "max_mel_tokens")}
    output = io.StringIO()
    init = {"op": "init", "source_root": str(tmp_path), "cfg_path": "config", "model_dir": "model"}
    take = {"op": "synthesize", "take_id": "one", "output_path": str(tmp_path / "out.wav"), **request}

    run_session(io.StringIO(json.dumps(init) + "\n" + json.dumps(take) + "\n" + '{"op":"complete"}\n'), output)

    infer = captured["infer"][0]
    assert {key: infer[key] for key in expert} == expert
    assert "do_sample" not in request
    assert "do_sample" not in infer


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("top_p", 1.01),
        ("top_k", 201),
        ("temperature", 0.09),
        ("length_penalty", -5.1),
        ("num_beams", 21),
        ("repetition_penalty", 50.1),
        ("max_mel_tokens", 5001),
    ],
)
def test_service_rejects_out_of_range_expert_generation_parameters(field: str, value: object, tmp_path: Path):
    service = IndexTTS2Service(AppPaths.from_project_root(tmp_path), runner=object(), coordinator=RuntimeCoordinator())
    with pytest.raises(ValueError, match=field):
        service._build_worker_payload(
            {"language": "EN", "emotion_mode": "same_voice", field: value},
            text="hello",
            speaker_audio_path="speaker.wav",
        )


def test_schema_v5_adds_nullable_identity_and_decoded_warnings(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    paths.ensure()
    legacy = sqlite3.connect(paths.db_path)
    legacy.executescript(
        """
        create table schema_version(version integer primary key, applied_at text not null);
        create table generations(id text primary key, input_text text not null, control_instruction text not null default '', voice_id text, reference_audio_path text, prompt_text text not null default '', cfg_value real not null, inference_timesteps integer not null, normalize integer not null, denoise integer not null, source_backend text not null default 'voxcpm2', source_mode text not null default 'legacy', description text not null default '', is_favorite integer not null default 0, output_audio_path text, sample_rate integer, status text not null, error_summary text not null default '', saved_voice_id text, promoted_to_voice_at text, hidden_from_history_at text, created_at text not null, updated_at text not null, deleted_at text);
        """
    )
    legacy.close()

    conn = initialize_database(paths)
    try:
        assert conn.execute("select max(version) from schema_version").fetchone()[0] == 5
        generation_columns = {row["name"] for row in conn.execute("pragma table_info(generations)")}
        take_columns = {row["name"] for row in conn.execute("pragma table_info(generation_takes)")}
        assert {"model_id", "model_version", "upstream_commit"} <= generation_columns
        assert {"model_id", "model_version", "upstream_commit", "warnings_json"} <= take_columns
    finally:
        conn.close()

    job = create_generation_job(
        paths,
        backend_id="indextts2",
        model_id="IndexTTS-2.5",
        model_version="2.5",
        upstream_commit="abc123",
        mode="line_performance",
        input_text="hello",
        params={"language": "EN"},
    )
    take = create_generation_take(
        paths,
        job_id=job.id,
        backend_id="indextts2",
        take_index=1,
        model_id=job.model_id,
        model_version=job.model_version,
        upstream_commit=job.upstream_commit,
        warnings=[{"code": "notice", "message": "stable"}],
    )
    payload = generation_take_to_dict(paths, take)
    assert payload["warnings"] == [{"code": "notice", "message": "stable"}]
    assert payload["model_id"] == "IndexTTS-2.5"


def test_selected_take_projects_identity_and_warnings_to_history(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    output = tmp_path / "take.wav"
    sf.write(output, np.zeros(20, dtype=np.float32), 24000)
    job = create_generation_job(
        paths,
        backend_id="indextts2",
        model_id="IndexTTS-2.5",
        model_version="2.5",
        upstream_commit="abc123",
        mode="line_performance",
        input_text="hello",
        params={"language": "EN"},
    )
    from voxcpm_app.job_store import create_asset

    asset = create_asset(paths, kind="take_output", path=output, sample_rate=24000)
    take = create_generation_take(
        paths,
        job_id=job.id,
        backend_id="indextts2",
        take_index=1,
        model_id=job.model_id,
        model_version=job.model_version,
        upstream_commit=job.upstream_commit,
        warnings=[{"code": "notice", "message": "stable"}],
    )
    update_generation_take(paths, take.id, status="succeeded", output_asset_id=asset.id)

    selected = select_take_and_project(paths, take.id)
    projected = create_generation  # keep import exercised before repository lookup
    assert projected is not None
    from voxcpm_app.generation_history import list_generations

    history = next(item for item in list_generations(paths) if item.id == selected.legacy_generation_id)
    assert history.model_id == "IndexTTS-2.5"
    assert history.model_version == "2.5"
    assert history.upstream_commit == "abc123"
    assert history.warnings == [{"code": "notice", "message": "stable"}]


def test_sync_history_warning_update_merges_and_deduplicates(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    generation = create_generation(
        paths,
        input_text="hello",
        control_instruction="",
        voice_id=None,
        reference_audio_path=None,
        prompt_text="",
        cfg_value=1,
        inference_timesteps=120,
        normalize=False,
        denoise=False,
        warnings=[{"code": "profile_warning", "message": "profile"}],
    )

    updated = update_generation_warnings(
        paths,
        generation.id,
        [
            {"code": "runtime_warning", "message": "runtime"},
            {"code": "runtime_warning", "message": "runtime"},
        ],
    )

    assert updated.warnings == [
        {"code": "profile_warning", "message": "profile"},
        {"code": "runtime_warning", "message": "runtime"},
    ]


def test_runtime_status_exposes_identity_capabilities_and_paths_at_top_level(tmp_path: Path):
    class FakeRunner:
        def status(self, paths, *, coordinator):
            return RuntimeBackendStatus(
                backend_id="indextts2",
                display_name="IndexTTS2",
                enabled=True,
                configured=True,
                loaded=False,
                busy=False,
                device="cuda",
                last_error="",
                capabilities=["line_performance", "emotion_text"],
                details={"missing_text_emotion_assets": []},
            )

    status = IndexTTS2Service(AppPaths.from_project_root(tmp_path), runner=FakeRunner(), coordinator=RuntimeCoordinator()).runtime_status()
    assert status.model_id == "IndexTTS-2.5"
    assert status.model_version == "2.5"
    assert status.supported_languages == ["ZH", "EN", "JA", "ES", "AR"]
    assert status.effective_precision in {"fp32", "bf16"}
    assert isinstance(status.text_emotion_enabled, bool)
    assert isinstance(status.warnings, list)
    assert all(set(warning) == {"code", "message"} for warning in status.warnings)
    assert isinstance(status.paths, dict)


def test_new_indextts_job_requires_language_and_uses_25_identity(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    with pytest.raises(ValueError, match="language is required"):
        create_generation_job(
            paths,
            backend_id="indextts2",
            model_id="IndexTTS-2.5",
            mode="line_performance",
            input_text="hello",
            params={},
        )

    job = create_generation_job(
        paths,
        backend_id="indextts2",
        model_id="anything",
        mode="line_performance",
        input_text="hello",
        params={"language": "JA"},
    )
    persisted = get_generation_job(paths, job.id)
    assert persisted is not None
    assert persisted.model_id == "IndexTTS-2.5"
    assert persisted.model_version == "2.5"


def test_parent_session_observes_events_and_reports_partial_failure(tmp_path: Path):
    class FakeProcess:
        def __init__(self):
            self.stdin = self
            self.stdout = self
            self.stderr = io.StringIO("upstream diagnostics\n")
            self.responses: list[str] = []
            self.returncode = None

        def write(self, value: str):
            message = json.loads(value)
            if message["op"] == "init":
                self.responses.append('{"event":"ready"}\n')
            elif message["op"] == "synthesize":
                take_id = message["take_id"]
                self.responses.append(json.dumps({"event": "take_started", "take_id": take_id}) + "\n")
                if take_id == "bad":
                    self.responses.append(json.dumps({"event": "take_failed", "take_id": take_id, "code": "worker_failed", "error": "boom", "details": {}}) + "\n")
                else:
                    sf.write(message["output_path"], np.zeros(10, dtype=np.float32), 24000)
                    self.responses.append(json.dumps({"event": "take_succeeded", "take_id": take_id, "sample_rate": 24000, "output_path": message["output_path"]}) + "\n")
            elif message["op"] == "complete":
                self.responses.append('{"event":"complete"}\n')
                self.returncode = 0
            return len(value)

        def flush(self):
            return None

        def readline(self):
            for _ in range(1000):
                if self.responses:
                    return self.responses.pop(0)
                if self.returncode is not None:
                    return ""
                threading.Event().wait(0.001)
            return ""

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode or 0

        def terminate(self):
            self.returncode = -15

        def kill(self):
            self.returncode = -9

    process = FakeProcess()
    session = SubprocessIndexTTS2Session(process, timeout_seconds=1, cancel_event=threading.Event())
    session.initialize({"source_root": str(tmp_path), "cfg_path": "config", "model_dir": "model"})
    good = tmp_path / "good.wav"
    assert session.synthesize({"text": "ok", "spk_audio_prompt": "speaker", "language": "EN"}, good, take_id="good") == 24000
    with pytest.raises(Exception) as raised:
        session.synthesize({"text": "bad", "spk_audio_prompt": "speaker", "language": "EN"}, tmp_path / "bad.wav", take_id="bad")
    session.close()

    assert getattr(raised.value, "code", None) == "worker_failed"
    assert [event["event"] for event in session.events] == [
        "ready",
        "take_started",
        "take_succeeded",
        "take_started",
        "take_failed",
        "complete",
    ]


def test_job_queue_uses_one_session_for_multiple_takes_and_keeps_partial_success(tmp_path: Path):
    class FakeGenerationService:
        pass

    class FakeSession:
        def __init__(self):
            self.calls = []
            self.last_warnings = []

        def synthesize(self, payload, output_path, *, take_id):
            self.calls.append(take_id)
            if len(self.calls) == 2:
                raise RuntimeError("second take failed")
            self.last_warnings = [{"code": "runtime_warning", "message": f"warning for {take_id}"}]
            sf.write(output_path, np.zeros(10, dtype=np.float32), 24000)
            return 24000

        def terminate(self):
            pass

    class FakeIndexService:
        def __init__(self):
            self.opens = 0
            self.session = FakeSession()

        @contextlib.contextmanager
        def open_job_session(self, payload, *, job_id, cancel_event):
            self.opens += 1
            yield self.session

        def synthesize_take(self, session, payload, *, take_id):
            output = tmp_path / f"{take_id}.wav"
            return output, session.synthesize(payload, output, take_id=take_id)

    service = FakeIndexService()
    queue = GenerationJobQueue(AppPaths.from_project_root(tmp_path), FakeGenerationService(), service)
    job = queue.submit(
        {
            "backend_id": "indextts2",
            "input_text": "hello",
            "warnings": [
                {"code": "legacy_language_defaulted", "message": "Legacy retry defaulted language to ZH."},
                {"code": "runtime_warning", "message": "duplicate"},
            ],
            "params": {
                "language": "EN",
                "take_count": 3,
                "speaker": {"kind": "upload", "path": str(tmp_path / "speaker.wav")},
            },
        }
    )
    queue._queue.join()

    persisted = get_generation_job(AppPaths.from_project_root(tmp_path), job.id)
    takes = __import__("voxcpm_app.job_store", fromlist=["list_generation_takes"]).list_generation_takes(AppPaths.from_project_root(tmp_path), job.id)
    assert service.opens == 1
    assert service.session.calls == [take.id for take in takes]
    assert [take.status for take in takes].count("failed") == 1
    assert generation_take_to_dict(AppPaths.from_project_root(tmp_path), takes[0])["warnings"] == [
        {"code": "legacy_language_defaulted", "message": "Legacy retry defaulted language to ZH."},
        {"code": "runtime_warning", "message": "duplicate"},
        {"code": "runtime_warning", "message": f"warning for {takes[0].id}"},
    ]
    assert persisted is not None and persisted.status == "succeeded"


def test_running_cancel_terminates_session_and_preserves_completed_take(tmp_path: Path):
    entered_second = threading.Event()
    release_second = threading.Event()

    class FakeGenerationService:
        pass

    class BlockingSession:
        def __init__(self):
            self.calls = 0

        def terminate(self):
            release_second.set()

    class BlockingIndexService:
        def __init__(self):
            self.session = BlockingSession()

        @contextlib.contextmanager
        def open_job_session(self, payload, *, job_id, cancel_event):
            yield self.session

        def synthesize_take(self, session, payload, *, take_id):
            session.calls += 1
            output = tmp_path / f"{take_id}.wav"
            if session.calls == 2:
                entered_second.set()
                release_second.wait(timeout=2)
                raise RuntimeError("terminated")
            sf.write(output, np.zeros(10, dtype=np.float32), 24000)
            return output, 24000

    paths = AppPaths.from_project_root(tmp_path)
    queue = GenerationJobQueue(paths, FakeGenerationService(), BlockingIndexService())
    job = queue.submit(
        {
            "backend_id": "indextts2",
            "input_text": "hello",
            "params": {"language": "EN", "take_count": 3, "speaker": {"kind": "upload", "path": "speaker.wav"}},
        }
    )
    assert entered_second.wait(timeout=2)
    cancelled = queue.cancel(job.id)
    queue._queue.join()

    takes = __import__("voxcpm_app.job_store", fromlist=["list_generation_takes"]).list_generation_takes(paths, job.id)
    assert cancelled.status == "cancelled"
    assert get_generation_job(paths, job.id).status == "cancelled"
    assert [take.status for take in takes] == ["succeeded", "cancelled", "cancelled"]
    assert queue.indextts2_service.session.calls == 2
    assert queue.indextts2_service is not None


def test_legacy_retry_defaults_only_new_job_language_and_warning(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    original = create_generation_job(
        paths,
        backend_id="voxcpm2",
        model_id="legacy",
        mode="line_performance",
        input_text="hello",
        params={},
    )
    conn = initialize_database(paths)
    try:
        conn.execute(
            "update generation_jobs set backend_id = 'indextts2', model_id = 'IndexTTS2', model_version = null where id = ?",
            (original.id,),
        )
        conn.commit()
    finally:
        conn.close()

    queue = object.__new__(GenerationJobQueue)
    queue.paths = paths
    captured: dict[str, object] = {}

    def capture_submit(payload):
        captured.update(payload)
        return payload

    queue.submit = capture_submit
    queue.retry(original.id)

    assert captured["params"]["language"] == "ZH"
    assert captured["warnings"] == [
        {"code": "legacy_language_defaulted", "message": "Legacy retry defaulted language to ZH."}
    ]
    unchanged = get_generation_job(paths, original.id)
    assert unchanged is not None
    assert json.loads(unchanged.params_json) == {}
    assert unchanged.warnings == []


def test_queue_rejects_missing_or_invalid_language_before_persisting_and_forces_model_identity(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    queue = GenerationJobQueue(paths, object(), object())

    with pytest.raises(ValueError, match="language is required"):
        queue.submit({"backend_id": "indextts2", "input_text": "hello", "params": {}})
    with pytest.raises(ValueError, match="language must be one of"):
        queue.submit({"backend_id": "indextts2", "input_text": "hello", "params": {"language": "FR"}})

    conn = initialize_database(paths)
    try:
        assert conn.execute("select count(*) from generation_jobs").fetchone()[0] == 0
    finally:
        conn.close()

    job = queue.submit(
        {
            "backend_id": "indextts2",
            "model_id": "IndexTTS2",
            "input_text": "hello",
            "params": {"language": "AR", "take_count": 1},
        }
    )
    assert job.model_id == "IndexTTS-2.5"
    assert job.model_version == "2.5"


@pytest.mark.parametrize("iteration", range(10))
def test_cancel_racing_take_finalization_has_consistent_terminal_result(iteration: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import voxcpm_app.job_queue as job_queue_module

    entered = threading.Event()
    release = threading.Event()
    original_create_asset = job_queue_module.create_asset

    def blocked_create_asset(*args, **kwargs):
        entered.set()
        assert release.wait(timeout=2)
        return original_create_asset(*args, **kwargs)

    monkeypatch.setattr(job_queue_module, "create_asset", blocked_create_asset)
    root = tmp_path / str(iteration)
    root.mkdir()
    paths = AppPaths.from_project_root(root)
    queue = GenerationJobQueue(paths, object(), _SuccessfulIndexService(root))
    job = queue.submit({"backend_id": "indextts2", "input_text": "hello", "params": {"language": "EN", "take_count": 1}})
    assert entered.wait(timeout=2)
    result: dict[str, object] = {}
    cancel_thread = threading.Thread(target=lambda: result.setdefault("job", queue.cancel(job.id)))
    cancel_thread.start()
    threading.Event().wait(0.05)
    release.set()
    cancel_thread.join(timeout=2)
    queue._queue.join()

    persisted = get_generation_job(paths, job.id)
    assert persisted is not None
    assert result["job"].status == persisted.status == "succeeded"


def test_cancel_racing_auto_select_cannot_report_cancelled_then_project_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import voxcpm_app.job_queue as job_queue_module

    entered = threading.Event()
    release = threading.Event()
    original_select = job_queue_module.select_take_and_project

    def blocked_select(*args, **kwargs):
        entered.set()
        assert release.wait(timeout=2)
        return original_select(*args, **kwargs)

    monkeypatch.setattr(job_queue_module, "select_take_and_project", blocked_select)
    paths = AppPaths.from_project_root(tmp_path)
    queue = GenerationJobQueue(paths, object(), _SuccessfulIndexService(tmp_path))
    job = queue.submit({"backend_id": "indextts2", "input_text": "hello", "params": {"language": "EN", "take_count": 1}})
    assert entered.wait(timeout=2)
    result: dict[str, object] = {}
    cancel_thread = threading.Thread(target=lambda: result.setdefault("job", queue.cancel(job.id)))
    cancel_thread.start()
    threading.Event().wait(0.05)
    release.set()
    cancel_thread.join(timeout=2)
    queue._queue.join()

    persisted = get_generation_job(paths, job.id)
    assert persisted is not None
    assert result["job"].status == persisted.status == "succeeded"
    assert any(item.id == persisted.legacy_generation_id for item in list_generations(paths))


def test_text_emotion_request_rejects_missing_qwen_assets_with_structured_code(tmp_path: Path):
    class FakeRunner:
        opened = False

        def status(self, paths, *, coordinator):
            return RuntimeBackendStatus(
                backend_id="indextts2",
                display_name="IndexTTS2",
                enabled=True,
                configured=True,
                loaded=False,
                busy=False,
                device="cuda",
                last_error="",
                capabilities=["emotion_text"],
                details={"missing_text_emotion_assets": ["QwenEmotion"]},
            )

        @contextlib.contextmanager
        def open_session(self, paths, payload, *, cancel_event=None):
            self.opened = True
            yield types.SimpleNamespace()

    speaker = tmp_path / "speaker.wav"
    speaker.write_bytes(b"speaker")
    service = IndexTTS2Service(AppPaths.from_project_root(tmp_path), runner=FakeRunner(), coordinator=RuntimeCoordinator())

    with pytest.raises(Exception) as raised:
        service.generate(
            {
                "text": "hello",
                "language": "EN",
                "speaker": {"kind": "upload", "path": str(speaker)},
                "emotion_mode": "text_prompt",
            }
        )

    assert getattr(raised.value, "code", None) == "text_emotion_unavailable"
    with pytest.raises(Exception) as session_error:
        with service.open_job_session(
            {"emotion_mode": "text_prompt"},
            job_id="job",
            cancel_event=threading.Event(),
        ):
            pass
    assert getattr(session_error.value, "code", None) == "text_emotion_unavailable"
    assert service.runner.opened is False


class _SuccessfulIndexService:
    def __init__(self, root: Path):
        self.root = root

    @contextlib.contextmanager
    def open_job_session(self, payload, *, job_id, cancel_event):
        yield types.SimpleNamespace(last_warnings=[], terminate=lambda: None)

    def synthesize_take(self, session, payload, *, take_id):
        output = self.root / f"{take_id}.wav"
        sf.write(output, np.zeros(10, dtype=np.float32), 24000)
        return output, 24000
