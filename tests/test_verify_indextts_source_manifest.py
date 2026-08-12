import hashlib
import json
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = REPOSITORY_ROOT / "scripts" / "verify_indextts_source.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fixture(root: Path) -> Path:
    source_root = root / "third_party" / "index-tts"
    source_root.mkdir(parents=True)
    (source_root / "LICENSE").write_text("upstream license\n", encoding="utf-8")
    (source_root / "indextts.py").write_text("print('upstream')\n", encoding="utf-8")
    (source_root / "checkpoints").mkdir()
    (source_root / "checkpoints" / "model.bin").write_bytes(b"local model asset")
    (source_root / "checkpoints-2.5").mkdir()
    (source_root / "checkpoints-2.5" / "pinyin.vocab").write_text(
        "upstream vocabulary\n", encoding="utf-8"
    )

    manifest = {
        "schema_version": 1,
        "upstream": {
            "repository": "https://github.com/index-tts/index-tts",
            "commit": "a371df7d0746a0ae7fdf075798b6b04e34a0132e",
            "tree": "0123456789abcdef0123456789abcdef01234567",
            "acquired_on": "2026-08-12",
        },
        "license": {"path": "LICENSE", "sha256": _sha256(source_root / "LICENSE")},
        "excluded_paths": [
            "SOURCE_MANIFEST.json",
            "checkpoints/",
        ],
        "files": [
            {"path": "LICENSE", "sha256": _sha256(source_root / "LICENSE")},
            {"path": "indextts.py", "sha256": _sha256(source_root / "indextts.py")},
            {
                "upstream_path": "checkpoints/pinyin.vocab",
                "path": "checkpoints-2.5/pinyin.vocab",
                "sha256": _sha256(source_root / "checkpoints-2.5" / "pinyin.vocab"),
            },
        ],
    }
    manifest_path = source_root / "SOURCE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _verify(manifest_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--manifest", str(manifest_path)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_verifier_accepts_manifest_and_excludes_local_checkpoint_assets(tmp_path: Path) -> None:
    manifest_path = _write_fixture(tmp_path)

    result = _verify(manifest_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "verified 3 upstream files" in result.stdout
    assert "mapped upstream: checkpoints/pinyin.vocab -> checkpoints-2.5/pinyin.vocab" in result.stdout


def test_verifier_rejects_modified_missing_and_extra_upstream_files(tmp_path: Path) -> None:
    manifest_path = _write_fixture(tmp_path)
    source_root = manifest_path.parent
    (source_root / "indextts.py").write_text("modified\n", encoding="utf-8")
    (source_root / "LICENSE").unlink()
    (source_root / "extra.py").write_text("unexpected\n", encoding="utf-8")
    (source_root / "checkpoints-2.5" / "pinyin.vocab").write_text("modified\n", encoding="utf-8")

    result = _verify(manifest_path)

    assert result.returncode == 1
    assert "missing: LICENSE" in result.stdout
    assert "modified: indextts.py" in result.stdout
    assert "extra: extra.py" in result.stdout
    assert "license missing: LICENSE" in result.stdout
    assert "modified: checkpoints-2.5/pinyin.vocab" in result.stdout
