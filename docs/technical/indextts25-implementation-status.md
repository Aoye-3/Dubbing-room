# IndexTTS-2.5 Implementation Status

Status date: 2026-08-12.

This is the authoritative execution status for the IndexTTS-2.5 replacement. It supersedes older IndexTTS 2.0 runtime, API, frontend, and testing statements where they conflict.

## Model identity and source

- The stable backend identifier remains `indextts2`.
- New jobs use `model_id=IndexTTS-2.5`, `model_version=2.5`, and upstream commit `a371df7d0746a0ae7fdf075798b6b04e34a0132e`.
- `third_party/index-tts` is an in-place snapshot of that commit. `SOURCE_MANIFEST.json` records the repository, commit, tree, license hash, 337 file hashes, and mapped Pinyin vocabulary.
- `third_party/index-tts/checkpoints` remains the untouched IndexTTS 2.0 rollback family. IndexTTS-2.5 assets belong only in `third_party/index-tts/checkpoints-2.5`.
- Source, config, and checkpoint family mismatches fail with `model_version_mismatch` before model construction.
- The repository does not contain or distribute the IndexTTS-2.5 model package. The user must install its config and weights after reviewing the bilibili custom license.

## Runtime and Settings contract

The project-local profile is stored at `data/app/indextts2-runtime.json`. Defaults are precision `auto`, text emotion enabled, and CUDA kernel, DeepSpeed, accel, and Torch compile disabled. On the current RTX 5060 Laptop GPU, `auto` resolves to BF16.

The backend exposes `GET /runtime-backends`, `GET /runtime-backends/indextts2/config`, and `POST /runtime-backends/indextts2/config`. Electron IPC and Settings use the same `IndexTTS2RuntimeProfile` contract. Saving affects the next job worker, never one already running.

Runtime status reports model identity, upstream commit, supported languages, effective precision, text-emotion capability, resolved paths, missing or mismatched assets, and structured low-VRAM warnings.

## Generation contract

Each job acquires one `RuntimeCoordinator` lease and starts one JSONL worker. The worker imports `indextts.infer_v2_5.IndexTTS2`, loads once, generates one to five takes sequentially, then exits before the lease is released. The compatibility `/indextts2/generate` endpoint uses the same protocol with one take.

The protocol emits `ready`, `take_started`, `take_succeeded`, `take_failed`, and `complete`. Upstream stdout is redirected to stderr. Running cancellation terminates the process, cancels unfinished takes, prevents History projection, and releases the lease.

New requests require `language` in `ZH`, `EN`, `JA`, `ES`, or `AR`; the service maps it to upstream `lang`. `duration_factor` is limited to 0.5 through 2.0. Text normalization, segmentation, and controlled sampling are generation options. Precision, QwenEmotion permission, and acceleration flags are runtime settings, not per-line controls. Retrying a legacy 2.0 job without language defaults to `ZH` and records `legacy_language_defaulted`; new requests never receive that fallback.

Text-emotion jobs alone load QwenEmotion. Missing Qwen assets are rejected as `text_emotion_unavailable`. CUDA OOM while initializing or running text emotion is `text_emotion_memory_insufficient`; the backend never silently changes emotion mode.

Database schema version 5 adds nullable model identity and structured warnings to generations, jobs, and takes. Existing records remain null. Selecting a take copies its identity and warnings into the job and projected History generation.

## Performance Desk contract

One pure `buildIndexTTS25JobRequest` mapper serves both multi-take generation and quick preview; quick preview submits one take through the job API. Controls cover language, reference voice, duration, emotion, take count, expert options, and conditional Pinyin, CMU, or Kana helpers. Spanish and Arabic expose no unsupported pronunciation helper. Reference audio carries the upstream 15-second note, and text emotion is labelled experimental and memory-sensitive.

The current-job desk exposes take status, playback, parameters, warnings or errors, selection, export, save to Voice Library, and cancellation. Selection projects the take into History. Jobs remains the global view. Electron preserves backend `code`, `type`, and `details`; the renderer distinguishes configuration, memory, cancellation, truncation, and inference failures.

## Automated verification

The 2026-08-12 consolidated run passed 142 Python tests and 35 renderer tests across six files. It also passed source-manifest verification, TypeScript typecheck, the renderer production build, Electron main/preload/dev-runner syntax checks, Python compilation, and `git diff --check`.

These gates cover asset-family detection, profile persistence, worker mappings and JSONL, five languages, four emotion modes, expert parameter propagation, one-load multi-take execution, partial failure, timeout, deterministic cancellation races, lease release, schema-v5 compatibility, History projection, form validation, pronunciation syntax, conditional controls, Settings save, bounded polling, take actions, and structured errors.

## Real-model acceptance remains open

The workspace intentionally lacks the official IndexTTS-2.5 `config.yaml` and model weights. Runtime status therefore reports `missing_checkpoints`; no real inference claim is made.

After the user installs the licensed assets, acceptance must record hardware, driver, CUDA, source commit, model directory, peak VRAM, and elapsed time while verifying:

- basic and cross-language synthesis for all five languages;
- all four emotion modes, including the 8 GB warning and OOM classification;
- monotonic duration at 0.5, 1.0, and 2.0;
- Pinyin, CMU, and Kana annotations;
- three takes with one load, partial failure, cancellation, and VRAM release;
- selected-take History projection, export, and save to Voice Library.

Do not update the product README to claim fully verified IndexTTS-2.5 support until these real-model checks pass.
