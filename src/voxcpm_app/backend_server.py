from __future__ import annotations

import argparse
import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .errors import AppBackendError
from .generation_service import GenerationService
from .indextts2_service import IndexTTS2Service
from .job_queue import GenerationJobQueue, job_to_dict
from .job_store import (
    generation_take_to_dict,
    get_generation_job,
    list_generation_jobs,
    list_generation_takes,
    select_take_and_project,
)
from .paths import AppPaths, default_project_root
from .service_cli import ACTIONS


def build_handler(
    paths: AppPaths,
    *,
    generation_service: GenerationService | None = None,
    indextts2_service: IndexTTS2Service | None = None,
):
    service = generation_service or GenerationService(paths)
    index_service = indextts2_service or IndexTTS2Service(paths, coordinator=service.coordinator)
    job_queue = GenerationJobQueue(paths, service, index_service)

    class BackendHandler(BaseHTTPRequestHandler):
        server_version = "VoxCPMAppBackend/0.1"

        def do_GET(self) -> None:
            try:
                parsed = urlparse(self.path)
                if parsed.path == "/health":
                    self._write_json(HTTPStatus.OK, {"ok": True})
                    return
                if parsed.path == "/runtime-backends":
                    self._write_json(
                        HTTPStatus.OK,
                        {
                            "items": [
                                service.runtime_status().to_dict(),
                                index_service.runtime_status().to_dict(),
                            ]
                        },
                    )
                    return
                if parsed.path == "/generation-jobs":
                    self._write_json(
                        HTTPStatus.OK,
                        {"items": [job_to_dict(job) for job in list_generation_jobs(paths)]},
                    )
                    return
                if parsed.path.startswith("/generation-jobs/"):
                    self._handle_generation_job_get(parsed.path)
                    return
                if parsed.path == "/media":
                    self._serve_media(parsed.query)
                    return
                self._write_error(HTTPStatus.NOT_FOUND, "not found", "not_found")
            except (FileNotFoundError, KeyError, ValueError) as exc:
                self._write_exception(exc)
            except Exception as exc:
                self._write_exception(exc, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                payload = self._read_json()
                if parsed.path == "/app-service":
                    self._handle_app_service(payload)
                    return
                if parsed.path == "/generate-audio":
                    record = service.generate_audio(payload)
                    self._write_json(HTTPStatus.OK, record.to_dict())
                    return
                if parsed.path == "/indextts2/generate":
                    record = index_service.generate(payload)
                    self._write_json(HTTPStatus.OK, record.to_dict())
                    return
                if parsed.path == "/generation-jobs":
                    job = job_queue.submit(payload)
                    self._write_json(HTTPStatus.OK, job_to_dict(job))
                    return
                if parsed.path.startswith("/generation-jobs/"):
                    self._handle_generation_job_post(parsed.path)
                    return
                if parsed.path.startswith("/generation-takes/"):
                    self._handle_generation_take_post(parsed.path)
                    return
                if parsed.path.startswith("/runtime-backends/"):
                    self._handle_runtime_backend_post(parsed.path)
                    return
                self._write_error(HTTPStatus.NOT_FOUND, "not found", "not_found")
            except (FileNotFoundError, KeyError, ValueError) as exc:
                self._write_exception(exc)
            except Exception as exc:
                self._write_exception(exc, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _handle_app_service(self, payload: dict[str, Any]) -> None:
            action = payload.get("action")
            if not isinstance(action, str) or action not in ACTIONS:
                raise ValueError(f"unsupported app service action: {action}")
            action_payload = payload.get("payload")
            if action_payload is None:
                action_payload = {}
            if not isinstance(action_payload, dict):
                raise ValueError("app service payload must be an object")
            self._write_json(HTTPStatus.OK, ACTIONS[action](paths, action_payload))

        def _handle_generation_job_get(self, path: str) -> None:
            parts = _path_parts(path)
            if len(parts) == 2:
                job = get_generation_job(paths, parts[1])
                if job is None:
                    raise KeyError(f"generation job not found: {parts[1]}")
                self._write_json(HTTPStatus.OK, job_to_dict(job))
                return
            if len(parts) == 3 and parts[2] == "takes":
                self._write_json(
                    HTTPStatus.OK,
                    {"items": [generation_take_to_dict(paths, take) for take in list_generation_takes(paths, parts[1])]},
                )
                return
            self._write_error(HTTPStatus.NOT_FOUND, "not found", "not_found")

        def _handle_generation_job_post(self, path: str) -> None:
            parts = _path_parts(path)
            if len(parts) == 3 and parts[2] == "cancel":
                self._write_json(HTTPStatus.OK, job_to_dict(job_queue.cancel(parts[1])))
                return
            if len(parts) == 3 and parts[2] == "retry":
                self._write_json(HTTPStatus.OK, job_to_dict(job_queue.retry(parts[1])))
                return
            self._write_error(HTTPStatus.NOT_FOUND, "not found", "not_found")

        def _handle_generation_take_post(self, path: str) -> None:
            parts = _path_parts(path)
            if len(parts) == 3 and parts[2] == "select":
                self._write_json(HTTPStatus.OK, generation_take_to_dict(paths, select_take_and_project(paths, parts[1])))
                return
            self._write_error(HTTPStatus.NOT_FOUND, "not found", "not_found")

        def _handle_runtime_backend_post(self, path: str) -> None:
            parts = _path_parts(path)
            if len(parts) == 3 and parts[2] == "unload":
                self._write_json(HTTPStatus.OK, {"ok": True, "backend_id": parts[1], "unloaded": False})
                return
            self._write_error(HTTPStatus.NOT_FOUND, "not found", "not_found")

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(raw or "{}")
            if not isinstance(payload, dict):
                raise ValueError("JSON payload must be an object")
            return payload

        def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _write_error(
            self,
            status: HTTPStatus,
            message: str,
            code: str,
            *,
            error_type: str = "AppBackendError",
            details: dict[str, Any] | None = None,
        ) -> None:
            self._write_json(
                status,
                {
                    "error": message,
                    "type": error_type,
                    "code": code,
                    "details": details or {},
                },
            )

        def _write_exception(self, exc: Exception, *, status: HTTPStatus | None = None) -> None:
            error_status = status or _http_status_for_exception(exc)
            self._write_error(
                error_status,
                str(exc),
                _error_code_for_exception(exc),
                error_type=type(exc).__name__,
                details=exc.details if isinstance(exc, AppBackendError) else None,
            )

        def _serve_media(self, query: str) -> None:
            value = parse_qs(query).get("path", [""])[0]
            if not value:
                self._write_error(HTTPStatus.BAD_REQUEST, "path is required", "validation_error")
                return
            root = paths.project_root.resolve()
            media_path = (root / value).resolve()
            if root != media_path and root not in media_path.parents:
                self._write_error(HTTPStatus.BAD_REQUEST, "path is outside project", "validation_error")
                return
            if not media_path.exists() or not media_path.is_file():
                self._write_error(HTTPStatus.NOT_FOUND, "media not found", "media_not_found")
                return

            content_type = mimetypes.guess_type(media_path.name)[0] or "application/octet-stream"
            data = media_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return BackendHandler


def _path_parts(path: str) -> list[str]:
    return [part for part in path.strip("/").split("/") if part]


def _http_status_for_exception(exc: Exception) -> HTTPStatus:
    if isinstance(exc, KeyError):
        return HTTPStatus.NOT_FOUND
    return HTTPStatus.BAD_REQUEST


def _error_code_for_exception(exc: Exception) -> str:
    if isinstance(exc, AppBackendError):
        return exc.code
    text = str(exc).lower()
    if isinstance(exc, KeyError):
        return "not_found"
    if "runtime busy" in text:
        return "runtime_busy"
    if "checkpoint" in text:
        return "checkpoints_missing"
    if "runtime python" in text or "runtime" in text and "configured" in text:
        return "runtime_missing"
    if "worker" in text:
        return "worker_failed"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "output" in text and "missing" in text:
        return "output_missing"
    return "validation_error"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VoxCPM-Box AppShell backend")
    parser.add_argument("--project-root", default=str(default_project_root()))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8818)
    parser.add_argument("--model-id", default=os.environ.get("VOXCPM_APP_MODEL_ID", "openbmb/VoxCPM2"))
    parser.add_argument("--device", default=os.environ.get("VOXCPM_APP_DEVICE", "cuda"))
    args = parser.parse_args(argv)

    paths = AppPaths.from_project_root(Path(args.project_root))
    _prepend_local_ffmpeg(paths.project_root)
    service = GenerationService(paths, model_id=args.model_id, device=args.device)
    server = ThreadingHTTPServer((args.host, args.port), build_handler(paths, generation_service=service))
    print(json.dumps({"ok": True, "host": args.host, "port": args.port}, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _prepend_local_ffmpeg(project_root: Path) -> None:
    ffmpeg = project_root / ".local-ffmpeg" / "ffmpeg.exe"
    if not ffmpeg.exists():
        return
    os.environ["PATH"] = str(ffmpeg.parent) + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("IMAGEIO_FFMPEG_EXE", str(ffmpeg))


if __name__ == "__main__":
    raise SystemExit(main())
