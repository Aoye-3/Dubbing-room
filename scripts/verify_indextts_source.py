"""Verify the pinned IndexTTS vendored source against its source manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_excluded(relative_path: str, excluded_paths: set[str]) -> bool:
    return any(
        relative_path == excluded.rstrip("/")
        or (excluded.endswith("/") and relative_path.startswith(excluded))
        for excluded in excluded_paths
    )


def verify(manifest_path: Path) -> list[str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_root = manifest_path.parent
    excluded_paths = set(manifest["excluded_paths"])
    expected_hashes = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
    mapped_files = [entry for entry in manifest["files"] if "upstream_path" in entry]
    issues: list[str] = []

    for relative_path in sorted(expected_hashes):
        source_path = source_root / relative_path
        if not source_path.is_file():
            issues.append(f"missing: {relative_path}")
            continue
        if sha256(source_path) != expected_hashes[relative_path]:
            issues.append(f"modified: {relative_path}")

    actual_paths = {
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*")
        if path.is_file()
        and not is_excluded(path.relative_to(source_root).as_posix(), excluded_paths)
    }
    for relative_path in sorted(actual_paths - expected_hashes.keys()):
        issues.append(f"extra: {relative_path}")

    license_path = manifest["license"]["path"]
    expected_license_hash = manifest["license"]["sha256"]
    local_license = source_root / license_path
    if not local_license.is_file():
        issues.append(f"license missing: {license_path}")
    elif sha256(local_license) != expected_license_hash:
        issues.append(f"license modified: {license_path}")

    if not issues:
        issues.append(f"verified {len(expected_hashes)} upstream files")
        issues.extend(
            f"mapped upstream: {entry['upstream_path']} -> {entry['path']}"
            for entry in mapped_files
        )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "third_party"
        / "index-tts"
        / "SOURCE_MANIFEST.json",
    )
    args = parser.parse_args()
    issues = verify(args.manifest.resolve())
    for issue in issues:
        print(issue)
    return 0 if issues[0].startswith("verified ") else 1


if __name__ == "__main__":
    raise SystemExit(main())
