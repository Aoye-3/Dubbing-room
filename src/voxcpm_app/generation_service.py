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
        normalize: bool,
        denoise: bool,
    ) -> tuple[int, np.ndarray]:
        ...


@dataclass(frozen=True)
class ResolvedReference:
    voice_id: str | None
    relative_path: str | None
    absolute_path: str | None


class VoxCPMSynthesizer:
    def __init__(self, *, model_id: str = "openbmb/VoxCPM2", device: str = "cuda"):
        self.model_id = model_id
        self.device = device
        self._model = None

    def _get_model(self):
        if self._model is None:
            from voxcpm import VoxCPM

            self._model = VoxCPM.from_pretrained(
                self.model_id,
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
        normalize: bool,
        denoise: bool,
    ) -> tuple[int, np.ndarray]:
        if prompt_text and not reference_audio_path:
            raise ValueError("prompt_text requires a reference audio")

        model = self._get_model()
        control = re.sub(r"[()（）]", "", control_instruction or "").strip()
        final_text = f"({control}){input_text}" if control else input_text
        prompt_text_clean = (prompt_text or "").strip()
        wav = model.generate(
            text=final_text,
            prompt_wav_path=reference_audio_path if prompt_text_clean else None,
            prompt_text=prompt_text_clean or None,
            reference_wav_path=reference_audio_path,
            cfg_value=float(cfg_value),
            inference_timesteps=int(inference_timesteps),
            normalize=bool(normalize),
            denoise=bool(denoise) and reference_audio_path is not None,
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
        self.synthesizer = synthesizer or VoxCPMSynthesizer(model_id=model_id, device=device)
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
            busy=bool(state["busy"]),
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
        )
        mark_generation_running(self.paths, generation.id)

        try:
            with self.coordinator.lease("voxcpm2", job_id=generation.id):
                sample_rate, audio = self.synthesizer.synthesize(
                    input_text=input_text,
                    control_instruction=str(payload.get("control_instruction") or ""),
                    reference_audio_path=reference.absolute_path,
                    prompt_text=str(payload.get("prompt_text") or ""),
                    cfg_value=float(payload.get("cfg_value", 2.0)),
                    inference_timesteps=int(payload.get("inference_timesteps", 10)),
                    normalize=bool(payload.get("normalize", False)),
                    denoise=bool(payload.get("denoise", False)),
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
