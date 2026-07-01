from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


GENERATION_STATUSES = {"pending", "running", "succeeded", "failed", "cancelled", "deleted"}
JOB_STATUSES = {"queued", "running", "succeeded", "failed", "cancelled", "deleted"}
ASSET_KINDS = {"voice", "reference", "generation_output", "take_output", "uploaded"}


@dataclass(frozen=True)
class VoiceRecord:
    id: str
    display_name: str
    tags: list[str]
    notes: str
    source: str
    audio_path: str
    audio_sha256: str
    duration_seconds: float | None
    created_at: str
    updated_at: str
    last_used_at: str | None
    deleted_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GenerationRecord:
    id: str
    input_text: str
    control_instruction: str
    voice_id: str | None
    reference_audio_path: str | None
    prompt_text: str
    cfg_value: float
    inference_timesteps: int
    normalize: bool
    denoise: bool
    output_audio_path: str | None
    sample_rate: int | None
    status: str
    error_summary: str
    created_at: str
    updated_at: str
    deleted_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AssetRecord:
    id: str
    kind: str
    path: str
    sha256: str
    mime_type: str
    duration_seconds: float | None
    sample_rate: int | None
    created_at: str
    deleted_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GenerationJobRecord:
    id: str
    backend_id: str
    model_id: str
    mode: str
    status: str
    input_text: str
    voice_id: str | None
    params_json: str
    output_asset_id: str | None
    error_summary: str
    legacy_generation_id: str | None
    created_at: str
    updated_at: str
    deleted_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GenerationTakeRecord:
    id: str
    job_id: str
    backend_id: str
    take_index: int
    label: str
    status: str
    params_json: str
    output_asset_id: str | None
    is_selected: bool
    error_summary: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

