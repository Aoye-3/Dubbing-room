from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .paths import AppPaths


UPSTREAM_COMMIT = "a371df7d0746a0ae7fdf075798b6b04e34a0132e"
SUPPORTED_LANGUAGES = ["ZH", "EN", "JA", "ES", "AR"]
_PROFILE_FIELDS = {"precision", "allow_text_emotion", "use_cuda_kernel", "use_deepspeed", "use_accel", "use_torch_compile"}


@dataclass(frozen=True)
class IndexTTS2RuntimeProfile:
    precision: str = "auto"
    allow_text_emotion: bool = True
    use_cuda_kernel: bool = False
    use_deepspeed: bool = False
    use_accel: bool = False
    use_torch_compile: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


DEFAULT_RUNTIME_PROFILE = IndexTTS2RuntimeProfile()


@dataclass(frozen=True)
class RuntimeProfileResolution:
    profile: IndexTTS2RuntimeProfile
    effective_precision: str
    warnings: list[str]
    capability: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile.to_dict(),
            "effective_precision": self.effective_precision,
            "warnings": self.warnings,
            "capability": self.capability,
        }


class IndexTTS2RuntimeProfileStore:
    def __init__(self, paths: AppPaths):
        self.paths = paths

    def load(self) -> RuntimeProfileResolution:
        warnings: list[str] = []
        profile = DEFAULT_RUNTIME_PROFILE
        path = self.paths.indextts2_runtime_profile_path
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                profile = _profile_from_payload(raw)
            except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
                warnings.append(f"Unable to read IndexTTS-2.5 runtime profile: {exc}")
        return _resolve_profile(profile, warnings)

    def save(self, payload: object) -> RuntimeProfileResolution:
        profile = _profile_from_payload(payload)
        self.paths.app_root.mkdir(parents=True, exist_ok=True)
        path = self.paths.indextts2_runtime_profile_path
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            temporary.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return _resolve_profile(profile, [])


def _profile_from_payload(payload: object) -> IndexTTS2RuntimeProfile:
    if not isinstance(payload, dict):
        raise ValueError("runtime profile must be an object")
    keys = set(payload)
    unknown = keys - _PROFILE_FIELDS
    missing = _PROFILE_FIELDS - keys
    if unknown:
        raise ValueError(f"unknown runtime profile fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"missing runtime profile fields: {', '.join(sorted(missing))}")
    precision = payload["precision"]
    if precision not in {"auto", "bf16", "fp32"}:
        raise ValueError("precision must be one of: auto, bf16, fp32")
    for field in _PROFILE_FIELDS - {"precision"}:
        if type(payload[field]) is not bool:
            raise ValueError(f"{field} must be a boolean")
    return IndexTTS2RuntimeProfile(**payload)


def _resolve_profile(profile: IndexTTS2RuntimeProfile, warnings: list[str]) -> RuntimeProfileResolution:
    bf16_supported, capability_warning = _cuda_bf16_available()
    if capability_warning:
        warnings.append(capability_warning)
    effective_precision = profile.precision
    if effective_precision == "auto":
        effective_precision = "bf16" if bf16_supported else "fp32"
    if effective_precision == "bf16" and not bf16_supported:
        warnings.append("BF16 was requested but CUDA BF16 support is unavailable.")
        effective_precision = "fp32"
    memory_gb, memory_warning = _cuda_memory_gb()
    if memory_warning:
        warnings.append(memory_warning)
    elif memory_gb is not None and memory_gb < 10:
        warnings.append(f"CUDA device has {memory_gb:g} GB low VRAM; IndexTTS-2.5 may use reduced-memory behavior.")
    return RuntimeProfileResolution(
        profile=profile,
        effective_precision=effective_precision,
        warnings=warnings,
        capability={
            "cuda_bf16_available": bf16_supported,
            "precision_modes": ["auto", "bf16", "fp32"],
            "text_emotion_available": profile.allow_text_emotion,
            "use_cuda_kernel": profile.use_cuda_kernel,
            "use_deepspeed": profile.use_deepspeed,
            "use_accel": profile.use_accel,
            "use_torch_compile": profile.use_torch_compile,
        },
    )


def _cuda_bf16_available() -> tuple[bool, str | None]:
    try:
        import torch

        if not torch.cuda.is_available():
            return False, None
        checker = getattr(torch.cuda, "is_bf16_supported", None)
        return bool(checker()) if callable(checker) else False, None
    except Exception as exc:
        return False, f"Unable to detect CUDA BF16 support: {exc}"


def _cuda_memory_gb() -> tuple[float | None, str | None]:
    try:
        import torch

        if not torch.cuda.is_available():
            return None, None
        return torch.cuda.get_device_properties(0).total_memory / (1024**3), None
    except Exception as exc:
        return None, f"Unable to detect CUDA memory: {exc}"
