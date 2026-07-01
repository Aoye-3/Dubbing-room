from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from .paths import AppPaths


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def initialize_database(paths: AppPaths) -> sqlite3.Connection:
    paths.ensure()
    conn = sqlite3.connect(paths.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    conn.executescript(
        """
        create table if not exists schema_version (
            version integer primary key,
            applied_at text not null
        );

        create table if not exists voices (
            id text primary key,
            display_name text not null,
            tags text not null default '[]',
            notes text not null default '',
            source text not null default 'upload',
            audio_path text not null,
            audio_sha256 text not null,
            duration_seconds real,
            created_at text not null,
            updated_at text not null,
            last_used_at text,
            deleted_at text
        );

        create table if not exists generations (
            id text primary key,
            input_text text not null,
            control_instruction text not null default '',
            voice_id text,
            reference_audio_path text,
            prompt_text text not null default '',
            cfg_value real not null,
            inference_timesteps integer not null,
            normalize integer not null,
            denoise integer not null,
            output_audio_path text,
            sample_rate integer,
            status text not null,
            error_summary text not null default '',
            created_at text not null,
            updated_at text not null,
            deleted_at text
        );

        create index if not exists idx_voices_deleted_at on voices(deleted_at);
        create index if not exists idx_generations_deleted_at on generations(deleted_at);
        create index if not exists idx_generations_created_at on generations(created_at);

        create table if not exists assets (
            id text primary key,
            kind text not null,
            path text not null,
            sha256 text not null,
            mime_type text not null,
            duration_seconds real,
            sample_rate integer,
            created_at text not null,
            deleted_at text
        );

        create table if not exists generation_jobs (
            id text primary key,
            backend_id text not null,
            model_id text not null,
            mode text not null,
            status text not null,
            input_text text not null,
            voice_id text,
            params_json text not null default '{}',
            output_asset_id text,
            error_summary text not null default '',
            legacy_generation_id text,
            created_at text not null,
            updated_at text not null,
            deleted_at text,
            foreign key(output_asset_id) references assets(id)
        );

        create table if not exists generation_takes (
            id text primary key,
            job_id text not null,
            backend_id text not null,
            take_index integer not null,
            label text not null default '',
            status text not null,
            params_json text not null default '{}',
            output_asset_id text,
            is_selected integer not null default 0,
            error_summary text not null default '',
            created_at text not null,
            updated_at text not null,
            foreign key(job_id) references generation_jobs(id),
            foreign key(output_asset_id) references assets(id)
        );

        create index if not exists idx_assets_deleted_at on assets(deleted_at);
        create index if not exists idx_generation_jobs_status on generation_jobs(status);
        create index if not exists idx_generation_jobs_created_at on generation_jobs(created_at);
        create index if not exists idx_generation_takes_job_id on generation_takes(job_id);
        create unique index if not exists idx_generation_takes_selected
            on generation_takes(job_id)
            where is_selected = 1;
        """
    )
    conn.execute(
        "insert or ignore into schema_version(version, applied_at) values (?, ?)",
        (1, utc_now()),
    )
    conn.execute(
        "insert or ignore into schema_version(version, applied_at) values (?, ?)",
        (2, utc_now()),
    )
    conn.commit()
    return conn

