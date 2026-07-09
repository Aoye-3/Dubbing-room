from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .audio_assets import copy_generation_audio
from .db import initialize_database, utc_now
from .paths import AppPaths
from .repositories import GenerationRepository
from .schemas import GenerationRecord
from .voice_library import create_voice


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
    source_backend: str = "voxcpm2",
    source_mode: str = "legacy",
    description: str = "",
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
        source_backend=source_backend or "voxcpm2",
        source_mode=source_mode or "legacy",
        description=description or "",
        is_favorite=False,
        output_audio_path=None,
        sample_rate=None,
        status="pending",
        error_summary="",
        saved_voice_id=None,
        promoted_to_voice_at=None,
        hidden_from_history_at=None,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    conn = initialize_database(paths)
    try:
        return GenerationRepository(conn).insert(record)
    finally:
        conn.close()


def list_generations(
    paths: AppPaths,
    *,
    include_deleted: bool = False,
    deleted_only: bool = False,
    include_hidden: bool = False,
) -> list[GenerationRecord]:
    conn = initialize_database(paths)
    try:
        return GenerationRepository(conn).list(
            include_deleted=include_deleted,
            deleted_only=deleted_only,
            include_hidden=include_hidden,
        )
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


def restore_generation(paths: AppPaths, generation_id: str) -> GenerationRecord:
    conn = initialize_database(paths)
    try:
        record = GenerationRepository(conn).get(generation_id)
        status = "succeeded" if record and record.output_audio_path else "failed" if record and record.error_summary else "pending"
        return GenerationRepository(conn).update(generation_id, status=status, deleted_at=None)
    finally:
        conn.close()


def update_generation_favorite(paths: AppPaths, generation_id: str, *, is_favorite: bool) -> GenerationRecord:
    conn = initialize_database(paths)
    try:
        return GenerationRepository(conn).update(generation_id, is_favorite=bool(is_favorite))
    finally:
        conn.close()


def purge_generations(paths: AppPaths, generation_ids: list[str]) -> dict[str, list[str]]:
    conn = initialize_database(paths)
    purged: list[str] = []
    try:
        repo = GenerationRepository(conn)
        records = []
        for generation_id in generation_ids:
            record = repo.get(generation_id)
            if record is None:
                raise KeyError(f"generation not found: {generation_id}")
            if record.deleted_at is None:
                raise ValueError("only trashed generations can be permanently deleted")
            records.append(record)
        for record in records:
            repo.hard_delete(record.id)
            if record.output_audio_path:
                output_path = (paths.project_root / record.output_audio_path).resolve()
                if output_path.exists() and output_path.is_file():
                    output_path.unlink()
            purged.append(record.id)
        return {"purged": purged}
    finally:
        conn.close()


def promote_generation_to_voice(
    paths: AppPaths,
    generation_id: str,
    *,
    display_name: str,
    tags: list[str] | None = None,
    notes: str = "",
) -> dict[str, object]:
    conn = initialize_database(paths)
    try:
        generation = GenerationRepository(conn).get(generation_id)
    finally:
        conn.close()
    if generation is None:
        raise KeyError(f"generation not found: {generation_id}")
    if generation.deleted_at is not None:
        raise ValueError("deleted generations cannot be saved as voices")
    if not generation.output_audio_path:
        raise ValueError("generation has no output audio")

    voice = create_voice(
        paths,
        source_audio_path=generation.output_audio_path,
        display_name=display_name,
        tags=tags or ["generated"],
        notes=notes,
        source="generated",
        source_generation_id=generation.id,
    )
    now = utc_now()
    conn = initialize_database(paths)
    try:
        updated = GenerationRepository(conn).update(
            generation.id,
            saved_voice_id=voice.id,
            promoted_to_voice_at=now,
            hidden_from_history_at=now,
        )
    finally:
        conn.close()
    return {"voice": voice.to_dict(), "generation": updated.to_dict()}
