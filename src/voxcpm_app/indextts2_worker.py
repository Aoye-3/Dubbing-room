from __future__ import annotations

import json
import sys
from pathlib import Path

import soundfile as sf


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        result = run(payload)
        print(json.dumps({"ok": True, **result}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc).splitlines()[0][:500],
                    "type": type(exc).__name__,
                    "code": _error_code(exc),
                    "details": {},
                },
                ensure_ascii=False,
            )
        )
        return 1


def run(payload: dict[str, object]) -> dict[str, object]:
    source_root = Path(str(payload["source_root"])).resolve()
    sys.path.insert(0, str(source_root))

    from indextts.infer_v2 import IndexTTS2

    output_path = Path(str(payload["output_path"])).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tts = IndexTTS2(
        cfg_path=str(payload["cfg_path"]),
        model_dir=str(payload["model_dir"]),
        device=str(payload.get("device", "cuda")),
        use_fp16=bool(payload.get("use_fp16", False)),
        use_cuda_kernel=bool(payload.get("use_cuda_kernel", False)),
        use_deepspeed=bool(payload.get("use_deepspeed", False)),
        use_accel=bool(payload.get("use_accel", False)),
        use_torch_compile=bool(payload.get("use_torch_compile", False)),
    )
    tts.infer(
        spk_audio_prompt=str(payload["spk_audio_prompt"]),
        text=str(payload["text"]),
        output_path=str(output_path),
        emo_audio_prompt=payload.get("emo_audio_prompt"),
        emo_alpha=float(payload.get("emo_alpha", 1.0)),
        emo_vector=payload.get("emo_vector"),
        use_emo_text=bool(payload.get("use_emo_text", False)),
        emo_text=payload.get("emo_text"),
        use_random=bool(payload.get("use_random", False)),
        interval_silence=int(payload.get("interval_silence", 200)),
        verbose=bool(payload.get("verbose", False)),
        max_text_tokens_per_segment=int(payload.get("max_text_tokens_per_segment", 120)),
        do_sample=bool(payload.get("do_sample", True)),
        top_p=float(payload.get("top_p", 0.8)),
        top_k=int(payload.get("top_k", 30)),
        temperature=float(payload.get("temperature", 0.8)),
        length_penalty=float(payload.get("length_penalty", 0.0)),
        num_beams=int(payload.get("num_beams", 3)),
        repetition_penalty=float(payload.get("repetition_penalty", 10.0)),
        max_mel_tokens=int(payload.get("max_mel_tokens", 1500)),
    )
    if not output_path.exists() or not output_path.is_file():
        raise RuntimeError(f"generated output missing: {output_path}")
    sf.info(str(output_path))
    return {"output_path": str(output_path)}


def _error_code(exc: Exception) -> str:
    text = str(exc).lower()
    if "checkpoint" in text:
        return "checkpoints_missing"
    if "runtime" in text:
        return "runtime_missing"
    if "output" in text and "missing" in text:
        return "output_missing"
    return "worker_failed"


if __name__ == "__main__":
    raise SystemExit(main())
