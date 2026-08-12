"""Generate the machine-readable manifest for the pinned IndexTTS source."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "third_party" / "index-tts"
MANIFEST_PATH = SOURCE_ROOT / "SOURCE_MANIFEST.json"
EXCLUDED_PATHS = {
    "SOURCE_MANIFEST.json",
    "checkpoints/",
    "checkpoints-2.5/README.md",
}
MAPPED_FILE = {
    "upstream_path": "checkpoints/pinyin.vocab",
    "path": "checkpoints-2.5/pinyin.vocab",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_excluded(relative_path: str) -> bool:
    return any(
        relative_path == excluded.rstrip("/")
        or (excluded.endswith("/") and relative_path.startswith(excluded))
        for excluded in EXCLUDED_PATHS
    )


def main() -> None:
    files = [
        {"path": relative_path, "sha256": sha256(path)}
        for path in sorted(SOURCE_ROOT.rglob("*"))
        if path.is_file()
        and not is_excluded(relative_path := path.relative_to(SOURCE_ROOT).as_posix())
        and relative_path != MAPPED_FILE["path"]
    ]
    files.append({**MAPPED_FILE, "sha256": sha256(SOURCE_ROOT / MAPPED_FILE["path"])})
    manifest = {
        "schema_version": 1,
        "upstream": {
            "repository": "https://github.com/index-tts/index-tts",
            "commit": "a371df7d0746a0ae7fdf075798b6b04e34a0132e",
            "tree": "fcc06dd0f745c60d35722e663c6cfec3a35fabb2",
            "acquired_on": "2026-08-12",
        },
        "license": {"path": "LICENSE", "sha256": sha256(SOURCE_ROOT / "LICENSE")},
        "excluded_paths": sorted(EXCLUDED_PATHS),
        "files": files,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
