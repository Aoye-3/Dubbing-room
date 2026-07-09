from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
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


class Synthesizer(Protocol):
    def synthesize(
        self,
        *,
        input_text: str,
        control_instruction: str,
        reference_audio_path: str | None,
        prompt_text: str,
        cfg_value: float,
        inference_timesteps: int,
        min_len: int,
        max_len: int,
        normalize: bool,
        denoise: bool,
        retry_badcase: bool,
        retry_badcase_max_times: int,
        retry_badcase_ratio_threshold: float,
    ) -> tuple[int, np.ndarray]:
        ...


@dataclass(frozen=True)
class ResolvedReference:
    voice_id: str | None
    relative_path: str | None
    absolute_path: str | None


class VoxCPMSynthesizer:
    def __init__(
        self,
        *,
        model_id: str = "openbmb/VoxCPM2",
        device: str = "cuda",
        cache_dir: str | None = None,
        local_files_only: bool = False,
        load_denoiser: bool = False,
        zipenhancer_model_id: str = "iic/speech_zipenhancer_ans_multiloss_16k_base",
    ):
        self.model_id = model_id
        self.device = device
        self.cache_dir = cache_dir
        self.local_files_only = local_files_only
        self.load_denoiser = load_denoiser
        self.zipenhancer_model_id = zipenhancer_model_id
        self._model = None

    def _get_model(self):
        if self._model is None:
            from voxcpm import VoxCPM

            self._model = VoxCPM.from_pretrained(
                self.model_id,
                load_denoiser=self.load_denoiser,
                zipenhancer_model_id=self.zipenhancer_model_id,
                cache_dir=self.cache_dir,
                local_files_only=self.local_files_only,
                device=self.device,
                optimize=str(self.device).startswith("cuda"),
            )
        return self._model

    def synthesize(
        self,
        *,
        input_text: str,
        control_instruction: str,
        reference_audio_path: str | None,
        prompt_text: str,
        cfg_value: float,
        inference_timesteps: int,
        min_len: int,
        max_len: int,
        normalize: bool,
        denoise: bool,
        retry_badcase: bool,
        retry_badcase_max_times: int,
        retry_badcase_ratio_threshold: float,
    ) -> tuple[int, np.ndarray]:
        if prompt_text and not reference_audio_path:
            raise ValueError("prompt_text requires a reference audio")

        model = self._get_model()
        control = re.sub(r"[()（）]", "", control_instruction or "").strip()
        prompt_text_clean = (prompt_text or "").strip()
        final_text = input_text if prompt_text_clean else f"({control}){input_text}" if control else input_text
        wav = model.generate(
            text=final_text,
            prompt_wav_path=reference_audio_path if prompt_text_clean else None,
            prompt_text=prompt_text_clean or None,
            reference_wav_path=reference_audio_path,
            cfg_value=float(cfg_value),
            inference_timesteps=int(inference_timesteps),
            min_len=int(min_len),
            max_len=int(max_len),
            normalize=bool(normalize),
            denoise=bool(denoise) and reference_audio_path is not None,
            retry_badcase=bool(retry_badcase),
            retry_badcase_max_times=int(retry_badcase_max_times),
            retry_badcase_ratio_threshold=float(retry_badcase_ratio_threshold),
        )
        return int(model.tts_model.sample_rate), wav


class GenerationService:
    def __init__(
        self,
        paths: AppPaths,
        *,
        synthesizer: Synthesizer | None = None,
        model_id: str = "openbmb/VoxCPM2",
        device: str = "cuda",
        coordinator: RuntimeCoordinator = RUNTIME_COORDINATOR,
    ):
        self.paths = paths
        self.synthesizer = synthesizer or VoxCPMSynthesizer(
            model_id=model_id,
            device=device,
            cache_dir=str(paths.project_root / "data" / "runtimes" / "voxcpm2" / "hf-cache"),
            load_denoiser=False,
        )
        self.device = device
        self.coordinator = coordinator

    def runtime_status(self) -> RuntimeBackendStatus:
        state = self.coordinator.status("voxcpm2")
        return RuntimeBackendStatus(
            backend_id="voxcpm2",
            display_name="VoxCPM2",
            enabled=True,
            configured=True,
            loaded=getattr(self.synthesizer, "_model", None) is not None,
            busy=bool(state["runtime_busy"]),
            device=self.device,
            last_error=str(state["last_error"]),
            capabilities=[
                "voice_design",
                "voice_clone",
                "ultimate_clone",
                "multilingual_generation",
            ],
            active_job_id=state["active_job_id"] if isinstance(state["active_job_id"], str) else None,
            started_at=state["started_at"] if isinstance(state["started_at"], str) else None,
            state="busy" if state["runtime_busy"] else "loaded" if getattr(self.synthesizer, "_model", None) is not None else "configured",
            details={
                "model_id": getattr(self.synthesizer, "model_id", "openbmb/VoxCPM2"),
                "cache_dir": getattr(
                    self.synthesizer,
                    "cache_dir",
                    str(self.paths.project_root / "data" / "runtimes" / "voxcpm2" / "hf-cache"),
                ),
                "local_files_only": bool(getattr(self.synthesizer, "local_files_only", False)),
                "load_denoiser": bool(getattr(self.synthesizer, "load_denoiser", False)),
                "runtime_busy": bool(state["runtime_busy"]),
                "active_backend": state["active_backend"],
            },
        )

    def generate_audio(self, payload: dict[str, Any]) -> GenerationRecord:
        input_text = str(payload.get("input_text") or "").strip()
        if not input_text:
            raise ValueError("input_text is required")

        reference = self._resolve_reference(payload.get("reference") or {"kind": "none"})
        generation = create_generation(
            self.paths,
            input_text=input_text,
            control_instruction=str(payload.get("control_instruction") or ""),
            voice_id=reference.voice_id,
            reference_audio_path=reference.relative_path,
            prompt_text=str(payload.get("prompt_text") or ""),
            cfg_value=float(payload.get("cfg_value", 2.0)),
            inference_timesteps=int(payload.get("inference_timesteps", 10)),
            normalize=bool(payload.get("normalize", False)),
            denoise=bool(payload.get("denoise", False)),
            source_backend="voxcpm2",
            source_mode=str(payload.get("source_mode") or "voice-design"),
            description=str(payload.get("description") or payload.get("control_instruction") or input_text),
        )
        mark_generation_running(self.paths, generation.id)

        try:
            active_job_id = str(payload.get("generation_job_id") or generation.id)
            with self.coordinator.lease("voxcpm2", job_id=active_job_id):
                sample_rate, audio = self.synthesizer.synthesize(
                    input_text=input_text,
                    control_instruction=str(payload.get("control_instruction") or ""),
                    reference_audio_path=reference.absolute_path,
                    prompt_text=str(payload.get("prompt_text") or ""),
                    cfg_value=float(payload.get("cfg_value", 2.0)),
                    inference_timesteps=int(payload.get("inference_timesteps", 10)),
                    min_len=int(payload.get("min_len", 2)),
                    max_len=int(payload.get("max_len", 4096)),
                    normalize=bool(payload.get("normalize", False)),
                    denoise=bool(payload.get("denoise", False)),
                    retry_badcase=bool(payload.get("retry_badcase", True)),
                    retry_badcase_max_times=int(payload.get("retry_badcase_max_times", 3)),
                    retry_badcase_ratio_threshold=float(payload.get("retry_badcase_ratio_threshold", 6.0)),
                )
            output_path = self.paths.tmp_dir / f"{generation.id}-output.wav"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output_path), np.asarray(audio), int(sample_rate))
            succeeded = mark_generation_succeeded(
                self.paths,
                generation.id,
                source_output_audio_path=output_path,
                sample_rate=int(sample_rate),
            )
            if reference.voice_id:
                mark_voice_used(self.paths, reference.voice_id)
            return succeeded
        except Exception as exc:
            return mark_generation_failed(
                self.paths,
                generation.id,
                error_summary=_error_summary(exc),
            )

    def _resolve_reference(self, reference: object) -> ResolvedReference:
        if not isinstance(reference, dict):
            raise ValueError("reference must be an object")

        kind = str(reference.get("kind") or "none")
        if kind == "none":
            return ResolvedReference(voice_id=None, relative_path=None, absolute_path=None)

        if kind == "upload":
            source_path = str(reference.get("path") or "")
            if not source_path:
                raise ValueError("reference upload path is required")
            relative_path = copy_tmp_audio(self.paths, source_path)
            return ResolvedReference(
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
            return ResolvedReference(
                voice_id=voice.id,
                relative_path=voice.audio_path,
                absolute_path=str((self.paths.project_root / voice.audio_path).resolve()),
            )

        raise ValueError(f"unsupported reference kind: {kind}")


def _error_summary(error: Exception) -> str:
    text = str(error).strip() or type(error).__name__
    return text.splitlines()[0][:500]
