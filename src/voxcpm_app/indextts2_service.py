from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

import soundfile as sf

from .audio_assets import copy_tmp_audio
from .db import initialize_database
from .errors import AppBackendError
from .generation_history import (
    create_generation,
    mark_generation_failed,
    mark_generation_running,
    mark_generation_succeeded,
)
from .paths import AppPaths
from .indextts2_runtime_profile import IndexTTS2RuntimeProfileStore, RuntimeProfileResolution, SUPPORTED_LANGUAGES, UPSTREAM_COMMIT
from .repositories import VoiceRepository
from .runtime import RUNTIME_COORDINATOR, RuntimeBackendStatus, RuntimeCoordinator
from .schemas import GenerationRecord
from .voice_library import mark_voice_used


EMOTION_VECTOR_FIELDS = ["happy", "angry", "sad", "afraid", "disgusted", "melancholic", "surprised", "calm"]
REQUIRED_CHECKPOINT_FILES = [
    "config.yaml",
    "gpt.pth",
    "s2mel.pth",
    "codec.pth",
    "multilingual_zh_ja_yue_char_del.tiktoken",
    "wav2vec2bert_stats.pt",
]


@dataclass(frozen=True)
class ResolvedAudio:
    voice_id: str | None
    relative_path: str | None
    absolute_path: str


class IndexTTS2Runner(Protocol):
    def status(self, paths: AppPaths, *, coordinator: RuntimeCoordinator) -> RuntimeBackendStatus:
        ...

    def synthesize(self, paths: AppPaths, payload: dict[str, Any], output_path: Path) -> int:
        ...


class SubprocessIndexTTS2Session:
    def __init__(
        self,
        process: subprocess.Popen[str],
        *,
        timeout_seconds: float,
        cancel_event: threading.Event | None = None,
    ):
        self.process = process
        self.timeout_seconds = timeout_seconds
        self.cancel_event = cancel_event or threading.Event()
        self.events: list[dict[str, Any]] = []
        self.stderr_lines: list[str] = []
        self.last_warnings: list[dict[str, str]] = []
        self._events: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._closed = False
        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def initialize(self, payload: dict[str, Any]) -> None:
        self._send({"op": "init", **payload})
        event = self._next_event()
        if event.get("event") != "ready":
            self._raise_event_error(event, default_code="worker_failed")

    def synthesize(self, payload: dict[str, Any], output_path: Path, *, take_id: str) -> int:
        self._send({"op": "synthesize", "take_id": take_id, **payload, "output_path": str(output_path)})
        started = self._next_event()
        if started.get("event") != "take_started" or started.get("take_id") != take_id:
            self._raise_event_error(started, default_code="worker_protocol_error")
        result = self._next_event()
        if result.get("event") == "take_failed":
            self._raise_event_error(result, default_code="worker_failed")
        if result.get("event") != "take_succeeded" or result.get("take_id") != take_id:
            self._raise_event_error(result, default_code="worker_protocol_error")
        self.last_warnings = _stable_warnings(result.get("warnings") if isinstance(result.get("warnings"), list) else [])
        if not output_path.is_file():
            raise AppBackendError(f"IndexTTS2 generated output is missing: {output_path}", code="output_missing")
        return int(result.get("sample_rate") or sf.info(str(output_path)).samplerate)

    def terminate(self) -> None:
        self.cancel_event.set()
        if self.process.poll() is None:
            self.process.terminate()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.process.poll() is None and not self.cancel_event.is_set():
            try:
                self._send({"op": "complete"})
                event = self._next_event(ignore_cancel=True)
                if event.get("event") != "complete":
                    self._raise_event_error(event, default_code="worker_protocol_error")
            except Exception:
                self.terminate()
                raise
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)

    def _send(self, payload: dict[str, Any]) -> None:
        if self.process.stdin is None:
            raise AppBackendError("IndexTTS2 worker stdin is unavailable", code="worker_eof")
        try:
            self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise AppBackendError("IndexTTS2 worker closed its input", code="worker_eof") from exc

    def _next_event(self, *, ignore_cancel: bool = False) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            if self.cancel_event.is_set() and not ignore_cancel:
                if self.process.poll() is None:
                    self.process.terminate()
                raise AppBackendError("IndexTTS2 generation cancelled", code="cancelled")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if self.process.poll() is None:
                    self.process.terminate()
                raise AppBackendError(
                    f"IndexTTS2 worker timed out after {self.timeout_seconds}s",
                    code="timeout",
                )
            try:
                event = self._events.get(timeout=min(0.1, remaining))
            except queue.Empty:
                continue
            if event is None:
                stderr = "".join(self.stderr_lines).strip()
                raise AppBackendError(stderr or "IndexTTS2 worker ended unexpectedly", code="worker_eof")
            self.events.append(event)
            return event

    def _read_stdout(self) -> None:
        if self.process.stdout is None:
            self._events.put(None)
            return
        for line in iter(self.process.stdout.readline, ""):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                event = {"event": "complete", "code": "worker_protocol_error", "error": "invalid worker JSON", "details": {}}
            self._events.put(event)
        self._events.put(None)

    def _drain_stderr(self) -> None:
        if self.process.stderr is None:
            return
        for line in iter(self.process.stderr.readline, ""):
            self.stderr_lines.append(line)

    @staticmethod
    def _raise_event_error(event: dict[str, Any], *, default_code: str) -> None:
        raise AppBackendError(
            str(event.get("error") or f"unexpected worker event: {event.get('event')}"),
            code=str(event.get("code") or default_code),
            details=event.get("details") if isinstance(event.get("details"), dict) else {},
        )


class SubprocessIndexTTS2Runner:
    def status(self, paths: AppPaths, *, coordinator: RuntimeCoordinator) -> RuntimeBackendStatus:
        source_root = _source_root(paths)
        runtime_python = _runtime_python(paths)
        model_dir = _model_dir(paths)
        missing: list[str] = []
        details: dict[str, object] = {
            "source_root": str(source_root),
            "runtime_python": str(runtime_python),
            "runtime_root": str(_runtime_root(paths)),
            "model_dir": str(model_dir),
            "cfg_path": str(_cfg_path(paths)),
            "missing_source": [],
            "missing_runtime": [],
            "missing_config": [],
            "missing_checkpoints": [],
            "outside_project_paths": [],
            "code": "",
        }
        outside_project_paths = [
            str(path)
            for path in [runtime_python, model_dir, _cfg_path(paths)]
            if not _is_project_local(paths, path)
        ]
        if outside_project_paths:
            details["outside_project_paths"] = outside_project_paths
            missing.extend(f"path outside project: {path}" for path in outside_project_paths)
        source_family = _source_model_family(paths)
        checkpoint_family = _checkpoint_model_family(model_dir)
        details["source_model_family"] = source_family
        details["checkpoint_model_family"] = checkpoint_family
        mismatch = source_family is not None and checkpoint_family is not None and source_family != checkpoint_family
        if not source_root.exists() or source_family != "2.5":
            missing.append("third_party/index-tts/indextts/infer_v2_5.py")
            details["missing_source"] = [str(source_root)]
        if not runtime_python.exists():
            missing.append(str(runtime_python))
            details["missing_runtime"] = [str(runtime_python)]
        cfg_path = _cfg_path(paths)
        if not cfg_path.exists():
            missing.append(str(cfg_path))
            details["missing_config"] = [str(cfg_path)]
        if not model_dir.exists():
            missing.append(str(model_dir))
            details["missing_checkpoints"] = [str(model_dir)]
        else:
            missing_checkpoints = [
                str(model_dir / name)
                for name in REQUIRED_CHECKPOINT_FILES if not (model_dir / name).exists()
            ]
            missing.extend(missing_checkpoints)
            details["missing_checkpoints"] = missing_checkpoints
        optional_assets = _text_emotion_readiness(paths)
        details.update(optional_assets)
        last_error = coordinator.last_error("indextts2") or "; ".join(missing)
        state = coordinator.status("indextts2")
        status_state = "busy" if state["runtime_busy"] else "configured"
        if mismatch:
            status_state = "model_version_mismatch"
            details["code"] = "model_version_mismatch"
            details["model_version_mismatch"] = True
        elif missing:
            status_state = "missing_runtime" if details["missing_runtime"] or details["outside_project_paths"] else "missing_checkpoints"
            details["code"] = "runtime_missing" if status_state == "missing_runtime" else "checkpoints_missing"
        if details["missing_source"]:
            if not mismatch:
                status_state = "missing_runtime"
                details["code"] = "runtime_missing"
        details["runtime_busy"] = bool(state["runtime_busy"])
        details["active_backend"] = state["active_backend"]
        return RuntimeBackendStatus(
            backend_id="indextts2",
            display_name="IndexTTS2",
            enabled=True,
            configured=not missing,
            loaded=False,
            busy=bool(state["runtime_busy"]),
            device=os.environ.get("INDEXTTS2_DEVICE", os.environ.get("VOXCPM_APP_DEVICE", "cuda")),
            last_error=last_error,
            capabilities=[
                "line_performance",
                "speaker_reference",
                "emotion_audio",
                "emotion_vector",
                "multi_take",
            ] + (["emotion_text"] if not optional_assets["missing_text_emotion_assets"] else []),
            active_job_id=state["active_job_id"] if isinstance(state["active_job_id"], str) else None,
            started_at=state["started_at"] if isinstance(state["started_at"], str) else None,
            state=status_state,
            details=details,
        )

    def synthesize(self, paths: AppPaths, payload: dict[str, Any], output_path: Path) -> int:
        with self.open_session(paths, payload) as session:
            return session.synthesize(payload, output_path, take_id=str(payload.get("take_id") or "single"))

    @contextmanager
    def open_session(
        self,
        paths: AppPaths,
        payload: dict[str, Any],
        *,
        cancel_event: threading.Event | None = None,
    ):
        source_root = _source_root(paths)
        runtime_python = _runtime_python(paths)
        model_dir = _model_dir(paths)
        cfg_path = _cfg_path(paths)
        outside_project_paths = [
            str(path)
            for path in [runtime_python, model_dir, cfg_path]
            if not _is_project_local(paths, path)
        ]
        mismatch = _asset_version_mismatch(paths)
        if mismatch:
            raise AppBackendError("IndexTTS-2.5 source and checkpoint families do not match", code="model_version_mismatch", details=mismatch)
        if outside_project_paths:
            raise RuntimeError(f"IndexTTS2 runtime paths must stay inside project: {', '.join(outside_project_paths)}")
        if not source_root.exists():
            raise RuntimeError("IndexTTS2 source snapshot is missing: third_party/index-tts")
        if not runtime_python.exists():
            raise RuntimeError(f"IndexTTS2 runtime python is not configured: {runtime_python}")
        missing_checkpoints = _missing_checkpoint_files(paths)
        if missing_checkpoints:
            raise RuntimeError(f"IndexTTS2 checkpoints are missing: {', '.join(missing_checkpoints)}")

        init_payload = {
            "source_root": str(source_root),
            "model_dir": str(model_dir),
            "cfg_path": str(cfg_path),
            "device": os.environ.get("INDEXTTS2_DEVICE", os.environ.get("VOXCPM_APP_DEVICE", "cuda")),
            "use_bf16": bool(payload.get("use_bf16", False)),
            "use_qwen_emo": bool(payload.get("use_qwen_emo", False)),
            "use_cuda_kernel": bool(payload.get("use_cuda_kernel", False)),
            "use_deepspeed": bool(payload.get("use_deepspeed", False)),
            "use_accel": bool(payload.get("use_accel", False)),
            "use_torch_compile": bool(payload.get("use_torch_compile", False)),
        }
        src_root = paths.project_root / "src"
        python_path_parts = [str(src_root), str(source_root)]
        if os.environ.get("PYTHONPATH"):
            python_path_parts.append(os.environ["PYTHONPATH"])
        env = {
            **os.environ,
            **_runtime_cache_env(paths),
            "PYTHONPATH": os.pathsep.join(python_path_parts),
        }
        process = subprocess.Popen(
            [str(runtime_python), "-m", "voxcpm_app.indextts2_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(paths.project_root),
            env=env,
        )
        session = SubprocessIndexTTS2Session(
            process,
            timeout_seconds=_worker_timeout_seconds(),
            cancel_event=cancel_event,
        )
        try:
            session.initialize(init_payload)
            yield session
        finally:
            session.close()


class IndexTTS2Service:
    def __init__(
        self,
        paths: AppPaths,
        *,
        runner: IndexTTS2Runner | None = None,
        coordinator: RuntimeCoordinator = RUNTIME_COORDINATOR,
    ):
        self.paths = paths
        self.runner = runner or SubprocessIndexTTS2Runner()
        self.coordinator = coordinator
        self.runtime_profiles = IndexTTS2RuntimeProfileStore(paths)

    def runtime_status(self) -> RuntimeBackendStatus:
        status = self.runner.status(self.paths, coordinator=self.coordinator)
        profile = self.runtime_profile()
        details = dict(status.details or {})
        text_emotion_available = profile.profile.allow_text_emotion and not bool(details.get("missing_text_emotion_assets"))
        capabilities = [capability for capability in status.capabilities if capability != "emotion_text"]
        if text_emotion_available:
            capabilities.append("emotion_text")
        details.update({
            "model_id": "IndexTTS-2.5",
            "model_version": "2.5",
            "upstream_commit": UPSTREAM_COMMIT,
            "supported_languages": SUPPORTED_LANGUAGES,
            "precision": profile.profile.precision,
            "effective_precision": profile.effective_precision,
            "text_emotion_enabled": text_emotion_available,
            "runtime_profile_path": str(self.paths.indextts2_runtime_profile_path),
            "warnings": _stable_warnings(profile.warnings),
            "capability": profile.capability,
        })
        return replace(
            status,
            capabilities=capabilities,
            details=details,
            model_id="IndexTTS-2.5",
            model_version="2.5",
            upstream_commit=UPSTREAM_COMMIT,
            supported_languages=list(SUPPORTED_LANGUAGES),
            effective_precision=profile.effective_precision,
            text_emotion_enabled=text_emotion_available,
            warnings=_stable_warnings(profile.warnings),
            paths={
                "source_root": str(_source_root(self.paths)),
                "runtime_root": str(_runtime_root(self.paths)),
                "model_dir": str(_model_dir(self.paths)),
                "config": str(_cfg_path(self.paths)),
                "runtime_profile": str(self.paths.indextts2_runtime_profile_path),
            },
        )

    def runtime_profile(self) -> RuntimeProfileResolution:
        return self.runtime_profiles.load()

    def save_runtime_profile(self, payload: object) -> RuntimeProfileResolution:
        return self.runtime_profiles.save(payload)

    def generate(self, payload: dict[str, Any]) -> GenerationRecord:
        text = str(payload.get("text") or payload.get("input_text") or "").strip()
        if not text:
            raise ValueError("text is required")
        speaker = self._resolve_speaker(payload.get("speaker"))
        request = self._build_worker_payload(payload, text=text, speaker_audio_path=speaker.absolute_path)
        generation = create_generation(
            self.paths,
            input_text=text,
            control_instruction=json.dumps(
                {
                    "engine": "indextts2",
                    "emotion_mode": request["emotion_mode"],
                    "params": _history_params(request),
                },
                ensure_ascii=False,
            ),
            voice_id=speaker.voice_id,
            reference_audio_path=speaker.relative_path,
            prompt_text=str(request.get("emo_text") or ""),
            cfg_value=float(request.get("emo_alpha", 1.0)),
            inference_timesteps=int(request.get("max_text_tokens_per_segment", 120)),
            normalize=False,
            denoise=False,
            source_backend="indextts2",
            source_mode="indextts2-performance",
            description=str(request.get("emotion_mode") or "IndexTTS2 performance"),
            model_id="IndexTTS-2.5",
            model_version="2.5",
            upstream_commit=UPSTREAM_COMMIT,
            warnings=_stable_warnings(self.runtime_profile().warnings),
        )
        mark_generation_running(self.paths, generation.id)
        output_path = self.paths.tmp_dir / f"{generation.id}-indextts2.wav"

        try:
            active_job_id = str(payload.get("generation_job_id") or generation.id)
            with self.open_job_session(request, job_id=active_job_id) as session:
                sample_rate = session.synthesize(request, output_path, take_id=generation.id)
            succeeded = mark_generation_succeeded(
                self.paths,
                generation.id,
                source_output_audio_path=output_path,
                sample_rate=sample_rate,
            )
            session_warnings = getattr(session, "last_warnings", [])
            if session_warnings:
                from .generation_history import update_generation_warnings

                succeeded = update_generation_warnings(self.paths, generation.id, session_warnings)
            if speaker.voice_id:
                mark_voice_used(self.paths, speaker.voice_id)
            return succeeded
        except Exception as exc:
            return mark_generation_failed(self.paths, generation.id, error_summary=_error_summary(exc))

    def generate_take(self, payload: dict[str, Any], *, take_id: str) -> tuple[Path, int]:
        active_job_id = str(payload.get("generation_job_id") or take_id)
        with self.open_job_session(payload, job_id=active_job_id) as session:
            return self.synthesize_take(session, payload, take_id=take_id)

    @contextmanager
    def open_job_session(
        self,
        payload: dict[str, Any],
        *,
        job_id: str,
        cancel_event: threading.Event | None = None,
    ):
        profile = self.runtime_profile()
        emotion_mode = str(payload.get("emotion_mode") or "same_voice")
        if emotion_mode == "text_prompt":
            if not profile.profile.allow_text_emotion:
                raise ValueError("text emotion is disabled by the runtime profile")
            _require_text_emotion_ready(self.paths)
        init_payload = {
            "use_bf16": profile.effective_precision == "bf16",
            "use_qwen_emo": emotion_mode == "text_prompt"
            and profile.profile.allow_text_emotion,
            "use_cuda_kernel": profile.profile.use_cuda_kernel,
            "use_deepspeed": profile.profile.use_deepspeed,
            "use_accel": profile.profile.use_accel,
            "use_torch_compile": profile.profile.use_torch_compile,
        }
        with self.coordinator.lease("indextts2", job_id=job_id):
            with self.runner.open_session(self.paths, init_payload, cancel_event=cancel_event) as session:
                yield session

    def synthesize_take(self, session: Any, payload: dict[str, Any], *, take_id: str) -> tuple[Path, int]:
        text = str(payload.get("text") or payload.get("input_text") or "").strip()
        if not text:
            raise ValueError("text is required")
        speaker = self._resolve_speaker(payload.get("speaker"))
        request = self._build_worker_payload(payload, text=text, speaker_audio_path=speaker.absolute_path)
        output_path = self.paths.tmp_dir / f"{take_id}-indextts2.wav"
        sample_rate = session.synthesize(request, output_path, take_id=take_id)
        if speaker.voice_id:
            mark_voice_used(self.paths, speaker.voice_id)
        return output_path, sample_rate

    def _resolve_speaker(self, speaker: object) -> ResolvedAudio:
        if not isinstance(speaker, dict):
            raise ValueError("speaker reference is required")
        return self._resolve_audio_reference(speaker, required_label="speaker")

    def _resolve_emotion_audio(self, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("emotion audio reference must be an object")
        return self._resolve_audio_reference(value, required_label="emotion audio").absolute_path

    def _resolve_audio_reference(self, reference: dict[str, Any], *, required_label: str) -> ResolvedAudio:
        kind = str(reference.get("kind") or "")
        if kind == "upload":
            source_path = str(reference.get("path") or "")
            if not source_path:
                raise ValueError(f"{required_label} upload path is required")
            relative_path = copy_tmp_audio(self.paths, source_path)
            return ResolvedAudio(
                voice_id=None,
                relative_path=relative_path,
                absolute_path=str((self.paths.project_root / relative_path).resolve()),
            )
        if kind == "saved_voice":
            voice_id = str(reference.get("voice_id") or "")
            if not voice_id:
                raise ValueError("voice_id is required")
            conn = initialize_database(self.paths)
            try:
                voice = VoiceRepository(conn).get(voice_id)
            finally:
                conn.close()
            if voice is None or voice.deleted_at is not None:
                raise ValueError(f"voice not found: {voice_id}")
            return ResolvedAudio(
                voice_id=voice.id,
                relative_path=voice.audio_path,
                absolute_path=str((self.paths.project_root / voice.audio_path).resolve()),
            )
        raise ValueError(f"{required_label} reference is required")

    def _build_worker_payload(self, payload: dict[str, Any], *, text: str, speaker_audio_path: str) -> dict[str, Any]:
        runtime_profile = self.runtime_profile()
        language = str(payload.get("language") or "")
        if not language:
            raise ValueError("language is required")
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError("language must be one of ZH, EN, JA, ES, AR")
        emotion_mode = str(payload.get("emotion_mode") or "same_voice")
        _validate_emotion_source_exclusive(payload, emotion_mode)
        emo_audio_prompt = None
        emo_vector = None
        use_emo_text = False
        emo_text = None
        if emotion_mode == "same_voice":
            pass
        elif emotion_mode == "audio_prompt":
            emo_audio_prompt = self._resolve_emotion_audio(payload.get("emotion_audio"))
        elif emotion_mode == "vector":
            emo_vector = _parse_emo_vector(payload.get("emo_vector"))
        elif emotion_mode == "text_prompt":
            if not runtime_profile.profile.allow_text_emotion:
                raise ValueError("text emotion is disabled by the runtime profile")
            _require_text_emotion_ready(self.paths)
            use_emo_text = True
            emo_text = str(payload.get("emo_text") or "").strip() or None
        else:
            raise ValueError(f"unsupported emotion mode: {emotion_mode}")

        return {
            "emotion_mode": emotion_mode,
            "spk_audio_prompt": speaker_audio_path,
            "text": text,
            "language": language,
            "emo_audio_prompt": emo_audio_prompt,
            "emo_alpha": _float_in_range(payload.get("emo_alpha", 1.0), "emo_alpha", 0.0, 1.0),
            "emo_vector": emo_vector,
            "use_emo_text": use_emo_text,
            "emo_text": emo_text,
            "use_random": bool(payload.get("use_random", False)),
            "interval_silence": _int_in_range(payload.get("interval_silence", 200), "interval_silence", 0, 5000),
            "max_text_tokens_per_segment": _int_in_range(
                payload.get("max_text_tokens_per_segment", 120),
                "max_text_tokens_per_segment",
                20,
                1000,
            ),
            "duration_factor": _float_in_range(payload.get("duration_factor", 1.0), "duration_factor", 0.5, 2.0),
            "text_normalization": bool(payload.get("text_normalization", True)),
            "top_p": _float_in_range(payload.get("top_p", 0.8), "top_p", 0.0, 1.0),
            "top_k": _int_in_range(payload.get("top_k", 30), "top_k", 0, 200),
            "temperature": _float_in_range(payload.get("temperature", 0.8), "temperature", 0.1, 2.0),
            "length_penalty": _float_in_range(payload.get("length_penalty", 0.0), "length_penalty", -5.0, 5.0),
            "num_beams": _int_in_range(payload.get("num_beams", 3), "num_beams", 1, 20),
            "repetition_penalty": _float_in_range(
                payload.get("repetition_penalty", 10.0),
                "repetition_penalty",
                0.1,
                50.0,
            ),
            "max_mel_tokens": _int_in_range(payload.get("max_mel_tokens", 1500), "max_mel_tokens", 100, 5000),
            "precision": runtime_profile.effective_precision,
            "allow_text_emotion": runtime_profile.profile.allow_text_emotion,
            "use_bf16": runtime_profile.effective_precision == "bf16",
            "use_qwen_emo": emotion_mode == "text_prompt" and runtime_profile.profile.allow_text_emotion,
            "use_cuda_kernel": runtime_profile.profile.use_cuda_kernel,
            "use_deepspeed": runtime_profile.profile.use_deepspeed,
            "use_accel": runtime_profile.profile.use_accel,
            "use_torch_compile": runtime_profile.profile.use_torch_compile,
        }


def _source_root(paths: AppPaths) -> Path:
    return paths.project_root / "third_party" / "index-tts"


def _runtime_python(paths: AppPaths) -> Path:
    configured = os.environ.get("INDEXTTS2_PYTHON")
    if configured:
        return Path(configured).resolve()
    return paths.project_root / "data" / "runtimes" / "indextts2" / ".venv" / "Scripts" / "python.exe"


def _runtime_root(paths: AppPaths) -> Path:
    return paths.project_root / "data" / "runtimes" / "indextts2"


def _runtime_cache_env(paths: AppPaths) -> dict[str, str]:
    runtime_root = _runtime_root(paths)
    return {
        "UV_PROJECT_ENVIRONMENT": str(runtime_root / ".venv"),
        "UV_CACHE_DIR": str(runtime_root / "uv-cache"),
        "UV_PYTHON_INSTALL_DIR": str(runtime_root / "uv-python"),
        "UV_PYTHON_CACHE_DIR": str(runtime_root / "uv-python-cache"),
        "UV_TOOL_DIR": str(runtime_root / "uv-tools"),
        "UV_TOOL_BIN_DIR": str(runtime_root / "uv-tool-bin"),
        "HF_HOME": str(runtime_root / "hf-home"),
        "HF_HUB_CACHE": str(runtime_root / "hf-home" / "hub"),
        "HF_XET_CACHE": str(runtime_root / "hf-home" / "xet"),
        "TORCH_EXTENSIONS_DIR": str(runtime_root / "torch-extensions"),
        "XDG_CACHE_HOME": str(runtime_root / "xdg-cache"),
        "MPLCONFIGDIR": str(runtime_root / "matplotlib"),
        "NUMBA_CACHE_DIR": str(runtime_root / "numba-cache"),
    }


def _worker_timeout_seconds() -> float:
    return float(os.environ.get("INDEXTTS2_WORKER_TIMEOUT_SECONDS", "1800"))


def _model_dir(paths: AppPaths) -> Path:
    configured = os.environ.get("INDEXTTS2_MODEL_DIR")
    if configured:
        return Path(configured).resolve()
    return paths.project_root / "third_party" / "index-tts" / "checkpoints-2.5"


def _cfg_path(paths: AppPaths) -> Path:
    configured = os.environ.get("INDEXTTS2_CFG_PATH")
    if configured:
        return Path(configured).resolve()
    return _model_dir(paths) / "config.yaml"


def _is_project_local(paths: AppPaths, path: Path) -> bool:
    root = paths.project_root.resolve()
    resolved = path.resolve()
    return resolved == root or root in resolved.parents


def _missing_checkpoint_files(paths: AppPaths) -> list[str]:
    model_dir = _model_dir(paths)
    if not model_dir.exists():
        return [str(model_dir)]
    return [str(model_dir / name) for name in REQUIRED_CHECKPOINT_FILES if not (model_dir / name).exists()]


def _source_model_family(paths: AppPaths) -> str | None:
    source = _source_root(paths) / "indextts"
    if (source / "infer_v2_5.py").exists():
        return "2.5"
    if (source / "infer_v2.py").exists():
        return "2.0"
    return None


def _checkpoint_model_family(model_dir: Path) -> str | None:
    config = model_dir / "config.yaml"
    if config.exists():
        try:
            text = config.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            text = ""
        if "2.5" in text:
            return "2.5"
        if "2.0" in text:
            return "2.0"
    required_25 = {"gpt.pth", "s2mel.pth", "codec.pth", "multilingual_zh_ja_yue_char_del.tiktoken", "wav2vec2bert_stats.pt"}
    if all((model_dir / name).exists() for name in required_25):
        return "2.5"
    if (model_dir / "bpe.model").exists() and (model_dir / "gpt.pth").exists() and (model_dir / "s2mel.pth").exists():
        return "2.0"
    return None


def _asset_version_mismatch(paths: AppPaths) -> dict[str, str] | None:
    source_family = _source_model_family(paths)
    checkpoint_family = _checkpoint_model_family(_model_dir(paths))
    if source_family is None or checkpoint_family is None or source_family == checkpoint_family:
        return None
    return {"source_model_family": source_family, "checkpoint_model_family": checkpoint_family}


def _optional_config_assets(cfg_path: Path, model_dir: Path) -> dict[str, object]:
    try:
        config_text = cfg_path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        config_text = ""
    missing_text_emotion_assets: list[str] = []
    missing_pronunciation_assets: list[str] = []
    if not config_text or "qwen_emo_path" not in config_text:
        missing_text_emotion_assets.append("QwenEmotion")
    else:
        qwen_paths = [path for path in model_dir.iterdir() if "qwen" in path.name.lower()] if model_dir.exists() else []
        if not qwen_paths:
            missing_text_emotion_assets.append("QwenEmotion")
    if "pinyin.vocab" in config_text and not (model_dir / "pinyin.vocab").exists():
        missing_pronunciation_assets.append("pinyin.vocab")
    return {
        "missing_text_emotion_assets": missing_text_emotion_assets,
        "missing_pronunciation_assets": missing_pronunciation_assets,
        "text_emotion_assets_configured": not missing_text_emotion_assets,
    }


def _text_emotion_readiness(paths: AppPaths) -> dict[str, object]:
    return _optional_config_assets(_cfg_path(paths), _model_dir(paths))


def _require_text_emotion_ready(paths: AppPaths) -> None:
    readiness = _text_emotion_readiness(paths)
    if readiness["missing_text_emotion_assets"]:
        raise AppBackendError(
            "Text emotion requires configured local QwenEmotion assets",
            code="text_emotion_unavailable",
            details={"missing_text_emotion_assets": readiness["missing_text_emotion_assets"]},
        )


def _parse_emo_vector(value: object) -> list[float]:
    if isinstance(value, dict):
        vector = [float(value.get(field, 0.0)) for field in EMOTION_VECTOR_FIELDS]
    elif isinstance(value, list):
        vector = [float(item) for item in value]
    else:
        raise ValueError("emo_vector is required for vector emotion mode")
    if len(vector) != len(EMOTION_VECTOR_FIELDS):
        raise ValueError("emo_vector must have 8 values")
    for item in vector:
        if item < 0 or item > 1:
            raise ValueError("emo_vector values must be between 0 and 1")
    if sum(vector) > 0.8:
        raise ValueError("emo_vector values must sum to 0.8 or less")
    return vector


def _validate_emotion_source_exclusive(payload: dict[str, Any], emotion_mode: str) -> None:
    sources: list[str] = []
    if payload.get("emotion_audio") is not None:
        sources.append("audio_prompt")
    if payload.get("emo_vector") is not None:
        sources.append("vector")
    if bool(payload.get("use_emo_text")) or str(payload.get("emo_text") or "").strip():
        sources.append("text_prompt")
    if len(sources) > 1:
        raise ValueError("emotion source must be one of audio_prompt, vector, or text_prompt")
    if emotion_mode == "same_voice" and sources:
        raise ValueError("same_voice emotion mode cannot include an emotion source")
    if emotion_mode == "text_prompt" and sources in ([], ["text_prompt"]):
        return
    if emotion_mode in {"audio_prompt", "vector", "text_prompt"} and sources != [emotion_mode]:
        raise ValueError(f"emotion_mode {emotion_mode} requires its matching emotion source")


def _float_in_range(value: object, name: str, minimum: float, maximum: float) -> float:
    parsed = float(value)
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _int_in_range(value: object, name: str, minimum: int, maximum: int) -> int:
    parsed = int(value)
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _history_params(request: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in request.items() if key not in {"spk_audio_prompt"}}


def _stable_warnings(warnings: list[object]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for warning in warnings:
        if isinstance(warning, dict) and "code" in warning and "message" in warning:
            result.append({"code": str(warning["code"]), "message": str(warning["message"])})
        else:
            result.append({"code": "runtime_profile_warning", "message": str(warning)})
    return result


def _error_summary(error: Exception) -> str:
    text = str(error).strip() or type(error).__name__
    if isinstance(error, AppBackendError):
        text = f"{error.code}: {text}"
    return text.splitlines()[0][:500]
