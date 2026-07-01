from __future__ import annotations

import hashlib
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voxcpm_app.db import initialize_database
from voxcpm_app.generation_history import (
    create_generation,
    delete_generation,
    list_generations,
    mark_generation_failed,
    mark_generation_running,
    mark_generation_succeeded,
)
from voxcpm_app.job_store import (
    create_asset,
    create_generation_job,
    create_generation_take,
    list_assets,
    list_generation_jobs,
    list_generation_takes,
    select_generation_take,
    update_generation_job,
    update_generation_take,
)
from voxcpm_app.paths import AppPaths
from voxcpm_app.voice_library import create_voice, delete_voice, list_voices, update_voice


def test_database_initialization_is_idempotent(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)

    initialize_database(paths).close()
    initialize_database(paths).close()

    assert paths.db_path.exists()
    with sqlite3.connect(paths.db_path) as conn:
        versions = conn.execute("select version from schema_version order by version").fetchall()
        tables = {
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type = 'table' and name in ('voices', 'generations', 'assets', 'generation_jobs', 'generation_takes')"
            )
        }

    assert versions == [(1,), (2,)]
    assert tables == {"voices", "generations", "assets", "generation_jobs", "generation_takes"}
    assert paths.voices_dir.exists()
    assert paths.generations_dir.exists()
    assert paths.tmp_dir.exists()


def test_v1_database_is_additively_migrated_to_v2(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    paths.ensure()
    with sqlite3.connect(paths.db_path) as conn:
        conn.executescript(
            """
            create table schema_version (version integer primary key, applied_at text not null);
            insert into schema_version(version, applied_at) values (1, '2026-01-01T00:00:00Z');
            create table voices (
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
            create table generations (
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
            """
        )

    initialize_database(paths).close()

    with sqlite3.connect(paths.db_path) as conn:
        versions = conn.execute("select version from schema_version order by version").fetchall()
        job_table = conn.execute(
            "select name from sqlite_master where type = 'table' and name = 'generation_jobs'"
        ).fetchone()

    assert versions == [(1,), (2,)]
    assert job_table == ("generation_jobs",)


def test_voice_lifecycle_copies_audio_and_hides_soft_deleted_records(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    source_audio = tmp_path / "uploaded.wav"
    source_audio.write_bytes(b"voice-bytes")

    voice = create_voice(
        paths,
        source_audio_path=source_audio,
        display_name="Studio Narrator",
        tags=["en", "narration"],
        notes="Clean delivery",
        source="upload",
        duration_seconds=1.25,
    )

    stored_path = tmp_path / voice.audio_path
    assert voice.display_name == "Studio Narrator"
    assert voice.tags == ["en", "narration"]
    assert voice.audio_path == f"data/app/voices/{voice.id}.wav"
    assert stored_path.read_bytes() == b"voice-bytes"
    assert voice.audio_sha256 == hashlib.sha256(b"voice-bytes").hexdigest()

    updated = update_voice(
        paths,
        voice.id,
        display_name="Narrator Updated",
        tags=["updated"],
        notes="New note",
    )
    assert updated.display_name == "Narrator Updated"
    assert updated.tags == ["updated"]
    assert updated.notes == "New note"
    assert [item.id for item in list_voices(paths)] == [voice.id]

    deleted = delete_voice(paths, voice.id)
    assert deleted.deleted_at is not None
    assert list_voices(paths) == []
    assert [item.id for item in list_voices(paths, include_deleted=True)] == [voice.id]


def test_generation_lifecycle_copies_output_and_hides_soft_deleted_records(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    generation = create_generation(
        paths,
        input_text="Hello world",
        control_instruction="warm voice",
        voice_id=None,
        reference_audio_path=None,
        prompt_text="",
        cfg_value=2.0,
        inference_timesteps=10,
        normalize=False,
        denoise=True,
    )
    assert generation.status == "pending"

    running = mark_generation_running(paths, generation.id)
    assert running.status == "running"

    output_audio = tmp_path / "result.wav"
    output_audio.write_bytes(b"generated-audio")
    succeeded = mark_generation_succeeded(
        paths,
        generation.id,
        source_output_audio_path=output_audio,
        sample_rate=48000,
    )

    assert succeeded.status == "succeeded"
    assert succeeded.output_audio_path == f"data/app/generations/{generation.id}.wav"
    assert (tmp_path / succeeded.output_audio_path).read_bytes() == b"generated-audio"
    assert succeeded.sample_rate == 48000

    failed = create_generation(
        paths,
        input_text="Bad request",
        control_instruction="",
        voice_id=None,
        reference_audio_path=None,
        prompt_text="",
        cfg_value=2.0,
        inference_timesteps=10,
        normalize=False,
        denoise=False,
    )
    failed = mark_generation_failed(paths, failed.id, error_summary="Model unavailable")
    assert failed.status == "failed"
    assert failed.error_summary == "Model unavailable"
    assert [item.id for item in list_generations(paths)] == [failed.id, generation.id]

    deleted = delete_generation(paths, generation.id)
    assert deleted.status == "deleted"
    assert deleted.deleted_at is not None
    assert [item.id for item in list_generations(paths)] == [failed.id]
    assert {item.id for item in list_generations(paths, include_deleted=True)} == {
        failed.id,
        generation.id,
    }


def test_asset_job_and_take_lifecycle(tmp_path: Path):
    paths = AppPaths.from_project_root(tmp_path)
    output_audio = tmp_path / "take.wav"
    output_audio.write_bytes(b"take-audio")

    asset = create_asset(paths, kind="take_output", path=output_audio, sample_rate=24000)
    job = create_generation_job(
        paths,
        backend_id="indextts2",
        model_id="IndexTTS2",
        mode="line_performance",
        input_text="Line one",
        params={"emotion_mode": "same_voice"},
    )
    take_one = create_generation_take(
        paths,
        job_id=job.id,
        backend_id="indextts2",
        take_index=1,
        label="Take 1",
        status="succeeded",
        output_asset_id=asset.id,
    )
    take_two = create_generation_take(
        paths,
        job_id=job.id,
        backend_id="indextts2",
        take_index=2,
        label="Take 2",
        status="succeeded",
    )

    selected_one = select_generation_take(paths, take_one.id)
    selected_two = select_generation_take(paths, take_two.id)
    updated_job = update_generation_job(paths, job.id, status="succeeded", output_asset_id=asset.id)
    failed_take = update_generation_take(paths, take_two.id, status="failed", error_summary="bad take")

    takes = list_generation_takes(paths, job.id)
    assert asset.path == "take.wav"
    assert list_assets(paths)[0].id == asset.id
    assert list_generation_jobs(paths)[0].id == job.id
    assert selected_one.is_selected is True
    assert selected_two.is_selected is True
    assert [item.is_selected for item in takes] == [False, True]
    assert updated_job.status == "succeeded"
    assert failed_take.error_summary == "bad take"
