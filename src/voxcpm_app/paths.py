from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    project_root: Path

    @classmethod
    def from_project_root(cls, project_root: str | Path) -> "AppPaths":
        return cls(Path(project_root).resolve())

    @property
    def app_root(self) -> Path:
        return self.project_root / "data" / "app"

    @property
    def db_path(self) -> Path:
        return self.app_root / "app.sqlite3"

    @property
    def voices_dir(self) -> Path:
        return self.app_root / "voices"

    @property
    def generations_dir(self) -> Path:
        return self.app_root / "generations"

    @property
    def tmp_dir(self) -> Path:
        return self.app_root / "tmp"

    def ensure(self) -> None:
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self.generations_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def project_relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.project_root).as_posix()


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_app_paths() -> AppPaths:
    return AppPaths.from_project_root(default_project_root())

