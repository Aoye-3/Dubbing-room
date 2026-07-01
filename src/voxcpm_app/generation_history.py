from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .audio_assets import copy_generation_audio
from .db import initialize_database, utc_now
from .paths import AppPaths
from .repositories import GenerationRepository
from .schemas import GenerationRecord


def create_generation(
    paths: AppPaths,
    *,
    input_text: str,
    control_instruction: str,
    voice_id: str | None,
    reference_audio_path: str | None,
    prompt_text: str,
    cfg_value: float,
    inference_timesteps: int,
    normalize: bool,
    denoise: bool,
) -> GenerationRecord:
    text = input_text.strip()
    if not text:
        raise ValueError("input_text is required")
    now = utc_now()
    record = GenerationRecord(
        id=str(uuid4()),
        input_text=text,
        control_instruction=control_instruction or "",
        voice_id=voice_id,
        reference_audio_path=reference_audio_path,
        prompt_text=prompt_text or "",
        cfg_value=float(cfg_value),
        inference_timesteps=int(inference_timesteps),
        normalize=bool(normalize),
        denoise=bool(denoise),
        output_audio_path=None,
        sample_rate=None,
        status="pending",
        error_summary="",
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    conn = initialize_database(paths)
    try:
        return GenerationRepository(conn).insert(record)
    finally:
        conn.close()


def list_generations(paths: AppPaths, *, include_deleted: bool = False) -> list[GenerationRecord]:
    conn = initialize_database(paths)
    try:
        return GenerationRepository(conn).list(include_deleted=include_deleted)
    finally:
        conn.close()


def mark_generation_running(paths: AppPaths, generation_id: str) -> GenerationRecord:
    conn = initialize_database(paths)
    try:
        return GenerationRepository(conn).update(generation_id, status="running")
    finally:
        conn.close()


def mark_generation_succeeded(
    paths: AppPaths,
    generation_id: str,
    *,
    source_output_audio_path: str | Path,
    sample_rate: int,
) -> GenerationRecord:
    output_audio_path = copy_generation_audio(paths, source_output_audio_path, generation_id)
    conn = initialize_database(paths)
    try:
        return GenerationRepository(conn).update(
            generation_id,
            status="succeeded",
            output_audio_path=output_audio_path,
            sample_rate=int(sample_rate),
            error_summary="",
        )
    finally:
        conn.close()


def mark_generation_failed(paths: AppPaths, generation_id: str, *, error_summary: str) -> GenerationRecord:
    conn = initialize_database(paths)
    try:
        return GenerationRepository(conn).update(
            generation_id,
            status="failed",
            error_summary=error_summary,
        )
    finally:
        conn.close()


def delete_generation(paths: AppPaths, generation_id: str) -> GenerationRecord:
    conn = initialize_database(paths)
    try:
        return GenerationRepository(conn).update(generation_id, status="deleted", deleted_at=utc_now())
    finally:
        conn.close()
