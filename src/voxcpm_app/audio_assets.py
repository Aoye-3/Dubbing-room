from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from uuid import uuid4

from .paths import AppPaths


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_voice_audio(paths: AppPaths, source_audio_path: str | Path, voice_id: str) -> tuple[str, str]:
    source = Path(source_audio_path)
    if not source.is_absolute():
        source = paths.project_root / source
    if not source.exists():
        raise FileNotFoundError(f"source audio does not exist: {source}")
    extension = source.suffix.lower() or ".wav"
    destination = paths.voices_dir / f"{voice_id}{extension}"
    paths.voices_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return paths.project_relative(destination), sha256_file(destination)


def copy_generation_audio(paths: AppPaths, source_output_audio_path: str | Path, generation_id: str) -> str:
    source = Path(source_output_audio_path)
    if not source.is_absolute():
        source = paths.project_root / source
    if not source.exists():
        raise FileNotFoundError(f"source output audio does not exist: {source}")
    destination = paths.generations_dir / f"{generation_id}.wav"
    paths.generations_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return paths.project_relative(destination)


def copy_tmp_audio(paths: AppPaths, source_audio_path: str | Path) -> str:
    source = Path(source_audio_path)
    if not source.exists():
        raise FileNotFoundError(f"source audio does not exist: {source}")
    extension = source.suffix.lower() or ".wav"
    destination = paths.tmp_dir / f"{uuid4()}{extension}"
    paths.tmp_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return paths.project_relative(destination)

