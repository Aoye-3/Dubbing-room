from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def run_service_cli(project_root: Path, action: str, payload: dict | None = None):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "voxcpm_app.service_cli",
            action,
            "--project-root",
            str(project_root),
        ],
        input=json.dumps(payload or {}),
        capture_output=True,
        text=True,
        env=env,
    )


def read_json_stdout(proc: subprocess.CompletedProcess[str]) -> dict:
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_service_cli_lists_and_creates_voices(tmp_path: Path):
    empty = read_json_stdout(run_service_cli(tmp_path, "list-voices"))
    assert empty == {"items": []}

    source_audio = tmp_path / "reference.m4a"
    source_audio.write_bytes(b"reference-audio")
    created = read_json_stdout(
        run_service_cli(
            tmp_path,
            "create-voice",
            {
                "source_audio_path": str(source_audio),
                "display_name": "Reference Voice",
                "tags": ["zh"],
                "notes": "Reusable",
                "source": "upload",
            },
        )
    )

    assert created["display_name"] == "Reference Voice"
    assert created["audio_path"].endswith(".m4a")

    listed = read_json_stdout(run_service_cli(tmp_path, "list-voices"))
    assert [item["id"] for item in listed["items"]] == [created["id"]]


def test_service_cli_generation_status_flow_and_errors_are_json(tmp_path: Path):
    created = read_json_stdout(
        run_service_cli(
            tmp_path,
            "create-generation",
            {
                "input_text": "Hello",
                "control_instruction": "",
                "voice_id": None,
                "reference_audio_path": None,
                "prompt_text": "",
                "cfg_value": 2.0,
                "inference_timesteps": 10,
                "normalize": False,
                "denoise": False,
            },
        )
    )
    assert created["status"] == "pending"

    running = read_json_stdout(run_service_cli(tmp_path, "mark-generation-running", {"id": created["id"]}))
    assert running["status"] == "running"

    output_audio = tmp_path / "output.wav"
    output_audio.write_bytes(b"result")
    succeeded = read_json_stdout(
        run_service_cli(
            tmp_path,
            "mark-generation-succeeded",
            {
                "id": created["id"],
                "source_output_audio_path": str(output_audio),
                "sample_rate": 48000,
            },
        )
    )
    assert succeeded["status"] == "succeeded"
    assert succeeded["output_audio_path"] == f"data/app/generations/{created['id']}.wav"

    failed = run_service_cli(tmp_path, "missing-action")
    assert failed.returncode == 2
    assert json.loads(failed.stdout)["error"]
