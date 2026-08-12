from __future__ import annotations

import contextlib
import json
import sys
import warnings
from pathlib import Path
from typing import IO, Any

import soundfile as sf


SUPPORTED_LANGUAGES = {"ZH", "EN", "JA", "ES", "AR"}


def main() -> int:
    return run_session(sys.stdin, sys.stdout)


def run_session(input_stream: IO[str], output_stream: IO[str]) -> int:
    model: Any = None
    initialized = False
    take_count = 0
    for raw_line in input_stream:
        if not raw_line.strip():
            continue
        message: dict[str, Any] = {}
        try:
            message = json.loads(raw_line)
            op = message.get("op")
            if op == "init":
                if initialized:
                    raise ValueError("worker is already initialized")
                model = _load_model(message)
                initialized = True
                _emit(output_stream, {"event": "ready"})
            elif op == "synthesize":
                if not initialized:
                    raise ValueError("first worker message must be init")
                take_count += 1
                if take_count > 5:
                    raise ValueError("worker accepts between 1 and 5 takes")
                _synthesize(model, message, output_stream)
            elif op == "complete":
                if not initialized:
                    raise ValueError("first worker message must be init")
                if take_count < 1:
                    raise ValueError("worker accepts between 1 and 5 takes")
                _emit(output_stream, {"event": "complete"})
                return 0
            else:
                raise ValueError(f"unsupported worker operation: {op}")
        except Exception as exc:
            event = "take_failed" if isinstance(message, dict) and message.get("op") == "synthesize" else "complete"
            text_emotion_requested = bool(
                isinstance(message, dict)
                and message.get("op") == "init"
                and message.get("use_qwen_emo")
            )
            payload = _error_payload(exc, text_emotion_requested=text_emotion_requested)
            if isinstance(message, dict) and message.get("take_id"):
                payload["take_id"] = str(message["take_id"])
            _emit(output_stream, {"event": event, **payload})
            if event == "complete":
                return 1
    if initialized:
        _emit(
            output_stream,
            {
                "event": "complete",
                **_error_payload(EOFError("worker stdin ended before explicit complete")),
            },
        )
        return 1
    _emit(output_stream, {"event": "complete", **_error_payload(ValueError("first worker message must be init"))})
    return 1


def run(payload: dict[str, object]) -> dict[str, object]:
    """Compatibility helper for direct, single-take worker tests."""
    output = _StringWriter()
    init = {key: value for key, value in payload.items() if key != "output_path"}
    init["op"] = "init"
    take = dict(payload)
    take.update({"op": "synthesize", "take_id": "single"})
    lines = _StringReader([init, take, {"op": "complete"}])
    code = run_session(lines, output)
    events = [json.loads(line) for line in output.lines]
    failed = next((event for event in events if event.get("event") == "take_failed"), None)
    if failed:
        raise RuntimeError(str(failed.get("error") or "worker failed"))
    if code:
        raise RuntimeError("worker failed")
    succeeded = next(event for event in events if event.get("event") == "take_succeeded")
    return {"output_path": str(succeeded["output_path"]), "sample_rate": int(succeeded["sample_rate"])}


def _load_model(message: dict[str, Any]) -> Any:
    source_root = Path(str(message["source_root"])).resolve()
    sys.path.insert(0, str(source_root))
    with contextlib.redirect_stdout(sys.stderr):
        from indextts.infer_v2_5 import IndexTTS2

        return IndexTTS2(
            cfg_path=str(message["cfg_path"]),
            model_dir=str(message["model_dir"]),
            device=str(message.get("device", "cuda")),
            use_bf16=bool(message.get("use_bf16", False)),
            use_qwen_emo=bool(message.get("use_qwen_emo", False)),
            use_cuda_kernel=bool(message.get("use_cuda_kernel", False)),
            use_deepspeed=bool(message.get("use_deepspeed", False)),
            use_accel=bool(message.get("use_accel", False)),
            use_torch_compile=bool(message.get("use_torch_compile", False)),
        )


def _synthesize(model: Any, message: dict[str, Any], output_stream: IO[str]) -> None:
    take_id = str(message.get("take_id") or "")
    _emit(output_stream, {"event": "take_started", "take_id": take_id})
    try:
        language = str(message.get("language") or "")
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError("language must be one of ZH, EN, JA, ES, AR")
        output_path = Path(str(message["output_path"])).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration_factor = float(message.get("duration_factor", 1.0))
        if duration_factor < 0.5 or duration_factor > 2.0:
            raise ValueError("duration_factor must be between 0.5 and 2.0")
        text_normalization = message.get("text_normalization", True)
        if not isinstance(text_normalization, bool):
            raise ValueError("text_normalization must be a boolean")
        infer_payload = {
            "spk_audio_prompt": str(message["spk_audio_prompt"]),
            "text": str(message["text"]),
            "output_path": str(output_path),
            "lang": language,
            "emo_audio_prompt": message.get("emo_audio_prompt"),
            "emo_alpha": float(message.get("emo_alpha", 1.0)),
            "emo_vector": message.get("emo_vector"),
            "use_emo_text": bool(message.get("emotion_mode") == "text_prompt"),
            "emo_text": message.get("emo_text"),
            "use_random": bool(message.get("use_random", False)),
            "interval_silence": int(message.get("interval_silence", 200)),
            "verbose": bool(message.get("verbose", False)),
            "max_text_tokens_per_segment": int(message.get("max_text_tokens_per_segment", 120)),
            "duration_factor": duration_factor,
            "text_normalization": text_normalization,
            "top_p": float(message.get("top_p", 0.8)),
            "top_k": int(message.get("top_k", 30)),
            "temperature": float(message.get("temperature", 0.8)),
            "length_penalty": float(message.get("length_penalty", 0.0)),
            "num_beams": int(message.get("num_beams", 3)),
            "repetition_penalty": float(message.get("repetition_penalty", 10.0)),
            "max_mel_tokens": int(message.get("max_mel_tokens", 1500)),
        }
        worker_warnings = _reference_warnings(message)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", RuntimeWarning)
            with contextlib.redirect_stdout(sys.stderr):
                model.infer(**infer_payload)
        for warning in caught:
            if issubclass(warning.category, RuntimeWarning):
                message_text = str(warning.message)
                code = "max_mel_tokens_reached" if "mel" in message_text.lower() and ("max" in message_text.lower() or "limit" in message_text.lower()) else "runtime_warning"
                worker_warnings.append({"code": code, "message": message_text})
        if not output_path.is_file():
            raise RuntimeError(f"generated output missing: {output_path}")
        sample_rate = int(sf.info(str(output_path)).samplerate)
        _emit(
            output_stream,
            {
                "event": "take_succeeded",
                "take_id": take_id,
                "output_path": str(output_path),
                "sample_rate": sample_rate,
                "warnings": worker_warnings,
            },
        )
    except Exception as exc:
        _emit(output_stream, {"event": "take_failed", "take_id": take_id, **_error_payload(exc)})


def _emit(output_stream: IO[str], event: dict[str, object]) -> None:
    output_stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    output_stream.flush()


def _reference_warnings(message: dict[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for key, label in (("spk_audio_prompt", "Speaker"), ("emo_audio_prompt", "Emotion")):
        path = message.get(key)
        if not path:
            continue
        try:
            if float(sf.info(str(path)).duration) > 15:
                result.append(
                    {
                        "code": "reference_audio_truncated",
                        "message": f"{label} reference exceeds 15 seconds and may be truncated.",
                    }
                )
        except Exception:
            pass
    return result


def _error_payload(exc: Exception, *, text_emotion_requested: bool = False) -> dict[str, object]:
    return {
        "error": str(exc).splitlines()[0][:500],
        "type": type(exc).__name__,
        "code": _error_code(exc, text_emotion_requested=text_emotion_requested),
        "details": {},
    }


def _error_code(exc: Exception, *, text_emotion_requested: bool = False) -> str:
    text = str(exc).lower()
    if "out of memory" in text and (text_emotion_requested or "qwen" in text or "emotion" in text):
        return "text_emotion_memory_insufficient"
    if isinstance(exc, EOFError):
        return "worker_eof"
    if "checkpoint" in text:
        return "checkpoints_missing"
    if "runtime" in text:
        return "runtime_missing"
    if "output" in text and "missing" in text:
        return "output_missing"
    if isinstance(exc, ValueError):
        return "validation_error"
    return "worker_failed"


class _StringReader:
    def __init__(self, messages: list[dict[str, object]]):
        self._lines = [json.dumps(message, ensure_ascii=False) + "\n" for message in messages]

    def __iter__(self):
        return iter(self._lines)


class _StringWriter:
    def __init__(self):
        self.lines: list[str] = []

    def write(self, value: str) -> int:
        self.lines.append(value)
        return len(value)

    def flush(self) -> None:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
