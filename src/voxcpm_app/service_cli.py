from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .generation_history import (
    create_generation,
    delete_generation,
    list_generations,
    mark_generation_failed,
    mark_generation_running,
    mark_generation_succeeded,
)
from .paths import AppPaths, default_project_root
from .voice_library import create_voice, delete_voice, list_voices, update_voice


Handler = Callable[[AppPaths, dict[str, Any]], dict[str, Any]]


def _items(records: list[Any]) -> dict[str, Any]:
    return {"items": [record.to_dict() for record in records]}


def _list_voices(paths: AppPaths, payload: dict[str, Any]) -> dict[str, Any]:
    return _items(list_voices(paths, include_deleted=bool(payload.get("include_deleted", False))))


def _create_voice(paths: AppPaths, payload: dict[str, Any]) -> dict[str, Any]:
    return create_voice(
        paths,
        source_audio_path=payload["source_audio_path"],
        display_name=payload["display_name"],
        tags=payload.get("tags") or [],
        notes=payload.get("notes") or "",
        source=payload.get("source") or "upload",
        duration_seconds=payload.get("duration_seconds"),
    ).to_dict()


def _update_voice(paths: AppPaths, payload: dict[str, Any]) -> dict[str, Any]:
    return update_voice(
        paths,
        payload["id"],
        display_name=payload["display_name"],
        tags=payload.get("tags") or [],
        notes=payload.get("notes") or "",
    ).to_dict()


def _delete_voice(paths: AppPaths, payload: dict[str, Any]) -> dict[str, Any]:
    return delete_voice(paths, payload["id"]).to_dict()


def _list_generations(paths: AppPaths, payload: dict[str, Any]) -> dict[str, Any]:
    return _items(list_generations(paths, include_deleted=bool(payload.get("include_deleted", False))))


def _create_generation(paths: AppPaths, payload: dict[str, Any]) -> dict[str, Any]:
    return create_generation(
        paths,
        input_text=payload["input_text"],
        control_instruction=payload.get("control_instruction") or "",
        voice_id=payload.get("voice_id"),
        reference_audio_path=payload.get("reference_audio_path"),
        prompt_text=payload.get("prompt_text") or "",
        cfg_value=payload.get("cfg_value", 2.0),
        inference_timesteps=payload.get("inference_timesteps", 10),
        normalize=payload.get("normalize", False),
        denoise=payload.get("denoise", False),
    ).to_dict()


def _mark_generation_running(paths: AppPaths, payload: dict[str, Any]) -> dict[str, Any]:
    return mark_generation_running(paths, payload["id"]).to_dict()


def _mark_generation_succeeded(paths: AppPaths, payload: dict[str, Any]) -> dict[str, Any]:
    return mark_generation_succeeded(
        paths,
        payload["id"],
        source_output_audio_path=payload["source_output_audio_path"],
        sample_rate=payload["sample_rate"],
    ).to_dict()


def _mark_generation_failed(paths: AppPaths, payload: dict[str, Any]) -> dict[str, Any]:
    return mark_generation_failed(paths, payload["id"], error_summary=payload.get("error_summary") or "").to_dict()


def _delete_generation(paths: AppPaths, payload: dict[str, Any]) -> dict[str, Any]:
    return delete_generation(paths, payload["id"]).to_dict()


ACTIONS: dict[str, Handler] = {
    "list-voices": _list_voices,
    "create-voice": _create_voice,
    "update-voice": _update_voice,
    "delete-voice": _delete_voice,
    "list-generations": _list_generations,
    "create-generation": _create_generation,
    "mark-generation-running": _mark_generation_running,
    "mark-generation-succeeded": _mark_generation_succeeded,
    "mark-generation-failed": _mark_generation_failed,
    "delete-generation": _delete_generation,
}


def _read_payload() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")
    return payload


def _write_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VoxCPM-Box local app service CLI")
    parser.add_argument("action")
    parser.add_argument("--project-root", default=str(default_project_root()))
    args = parser.parse_args(argv)

    handler = ACTIONS.get(args.action)
    if handler is None:
        _write_json({"error": f"unknown action: {args.action}"})
        return 2

    try:
        payload = _read_payload()
        paths = AppPaths.from_project_root(Path(args.project_root))
        _write_json(handler(paths, payload))
        return 0
    except Exception as exc:
        _write_json({"error": str(exc), "type": type(exc).__name__})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
