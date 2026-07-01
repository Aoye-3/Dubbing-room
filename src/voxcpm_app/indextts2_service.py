from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import soundfile as sf

from .audio_assets import copy_tmp_audio
from .db import initialize_database
from .generation_history import (
    create_generation,
    mark_generation_failed,
    mark_generation_running,
    mark_generation_succeeded,
)
from .paths import AppPaths
from .repositories import VoiceRepository
from .runtime import RUNTIME_COORDINATOR, RuntimeBackendStatus, RuntimeCoordinator
from .schemas import GenerationRecord
from .voice_library import mark_voice_used


EMOTION_VECTOR_FIELDS = ["happy", "angry", "sad", "afraid", "disgusted", "melancholic", "surprised", "calm"]
REQUIRED_CHECKPOINT_FILES = ["config.yaml", "bpe.model", "gpt.pth", "s2mel.pth"]


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


class SubprocessIndexTTS2Runner:
    def status(self, paths: AppPaths, *, coordinator: RuntimeCoordinator) -> RuntimeBackendStatus:
        source_root = _source_root(paths)
        runtime_python = _runtime_python(paths)
        model_dir = _model_dir(paths)
        missing: list[str] = []
        if not source_root.exists():
            missing.append("third_party/index-tts")
        if not runtime_python.exists():
            missing.append(str(runtime_python))
        if not model_dir.exists():
            missing.append(str(model_dir))
        else:
            missing.extend(str(model_dir / name) for name in REQUIRED_CHECKPOINT_FILES if not (model_dir / name).exists())
        last_error = coordinator.last_error("indextts2") or "; ".join(missing)
        state = coordinator.status("indextts2")
        return RuntimeBackendStatus(
            backend_id="indextts2",
            display_name="IndexTTS2",
            enabled=True,
            configured=not missing,
            loaded=False,
            busy=bool(state["busy"]),
            device=os.environ.get("INDEXTTS2_DEVICE", os.environ.get("VOXCPM_APP_DEVICE", "cuda")),
            last_error=last_error,
            capabilities=[
                "line_performance",
                "speaker_reference",
                "emotion_audio",
                "emotion_vector",
                "emotion_text",
                "multi_take",
            ],
            active_job_id=state["active_job_id"] if isinstance(state["active_job_id"], str) else None,
            started_at=state["started_at"] if isinstance(state["started_at"], str) else None,
        )

    def synthesize(self, paths: AppPaths, payload: dict[str, Any], output_path: Path) -> int:
        source_root = _source_root(paths)
        runtime_python = _runtime_python(paths)
        model_dir = _model_dir(paths)
        cfg_path = _cfg_path(paths)
        if not source_root.exists():
            raise RuntimeError("IndexTTS2 source snapshot is missing: third_party/index-tts")
        if not runtime_python.exists():
            raise RuntimeError(f"IndexTTS2 runtime python is not configured: {runtime_python}")
        missing_checkpoints = _missing_checkpoint_files(paths)
        if missing_checkpoints:
            raise RuntimeError(f"IndexTTS2 checkpoints are missing: {', '.join(missing_checkpoints)}")

        worker_payload = {
            **payload,
            "source_root": str(source_root),
            "model_dir": str(model_dir),
            "cfg_path": str(cfg_path),
            "output_path": str(output_path),
            "device": os.environ.get("INDEXTTS2_DEVICE", os.environ.get("VOXCPM_APP_DEVICE", "cuda")),
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
        completed = subprocess.run(
            [str(runtime_python), "-m", "voxcpm_app.indextts2_worker"],
            input=json.dumps(worker_payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            cwd=str(paths.project_root),
            env=env,
            check=False,
        )
        stdout_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        raw = stdout_lines[-1] if stdout_lines else "{}"
        try:
            result = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid IndexTTS2 worker JSON: {exc}") from exc
        if completed.returncode != 0 or not result.get("ok"):
            raise RuntimeError(str(result.get("error") or completed.stderr or "IndexTTS2 worker failed"))
        info = sf.info(str(output_path))
        return int(info.samplerate)


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

    def runtime_status(self) -> RuntimeBackendStatus:
        return self.runner.status(self.paths, coordinator=self.coordinator)

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
        )
        mark_generation_running(self.paths, generation.id)
        output_path = self.paths.tmp_dir / f"{generation.id}-indextts2.wav"

        try:
            with self.coordinator.lease("indextts2"):
                sample_rate = self.runner.synthesize(self.paths, request, output_path)
            succeeded = mark_generation_succeeded(
                self.paths,
                generation.id,
                source_output_audio_path=output_path,
                sample_rate=sample_rate,
            )
            if speaker.voice_id:
                mark_voice_used(self.paths, speaker.voice_id)
            return succeeded
        except Exception as exc:
            return mark_generation_failed(self.paths, generation.id, error_summary=_error_summary(exc))

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
            use_emo_text = True
            emo_text = str(payload.get("emo_text") or "").strip() or None
            if emo_text is None:
                raise ValueError("emo_text is required for text emotion mode")
        else:
            raise ValueError(f"unsupported emotion mode: {emotion_mode}")

        return {
            "emotion_mode": emotion_mode,
            "spk_audio_prompt": speaker_audio_path,
            "text": text,
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
            "do_sample": bool(payload.get("do_sample", True)),
            "top_p": _float_in_range(payload.get("top_p", 0.8), "top_p", 0.0, 1.0),
            "top_k": _int_in_range(payload.get("top_k", 30), "top_k", 0, 200),
            "temperature": _float_in_range(payload.get("temperature", 0.8), "temperature", 0.1, 2.0),
            "length_penalty": float(payload.get("length_penalty", 0.0)),
            "num_beams": _int_in_range(payload.get("num_beams", 3), "num_beams", 1, 20),
            "repetition_penalty": _float_in_range(
                payload.get("repetition_penalty", 10.0),
                "repetition_penalty",
                0.1,
                50.0,
            ),
            "max_mel_tokens": _int_in_range(payload.get("max_mel_tokens", 1500), "max_mel_tokens", 100, 5000),
            "use_fp16": bool(payload.get("use_fp16", False)),
            "use_cuda_kernel": bool(payload.get("use_cuda_kernel", False)),
            "use_deepspeed": bool(payload.get("use_deepspeed", False)),
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
    }


def _model_dir(paths: AppPaths) -> Path:
    configured = os.environ.get("INDEXTTS2_MODEL_DIR")
    if configured:
        return Path(configured).resolve()
    return paths.project_root / "third_party" / "index-tts" / "checkpoints"


def _cfg_path(paths: AppPaths) -> Path:
    configured = os.environ.get("INDEXTTS2_CFG_PATH")
    if configured:
        return Path(configured).resolve()
    return _model_dir(paths) / "config.yaml"


def _missing_checkpoint_files(paths: AppPaths) -> list[str]:
    model_dir = _model_dir(paths)
    if not model_dir.exists():
        return [str(model_dir)]
    return [str(model_dir / name) for name in REQUIRED_CHECKPOINT_FILES if not (model_dir / name).exists()]


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


def _error_summary(error: Exception) -> str:
    text = str(error).strip() or type(error).__name__
    return text.splitlines()[0][:500]
