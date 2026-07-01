from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UTILS_PATH = ROOT / "src" / "voxcpm" / "model" / "utils.py"

transformers_stub = types.ModuleType("transformers")
transformers_stub.PreTrainedTokenizer = object
sys.modules.setdefault("transformers", transformers_stub)

spec = importlib.util.spec_from_file_location("voxcpm.model.utils", UTILS_PATH)
utils = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(utils)


def test_resolve_runtime_device_auto_falls_back_to_cpu(monkeypatch):
    monkeypatch.setattr(utils.torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(utils, "_has_mps", lambda: False)

    assert utils.resolve_runtime_device(None, "cuda") == "cpu"


def test_resolve_runtime_device_auto_uses_mps_when_available(monkeypatch):
    monkeypatch.setattr(utils.torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(utils, "_has_mps", lambda: True)

    assert utils.resolve_runtime_device("auto", "cuda") == "mps"


def test_resolve_runtime_device_respects_explicit_cpu(monkeypatch):
    monkeypatch.setattr(utils.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(utils, "_has_mps", lambda: True)

    assert utils.resolve_runtime_device("cpu", "cuda") == "cpu"


def test_resolve_runtime_device_rejects_unavailable_explicit_cuda(monkeypatch):
    monkeypatch.setattr(utils.torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(utils, "_has_mps", lambda: True)

    with pytest.raises(ValueError, match="CUDA is not available"):
        utils.resolve_runtime_device("cuda:0", "cuda")
