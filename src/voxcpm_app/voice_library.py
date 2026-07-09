from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .audio_assets import copy_voice_audio
from .db import initialize_database, utc_now
from .paths import AppPaths
from .repositories import VoiceRepository
from .schemas import VoiceRecord


def create_voice(
    paths: AppPaths,
    *,
    source_audio_path: str | Path,
    display_name: str,
    tags: list[str] | None = None,
    notes: str = "",
    source: str = "upload",
    source_generation_id: str | None = None,
    duration_seconds: float | None = None,
) -> VoiceRecord:
    name = display_name.strip()
    if not name:
        raise ValueError("display_name is required")
    voice_id = str(uuid4())
    audio_path, audio_sha256 = copy_voice_audio(paths, source_audio_path, voice_id)
    now = utc_now()
    record = VoiceRecord(
        id=voice_id,
        display_name=name,
        tags=list(tags or []),
        notes=notes,
        source=source or "upload",
        audio_path=audio_path,
        audio_sha256=audio_sha256,
        source_generation_id=source_generation_id,
        duration_seconds=duration_seconds,
        created_at=now,
        updated_at=now,
        last_used_at=None,
        deleted_at=None,
    )
    conn = initialize_database(paths)
    try:
        return VoiceRepository(conn).insert(record)
    finally:
        conn.close()


def list_voices(paths: AppPaths, *, include_deleted: bool = False) -> list[VoiceRecord]:
    conn = initialize_database(paths)
    try:
        return VoiceRepository(conn).list(include_deleted=include_deleted)
    finally:
        conn.close()


def update_voice(
    paths: AppPaths,
    voice_id: str,
    *,
    display_name: str,
    tags: list[str],
    notes: str,
) -> VoiceRecord:
    conn = initialize_database(paths)
    try:
        return VoiceRepository(conn).update(
            voice_id,
            display_name=display_name.strip(),
            tags=list(tags),
            notes=notes,
        )
    finally:
        conn.close()


def delete_voice(paths: AppPaths, voice_id: str) -> VoiceRecord:
    conn = initialize_database(paths)
    try:
        return VoiceRepository(conn).soft_delete(voice_id)
    finally:
        conn.close()


def mark_voice_used(paths: AppPaths, voice_id: str) -> VoiceRecord:
    conn = initialize_database(paths)
    try:
        return VoiceRepository(conn).mark_used(voice_id)
    finally:
        conn.close()

