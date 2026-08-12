# IndexTTS-2.5 Upstream Contract Baseline

## Purpose

This document records the upstream facts that the Dubbing-room IndexTTS adapter follows. See [IndexTTS-2.5 implementation status](indextts25-implementation-status.md) for the local cutover and remaining real-model gates.

Research date: 2026-08-12.

Upstream repository: <https://github.com/index-tts/index-tts>

Pinned research baseline: [`a371df7d0746a0ae7fdf075798b6b04e34a0132e`](https://github.com/index-tts/index-tts/commit/a371df7d0746a0ae7fdf075798b6b04e34a0132e).

The first public 2.5 implementation commit is [`583d6d4c8399474a8552ff7aae043920148bb235`](https://github.com/index-tts/index-tts/commit/583d6d4c8399474a8552ff7aae043920148bb235). The later pinned commit is used because it includes post-release low-VRAM and QwenEmotion capability fixes.

## Release Identification

- The official README announces IndexTTS-2.5 on 2026-08-10 and lists Chinese, English, Japanese, Spanish, and Arabic support, `duration_factor`, improved pronunciation controls, and faster inference than IndexTTS-2. [Official README](https://github.com/index-tts/index-tts/blob/a371df7d0746a0ae7fdf075798b6b04e34a0132e/README.md#L15-L38)
- There is currently no Git tag or GitHub Release for 2.0 or 2.5. The latest published tag is `v1.5.0`.
- `pyproject.toml` still reports package version `2.0.0`. Package metadata therefore cannot distinguish a 2.0 snapshot from a 2.5 snapshot. [Upstream package metadata](https://github.com/index-tts/index-tts/blob/a371df7d0746a0ae7fdf075798b6b04e34a0132e/pyproject.toml#L1-L22)
- Every vendored snapshot must record the full upstream commit SHA, acquisition date, license hash, and source manifest. Following an unpinned `main` is not an acceptable runtime identity.

## Current Local Baseline

- `third_party/index-tts` is now an in-place snapshot of the pinned commit and is verified by `SOURCE_MANIFEST.json`; upstream package metadata still reports `2.0.0`, so the commit remains the authoritative identity.
- `third_party/index-tts/checkpoints` preserves the former 2.0 rollback assets. The adapter never selects that directory for 2.5.
- `third_party/index-tts/checkpoints-2.5` is the only 2.5 asset location. Its licensed config and weights are not installed in this workspace.
- The worker imports `indextts.infer_v2_5.IndexTTS2`, uses BF16/QwenEmotion runtime settings, and requires the 2.5 language and duration contract.
- The isolated Python 3.10 runtime remains project-local. Its environment must be reconciled with the pinned upstream lock before real-model acceptance.

Source presence and automated adapter tests are not real-model acceptance. Until the licensed assets are installed and the hardware matrix passes, runtime readiness correctly remains `missing_checkpoints`.

## Installation And Assets

The upstream project requires Python `>=3.10,<3.12` and documents `uv sync` as the reliable install path. Its Windows/Linux PyTorch source is cu128. Relevant pinned dependencies include PyTorch/Torchaudio 2.8 and Transformers 4.52.1. [Upstream dependencies](https://github.com/index-tts/index-tts/blob/a371df7d0746a0ae7fdf075798b6b04e34a0132e/pyproject.toml#L22-L89)

Official 2.5 model repositories:

- Hugging Face: `IndexTeam/IndexTTS-2.5`
- ModelScope: `IndexTeam/IndexTTS-2.5`

The official WebUI checks this main inventory:

| Version | Required main model files |
| --- | --- |
| 2.0 | `bpe.model`, `gpt.pth`, `s2mel.pth`, `wav2vec2bert_stats.pt` |
| 2.5 | `gpt.pth`, `s2mel.pth`, `codec.pth`, `multilingual_zh_ja_yue_char_del.tiktoken`, `wav2vec2bert_stats.pt` |

Source: [upstream WebUI model check](https://github.com/index-tts/index-tts/blob/a371df7d0746a0ae7fdf075798b6b04e34a0132e/webui.py#L50-L84).

The model directories are not interchangeable. The application must detect and reject source/config/checkpoint family mismatches before launching a worker. It must not overlay 2.5 files on the existing 2.0 directory.

## Constructor Contract

IndexTTS-2.5 uses a different module and precision option:

```python
from indextts.infer_v2_5 import IndexTTS2

tts = IndexTTS2(
    cfg_path="checkpoints/config.yaml",
    model_dir="checkpoints",
    use_bf16=False,
    device=None,
    use_gpt_latent=False,
    use_cuda_kernel=None,
    use_deepspeed=False,
    use_accel=False,
    use_torch_compile=False,
    use_qwen_emo=False,
)
```

Source: [2.5 constructor](https://github.com/index-tts/index-tts/blob/a371df7d0746a0ae7fdf075798b6b04e34a0132e/indextts/infer_v2_5.py#L68-L85).

Migration differences:

| Area | IndexTTS-2 | IndexTTS-2.5 |
| --- | --- | --- |
| Module | `indextts.infer_v2` | `indextts.infer_v2_5` |
| Half precision | `use_fp16` | `use_bf16` |
| Text-emotion model | loaded by the 2.0 implementation | conditional `use_qwen_emo`, default false |
| Tokenizer | BPE | Tiktoken |
| Semantic codec | auxiliary semantic codec asset | main model `codec.pth` |
| GPT latent flag | not a public constructor input | `use_gpt_latent`, internal/advanced |

`use_gpt_latent` is not documented as an end-user feature and must not be exposed in the normal UI without a measured product requirement.

## Inference Contract

```python
tts.infer(
    spk_audio_prompt,
    text,
    output_path,
    lang,
    emo_audio_prompt=None,
    emo_alpha=1.0,
    emo_vector=None,
    use_emo_text=False,
    emo_text=None,
    use_random=False,
    interval_silence=200,
    verbose=False,
    max_text_tokens_per_segment=120,
    stream_return=False,
    more_segment_before=0,
    duration_factor=1.0,
    text_normalization=True,
    **generation_kwargs,
)
```

Source: [2.5 `infer` and `infer_generator`](https://github.com/index-tts/index-tts/blob/a371df7d0746a0ae7fdf075798b6b04e34a0132e/indextts/infer_v2_5.py#L465-L530).

### Stable application inputs

- `lang`: required application enum `ZH | EN | JA | ES | AR`.
- `duration_factor`: `0.5..2.0`, default `1.0`. Values above one lengthen speech; values below one shorten it. It is not a target-seconds control.
- `text_normalization`: default true.
- `interval_silence`: default 200 ms.
- `max_text_tokens_per_segment`: default 120.
- `emo_alpha`: `0..1`; upstream API default 1.0. The WebUI uses 0.65 in applicable modes.
- Emotion vector order: happy, angry, sad, afraid, disgusted, melancholic, surprised, calm.

### Expert generation inputs

| Parameter | Upstream default |
| --- | ---: |
| `top_p` | 0.8 |
| `top_k` | 30 |
| `temperature` | 0.8 |
| `length_penalty` | 0.0 |
| `num_beams` | 3 |
| `repetition_penalty` | 10.0 |
| `max_mel_tokens` | 1500 |

`do_sample` is currently read from keyword arguments but the downstream call is hard-coded to `True`. It must not be presented as a reliable user control unless the adapter pins a corrected upstream revision or carries a tested local patch. [Generation call](https://github.com/index-tts/index-tts/blob/a371df7d0746a0ae7fdf075798b6b04e34a0132e/indextts/infer_v2_5.py#L708-L727)

Arbitrary `generation_kwargs` are not a stable public application contract and must not be forwarded from untyped renderer input.

## Emotion Modes

The application should preserve its existing discriminated mode concept:

```text
same_voice
audio_prompt
vector
text_prompt
```

Only fields belonging to the selected mode are accepted. Upstream clears the independent emotion reference when vector or text guidance is used. [Emotion exclusivity](https://github.com/index-tts/index-tts/blob/a371df7d0746a0ae7fdf075798b6b04e34a0132e/indextts/infer_v2_5.py#L539-L570)

Text emotion is conditional. `use_emo_text=True` raises `RuntimeError` when the model was built without `use_qwen_emo=True`. The runtime status must publish this actual capability, and the renderer must disable the mode when it is unavailable.

The upstream WebUI normalizes vectors with fixed bias factors and a maximum total of 0.8. The direct `infer` call does not automatically invoke that helper. Dubbing-room currently rejects totals above 0.8; that deterministic contract should remain unless product testing justifies switching to automatic scaling.

## Language And Pronunciation Control

Official languages and application codes:

| UI label | API value | Pronunciation helper |
| --- | --- | --- |
| Chinese | `ZH` | Pinyin: `<行|XING2>` |
| English | `EN` | CMU phonemes: `<minute|M IH1 . N AH0 T>` |
| Japanese | `JA` | Kana: `<上手|じょうず>` |
| Spanish | `ES` | none documented |
| Arabic | `AR` | none documented |

Source: [official pronunciation examples](https://github.com/index-tts/index-tts/blob/a371df7d0746a0ae7fdf075798b6b04e34a0132e/README.md#L319-L343).

The UI must not produce the old bare-uppercase-Pinyin syntax for 2.5. Pronunciation assistance should insert the `<source|pronunciation>` form and change its guidance with the selected language.

Text normalization differs by language in current upstream source: ZH/EN use the project normalizer, JA/ES use NeMo normalization, and AR does not enter either normalization branch. This is a source observation, not a claim that Arabic is unsupported. Arabic numbers and punctuation require explicit acceptance tests. [Normalization branches](https://github.com/index-tts/index-tts/blob/a371df7d0746a0ae7fdf075798b6b04e34a0132e/indextts/infer_v2_5.py#L642-L667)

## Output, Reference Audio, And Low-VRAM Behavior

- Speaker and emotion references are truncated to their first 15 seconds by upstream inference.
- No official minimum duration, file-size limit, channel constraint, or input-format whitelist is documented. Dubbing-room must not invent these limits before local tests establish them.
- File output is 22,050 Hz int16 WAV. The existing media, History, take, and Voice Library path contract can remain.
- `stream_return=True` exposes a Python generator, not a stable HTTP or Electron streaming protocol. Streaming is out of the initial replacement scope.
- A `max_mel_tokens` limit warning can indicate truncated output and should be preserved as a structured worker warning.
- On CUDA devices below 10 GB VRAM, upstream can split long non-streaming text and the official WebUI defaults to half precision while skipping QwenEmotion. [Low-VRAM behavior](https://github.com/index-tts/index-tts/commit/a371df7d0746a0ae7fdf075798b6b04e34a0132e)

Runtime capabilities must describe the effective state, not just model claims:

```json
{
  "backend_id": "indextts2",
  "model_id": "IndexTTS-2.5",
  "model_version": "2.5",
  "upstream_commit": "a371df7d0746a0ae7fdf075798b6b04e34a0132e",
  "languages": ["ZH", "EN", "JA", "ES", "AR"],
  "precision_modes": ["fp32", "bf16"],
  "supports_duration_factor": true,
  "supports_text_emotion": false,
  "supports_streaming": false
}
```

## CLI And Serving Boundaries

- The supported direct 2.5 module is `indextts/infer_v2_5.py`.
- The installed `indextts2` console entry still points to `indextts.cli_v2`, which imports the 2.0 module and checks 2.0 assets. It must not be used as the 2.5 adapter.
- The repository TensorRT backend is documented for IndexTTS-2 and currently has no 2.5 engines.
- Upstream advertises a vLLM production recipe, but adopting vLLM would be a separate architecture decision. It is not required for the local replacement.

## License And Product Compliance

The upstream project uses `LicenseRef-Bilibili-IndexTTS`, not MIT or Apache. The license defines the model to include published weights and final code. [Official license](https://github.com/index-tts/index-tts/blob/a371df7d0746a0ae7fdf075798b6b04e34a0132e/LICENSE)

Before distributing source, weights, a bundled runtime, or model-derived material:

- retain the license and copyright notices;
- review the separate-license thresholds stated in the upstream license;
- include the required derivative-work disclaimer where applicable;
- review restrictions on using the model to improve other AI models;
- add voice-authorization and misuse guidance to the product flow;
- obtain a human legal/compliance review. This document is not legal advice.

## Confirmed Unknowns

- Whether upstream will publish a formal 2.5 tag or GitHub Release.
- Official minimum reference duration and input file whitelist.
- A stable HTTP contract for ordinary Python inference.
- A supported ordinary-inference streaming transport.
- 2.5 TensorRT availability.
- Exact quality and memory behavior on the project's target GPUs.

These unknowns must be measured or confirmed from a later pinned official revision; they must not be silently filled with assumptions.
