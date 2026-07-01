from __future__ import annotations

import json
import sqlite3
from dataclasses import replace

from .db import utc_now
from .schemas import AssetRecord, GenerationJobRecord, GenerationRecord, GenerationTakeRecord, VoiceRecord


def _voice_from_row(row: sqlite3.Row) -> VoiceRecord:
    return VoiceRecord(
        id=row["id"],
        display_name=row["display_name"],
        tags=json.loads(row["tags"]),
        notes=row["notes"],
        source=row["source"],
        audio_path=row["audio_path"],
        audio_sha256=row["audio_sha256"],
        duration_seconds=row["duration_seconds"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_used_at=row["last_used_at"],
        deleted_at=row["deleted_at"],
    )


def _generation_from_row(row: sqlite3.Row) -> GenerationRecord:
    return GenerationRecord(
        id=row["id"],
        input_text=row["input_text"],
        control_instruction=row["control_instruction"],
        voice_id=row["voice_id"],
        reference_audio_path=row["reference_audio_path"],
        prompt_text=row["prompt_text"],
        cfg_value=row["cfg_value"],
        inference_timesteps=row["inference_timesteps"],
        normalize=bool(row["normalize"]),
        denoise=bool(row["denoise"]),
        output_audio_path=row["output_audio_path"],
        sample_rate=row["sample_rate"],
        status=row["status"],
        error_summary=row["error_summary"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
    )


def _asset_from_row(row: sqlite3.Row) -> AssetRecord:
    return AssetRecord(
        id=row["id"],
        kind=row["kind"],
        path=row["path"],
        sha256=row["sha256"],
        mime_type=row["mime_type"],
        duration_seconds=row["duration_seconds"],
        sample_rate=row["sample_rate"],
        created_at=row["created_at"],
        deleted_at=row["deleted_at"],
    )


def _job_from_row(row: sqlite3.Row) -> GenerationJobRecord:
    return GenerationJobRecord(
        id=row["id"],
        backend_id=row["backend_id"],
        model_id=row["model_id"],
        mode=row["mode"],
        status=row["status"],
        input_text=row["input_text"],
        voice_id=row["voice_id"],
        params_json=row["params_json"],
        output_asset_id=row["output_asset_id"],
        error_summary=row["error_summary"],
        legacy_generation_id=row["legacy_generation_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
    )


def _take_from_row(row: sqlite3.Row) -> GenerationTakeRecord:
    return GenerationTakeRecord(
        id=row["id"],
        job_id=row["job_id"],
        backend_id=row["backend_id"],
        take_index=row["take_index"],
        label=row["label"],
        status=row["status"],
        params_json=row["params_json"],
        output_asset_id=row["output_asset_id"],
        is_selected=bool(row["is_selected"]),
        error_summary=row["error_summary"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class VoiceRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert(self, record: VoiceRecord) -> VoiceRecord:
        self.conn.execute(
            """
            insert into voices (
                id, display_name, tags, notes, source, audio_path, audio_sha256,
                duration_seconds, created_at, updated_at, last_used_at, deleted_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.display_name,
                json.dumps(record.tags, ensure_ascii=False),
                record.notes,
                record.source,
                record.audio_path,
                record.audio_sha256,
                record.duration_seconds,
                record.created_at,
                record.updated_at,
                record.last_used_at,
                record.deleted_at,
            ),
        )
        self.conn.commit()
        return record

    def get(self, voice_id: str) -> VoiceRecord | None:
        row = self.conn.execute("select * from voices where id = ?", (voice_id,)).fetchone()
        return _voice_from_row(row) if row else None

    def list(self, include_deleted: bool = False) -> list[VoiceRecord]:
        sql = "select * from voices"
        if not include_deleted:
            sql += " where deleted_at is null"
        sql += " order by created_at desc, rowid desc"
        return [_voice_from_row(row) for row in self.conn.execute(sql)]

    def update(self, voice_id: str, **fields: object) -> VoiceRecord:
        current = self.get(voice_id)
        if current is None:
            raise KeyError(f"voice not found: {voice_id}")
        updated = replace(current, updated_at=utc_now(), **fields)
        self.conn.execute(
            """
            update voices
            set display_name = ?, tags = ?, notes = ?, updated_at = ?
            where id = ?
            """,
            (
                updated.display_name,
                json.dumps(updated.tags, ensure_ascii=False),
                updated.notes,
                updated.updated_at,
                voice_id,
            ),
        )
        self.conn.commit()
        return updated

    def soft_delete(self, voice_id: str) -> VoiceRecord:
        current = self.get(voice_id)
        if current is None:
            raise KeyError(f"voice not found: {voice_id}")
        deleted = replace(current, deleted_at=utc_now(), updated_at=utc_now())
        self.conn.execute(
            "update voices set deleted_at = ?, updated_at = ? where id = ?",
            (deleted.deleted_at, deleted.updated_at, voice_id),
        )
        self.conn.commit()
        return deleted

    def mark_used(self, voice_id: str) -> VoiceRecord:
        current = self.get(voice_id)
        if current is None:
            raise KeyError(f"voice not found: {voice_id}")
        now = utc_now()
        updated = replace(current, last_used_at=now, updated_at=now)
        self.conn.execute(
            "update voices set last_used_at = ?, updated_at = ? where id = ?",
            (updated.last_used_at, updated.updated_at, voice_id),
        )
        self.conn.commit()
        return updated


class AssetRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert(self, record: AssetRecord) -> AssetRecord:
        self.conn.execute(
            """
            insert into assets (
                id, kind, path, sha256, mime_type, duration_seconds,
                sample_rate, created_at, deleted_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.kind,
                record.path,
                record.sha256,
                record.mime_type,
                record.duration_seconds,
                record.sample_rate,
                record.created_at,
                record.deleted_at,
            ),
        )
        self.conn.commit()
        return record

    def get(self, asset_id: str) -> AssetRecord | None:
        row = self.conn.execute("select * from assets where id = ?", (asset_id,)).fetchone()
        return _asset_from_row(row) if row else None

    def list(self, include_deleted: bool = False) -> list[AssetRecord]:
        sql = "select * from assets"
        if not include_deleted:
            sql += " where deleted_at is null"
        sql += " order by created_at desc, rowid desc"
        return [_asset_from_row(row) for row in self.conn.execute(sql)]


class GenerationJobRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert(self, record: GenerationJobRecord) -> GenerationJobRecord:
        self.conn.execute(
            """
            insert into generation_jobs (
                id, backend_id, model_id, mode, status, input_text, voice_id,
                params_json, output_asset_id, error_summary, legacy_generation_id,
                created_at, updated_at, deleted_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.backend_id,
                record.model_id,
                record.mode,
                record.status,
                record.input_text,
                record.voice_id,
                record.params_json,
                record.output_asset_id,
                record.error_summary,
                record.legacy_generation_id,
                record.created_at,
                record.updated_at,
                record.deleted_at,
            ),
        )
        self.conn.commit()
        return record

    def get(self, job_id: str) -> GenerationJobRecord | None:
        row = self.conn.execute("select * from generation_jobs where id = ?", (job_id,)).fetchone()
        return _job_from_row(row) if row else None

    def list(self, include_deleted: bool = False) -> list[GenerationJobRecord]:
        sql = "select * from generation_jobs"
        if not include_deleted:
            sql += " where deleted_at is null"
        sql += " order by created_at desc, rowid desc"
        return [_job_from_row(row) for row in self.conn.execute(sql)]

    def update(self, job_id: str, **fields: object) -> GenerationJobRecord:
        current = self.get(job_id)
        if current is None:
            raise KeyError(f"generation job not found: {job_id}")
        updated = replace(current, updated_at=utc_now(), **fields)
        self.conn.execute(
            """
            update generation_jobs
            set status = ?, output_asset_id = ?, error_summary = ?,
                legacy_generation_id = ?, updated_at = ?, deleted_at = ?
            where id = ?
            """,
            (
                updated.status,
                updated.output_asset_id,
                updated.error_summary,
                updated.legacy_generation_id,
                updated.updated_at,
                updated.deleted_at,
                job_id,
            ),
        )
        self.conn.commit()
        return updated

class GenerationTakeRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert(self, record: GenerationTakeRecord) -> GenerationTakeRecord:
        self.conn.execute(
            """
            insert into generation_takes (
                id, job_id, backend_id, take_index, label, status, params_json,
                output_asset_id, is_selected, error_summary, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.job_id,
                record.backend_id,
                record.take_index,
                record.label,
                record.status,
                record.params_json,
                record.output_asset_id,
                int(record.is_selected),
                record.error_summary,
                record.created_at,
                record.updated_at,
            ),
        )
        self.conn.commit()
        return record

    def get(self, take_id: str) -> GenerationTakeRecord | None:
        row = self.conn.execute("select * from generation_takes where id = ?", (take_id,)).fetchone()
        return _take_from_row(row) if row else None

    def list_for_job(self, job_id: str) -> list[GenerationTakeRecord]:
        rows = self.conn.execute(
            "select * from generation_takes where job_id = ? order by take_index asc, rowid asc",
            (job_id,),
        )
        return [_take_from_row(row) for row in rows]

    def update(self, take_id: str, **fields: object) -> GenerationTakeRecord:
        current = self.get(take_id)
        if current is None:
            raise KeyError(f"generation take not found: {take_id}")
        updated = replace(current, updated_at=utc_now(), **fields)
        self.conn.execute(
            """
            update generation_takes
            set label = ?, status = ?, output_asset_id = ?, is_selected = ?,
                error_summary = ?, updated_at = ?
            where id = ?
            """,
            (
                updated.label,
                updated.status,
                updated.output_asset_id,
                int(updated.is_selected),
                updated.error_summary,
                updated.updated_at,
                take_id,
            ),
        )
        self.conn.commit()
        return updated

    def select(self, take_id: str) -> GenerationTakeRecord:
        current = self.get(take_id)
        if current is None:
            raise KeyError(f"generation take not found: {take_id}")
        now = utc_now()
        self.conn.execute("update generation_takes set is_selected = 0, updated_at = ? where job_id = ?", (now, current.job_id))
        self.conn.execute("update generation_takes set is_selected = 1, updated_at = ? where id = ?", (now, take_id))
        self.conn.commit()
        selected = self.get(take_id)
        if selected is None:
            raise KeyError(f"generation take not found: {take_id}")
        return selected

class GenerationRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert(self, record: GenerationRecord) -> GenerationRecord:
        self.conn.execute(
            """
            insert into generations (
                id, input_text, control_instruction, voice_id, reference_audio_path,
                prompt_text, cfg_value, inference_timesteps, normalize, denoise,
                output_audio_path, sample_rate, status, error_summary, created_at,
                updated_at, deleted_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.input_text,
                record.control_instruction,
                record.voice_id,
                record.reference_audio_path,
                record.prompt_text,
                record.cfg_value,
                record.inference_timesteps,
                int(record.normalize),
                int(record.denoise),
                record.output_audio_path,
                record.sample_rate,
                record.status,
                record.error_summary,
                record.created_at,
                record.updated_at,
                record.deleted_at,
            ),
        )
        self.conn.commit()
        return record

    def get(self, generation_id: str) -> GenerationRecord | None:
        row = self.conn.execute("select * from generations where id = ?", (generation_id,)).fetchone()
        return _generation_from_row(row) if row else None

    def list(self, include_deleted: bool = False) -> list[GenerationRecord]:
        sql = "select * from generations"
        if not include_deleted:
            sql += " where deleted_at is null"
        sql += " order by created_at desc, rowid desc"
        return [_generation_from_row(row) for row in self.conn.execute(sql)]

    def update(self, generation_id: str, **fields: object) -> GenerationRecord:
        current = self.get(generation_id)
        if current is None:
            raise KeyError(f"generation not found: {generation_id}")
        updated = replace(current, updated_at=utc_now(), **fields)
        self.conn.execute(
            """
            update generations
            set output_audio_path = ?, sample_rate = ?, status = ?, error_summary = ?,
                updated_at = ?, deleted_at = ?
            where id = ?
            """,
            (
                updated.output_audio_path,
                updated.sample_rate,
                updated.status,
                updated.error_summary,
                updated.updated_at,
                updated.deleted_at,
                generation_id,
            ),
        )
        self.conn.commit()
        return updated

