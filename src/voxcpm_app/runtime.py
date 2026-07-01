from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Iterator


@dataclass(frozen=True)
class RuntimeBackendStatus:
    backend_id: str
    display_name: str
    enabled: bool
    configured: bool
    loaded: bool
    busy: bool
    device: str
    last_error: str
    capabilities: list[str]
    active_job_id: str | None = None
    started_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class RuntimeCoordinator:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_backend: str | None = None
        self._active_job_id: str | None = None
        self._started_at: str | None = None
        self._last_error: dict[str, str] = {}

    @contextmanager
    def lease(self, backend_id: str, *, job_id: str | None = None) -> Iterator[None]:
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            active = self._active_backend or "another backend"
            raise RuntimeError(f"runtime busy: {active}")
        self._active_backend = backend_id
        self._active_job_id = job_id
        self._started_at = _utc_now()
        try:
            yield
            self._last_error[backend_id] = ""
        except Exception as exc:
            self._last_error[backend_id] = str(exc).splitlines()[0][:500]
            raise
        finally:
            self._active_backend = None
            self._active_job_id = None
            self._started_at = None
            self._lock.release()

    def is_busy(self) -> bool:
        return self._lock.locked()

    def is_busy_backend(self, backend_id: str) -> bool:
        return self._active_backend == backend_id

    def last_error(self, backend_id: str) -> str:
        return self._last_error.get(backend_id, "")

    def status(self, backend_id: str) -> dict[str, object]:
        return {
            "busy": self.is_busy_backend(backend_id),
            "active_job_id": self._active_job_id if self._active_backend == backend_id else None,
            "started_at": self._started_at if self._active_backend == backend_id else None,
            "last_error": self.last_error(backend_id),
        }


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


RUNTIME_COORDINATOR = RuntimeCoordinator()
