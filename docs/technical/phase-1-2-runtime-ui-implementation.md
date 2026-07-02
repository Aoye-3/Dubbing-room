# Phase 1/2 Runtime and UI Implementation Notes

Status date: 2026-07-02

Branch: `codex/model-api-adapter-alignment`

This note records the current technical contract after Phase 1 and Phase 2 of
the dual-model plan. It is intentionally implementation-facing: when the API,
runtime, or renderer behavior changes, update this file together with
`models-runtime.md`, `backend-api.md`, and `testing-acceptance.md`.

## Runtime Backend Contract

`GET /runtime-backends` returns one entry per backend:

```json
{
  "backend_id": "voxcpm2",
  "display_name": "VoxCPM2",
  "enabled": true,
  "configured": true,
  "loaded": false,
  "busy": false,
  "device": "cuda",
  "last_error": null,
  "capabilities": ["voice_clone", "instruction_control", "quality_retry"],
  "active_job_id": null,
  "started_at": null,
  "state": "configured",
  "details": {
    "runtime_busy": false,
    "active_backend": null
  }
}
```

The current runtime coordinator has a single project-local generation slot.
That means `busy` is a global runtime signal: if VoxCPM2 is generating,
IndexTTS2 also reports `busy: true`, with `details.active_backend` identifying
the backend that holds the lease.

Current states:

- `configured`: backend can be invoked but is not currently loaded or busy.
- `loaded`: backend has an in-memory model instance.
- `busy`: the shared runtime slot is held.
- `missing_runtime`: the backend runtime entrypoint or local runtime is missing.
- `missing_checkpoints`: configured runtime exists, but required model assets are missing.

## VoxCPM2 Integration

Default runtime behavior:

- Model id defaults to `openbmb/VoxCPM2`.
- Hugging Face cache defaults to `data/runtimes/voxcpm2/hf-cache`.
- `local_files_only` defaults to `false`.
- The denoiser is disabled by default with `load_denoiser: false`.
- `zipenhancer_model_id` is passed through only when configured.

Generation payload fields now include:

- `text`
- `prompt_wav`
- `prompt_text`
- `cfg_value`
- `inference_timesteps`
- `normalize`
- `denoise`
- `streaming`
- `min_len`
- `max_len`
- `retry_badcase`
- `retry_badcase_max_times`
- `retry_badcase_ratio_threshold`
- `generation_job_id`

Ultimate Clone mode now treats `prompt_text` as the authority and leaves
instruction/control text blank. This keeps reference-audio cloning separate from
instructional control text.

Known upstream limitation: `do_sample` is still forwarded in the app contract,
but the current upstream `VoxCPM.generate` path hardcodes sampling behavior.
Keep this visible until upstream exposes the parameter or the local integration
wraps it explicitly.

## IndexTTS2 Integration

Default project-local paths:

- Source root: `third_party/index-tts`
- Runtime Python: `data/runtimes/indextts2/.venv/Scripts/python.exe`
- Model directory: `third_party/index-tts/checkpoints`
- Config path: `third_party/index-tts/checkpoints/config.yaml`
- Runtime cache root: `data/runtimes/indextts2`

The following environment overrides are accepted only when they resolve inside
the project root:

- `INDEXTTS2_PYTHON`
- `INDEXTTS2_MODEL_DIR`
- `INDEXTTS2_CFG_PATH`

If an override points outside the project, runtime status reports it in
`details.outside_project_paths`, and synthesis fails with a structured
`validation_error`.

Required checkpoint assets:

- `config.yaml`
- `bpe.model`
- `gpt.pth`
- `s2mel.pth`
- `wav2vec2bert_stats.pt`
- `feat1.pt`
- `feat2.pt`
- `qwen0.6bemo4-merge`
- `hf_cache/semantic_codec_model.safetensors`
- `hf_cache/campplus_cn_common.bin`
- `hf_cache/bigvgan/config.json`
- `hf_cache/bigvgan/bigvgan_generator.pt`
- `hf_cache/w2v-bert-2.0`

Renderer and worker payload fields now include:

- `text`
- `reference_audio`
- `emotion_mode`
- `emotion_audio`
- `emotion_alpha`
- `emotion_vector`
- `emo_text`
- `emo_random`
- `interval_silence`
- `do_sample`
- `top_p`
- `top_k`
- `temperature`
- `repetition_penalty`
- `max_mel_tokens`
- `seed`
- `use_fp16`
- `use_cuda_kernel`
- `use_deepspeed`
- `use_accel`
- `use_torch_compile`
- `generation_job_id`

Text emotion mode no longer requires explicit `emo_text`. Vector emotion mode
is blocked when the sum of vector values exceeds `0.8`, matching IndexTTS2's
safe operating guidance.

Worker safeguards:

- Timeout defaults to `INDEXTTS2_WORKER_TIMEOUT_SECONDS` or 1800 seconds.
- Worker failure JSON preserves `code` and `details` in backend errors.
- The backend reads the final stdout JSON line from the worker.
- Successful workers must produce a readable output file; missing or invalid
  audio is classified as `output_missing`.
- `use_accel` and `use_torch_compile` are passed to the IndexTTS2 constructor.

## Error Contract

Non-2xx backend routes return structured JSON:

```json
{
  "error": "Runtime is busy with another generation.",
  "type": "RuntimeError",
  "code": "runtime_busy",
  "details": {
    "active_backend": "voxcpm2"
  }
}
```

Current error codes include:

- `validation_error`
- `not_found`
- `runtime_busy`
- `checkpoints_missing`
- `runtime_missing`
- `worker_failed`
- `timeout`
- `output_missing`
- `media_not_found`
- `internal_error`

Legacy synchronous generation routes still persist failed `GenerationRecord`
objects for synthesis/runtime failures where the generation lifecycle has
already started. Route-level failures, media failures, and invalid requests use
the structured error envelope above.

Electron currently converts non-2xx responses to `Error(parsed.error)`. The
structured `code` and `details` fields are part of the backend contract, but the
renderer does not yet expose them as a typed UI error object.

## Renderer Behavior

Settings now displays backend readiness from `/runtime-backends`, including
state, busy status, configured/loaded flags, missing checkpoint details, runtime
paths, and active backend.

The VoxCPM2 workbench exposes length bounds and bad-case retry controls. The
IndexTTS2 workbench exposes acceleration toggles and validates emotion vector
total before generation or queue submission.

## Latest Verification

Local verification completed after Phase 1/2 implementation:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_storage.py tests\test_voxcpm_app_service_cli.py tests\test_voxcpm_app_generation_service.py tests\test_voxcpm_app_indextts2_service.py --basetemp data\pytest-tmp
npm.cmd run typecheck
npm.cmd run build
node --check electron\main.js
node --check electron\preload.js
git diff --check
```

Result:

- Python tests: 37 passed.
- TypeScript typecheck: passed.
- Renderer build: passed.
- Electron syntax checks: passed.
- Diff whitespace check: passed, with pre-existing CRLF warnings only.

## Remaining Technical Gaps

- Renderer tests for runtime status cards and IndexTTS2 validation states.
- Electron IPC integration tests for structured backend errors.
- Real-model smoke tests against project-local VoxCPM2 and IndexTTS2 runtimes.
- Cross-process runtime locking if multiple backend server processes are allowed.
- Hard cancellation for already-running subprocess/model generation.
- Typed renderer handling for backend `code` and `details`.
