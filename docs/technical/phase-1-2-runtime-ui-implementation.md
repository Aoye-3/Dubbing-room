# Dual-Model Runtime, UI, and Job/Take Implementation Notes

Status date: 2026-08-07

Baseline: current `main` functionality plus documentation maintenance branch

This note records the current technical contract after Phase 1 through Phase 3 of
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

Renderer `IndexTTS2Payload` fields now include:

- `text`
- `speaker`
- `emotion_mode`
- `emotion_audio`
- `emo_alpha`
- `emo_vector`
- `use_emo_text`
- `emo_text`
- `use_random`
- `interval_silence`
- `max_text_tokens_per_segment`
- `do_sample`
- `top_p`
- `top_k`
- `temperature`
- `length_penalty`
- `num_beams`
- `repetition_penalty`
- `max_mel_tokens`
- `use_fp16`
- `use_cuda_kernel`
- `use_deepspeed`
- `use_accel`
- `use_torch_compile`
- `take_count`

Before invoking the worker, the service resolves `speaker` and `emotion_audio`
to project-local paths and normalizes them as `spk_audio_prompt` and
`emo_audio_prompt`. Job execution supplies its id through the service/runtime
boundary rather than as a renderer `IndexTTS2Payload` field.

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

`main.tsx` now only mounts `App`. Domain pages and shared behavior live under
`app/`, `shared/`, `voxcpm/`, `indextts2/`, `jobs/`, `storage/`, and `updates/`.

Both model workbenches disable generation while their runtime is unconfigured or
globally busy. They share `GenerationResultPanel` for playback, export, and
save-as-voice presentation while keeping generation and persistence side effects
in the owning page.

## Phase 3 Job/Take Contract

Implemented HTTP surface:

```text
POST /generation-jobs
GET  /generation-jobs
GET  /generation-jobs/:job_id
POST /generation-jobs/:job_id/cancel
POST /generation-jobs/:job_id/retry
GET  /generation-jobs/:job_id/takes
POST /generation-takes/:take_id/select
```

Current behavior:

- The backend owns an in-process FIFO queue.
- VoxCPM2 queued jobs produce one output asset and a compatibility History record.
- IndexTTS2 jobs create 1-5 takes, default 3, and execute them sequentially.
- Successful takes expose `output_asset` in API responses for playback.
- The first successful take is projected to History; selecting another successful
  take updates the projection idempotently.
- A failed take cannot be selected and remains visible only in Jobs detail.
- A successful take can be copied into Voice Library with `source: "take"`.
- queued jobs can be cancelled; cancelling a running job only records
  `cancel requested` and does not interrupt current inference.
- retry creates a new job from the previous backend, mode, voice, and params.

The Jobs renderer polls jobs and takes every 3 seconds and exposes cancel, retry,
playback, select, and save-as-voice actions.

## Latest Verification

Local verification completed after Phase 1/2 implementation:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_storage.py tests\test_voxcpm_app_service_cli.py tests\test_voxcpm_app_generation_service.py tests\test_voxcpm_app_indextts2_service.py --basetemp data\pytest-tmp
npm.cmd run typecheck
npm.cmd run build
node --check electron\main.js
node --check electron\preload.js
node --check electron\dev-runner.js
git diff --check
```

Result:

- Python tests: 45 passed in 10.01s.
- TypeScript typecheck: passed.
- Renderer build: passed; 1717 modules transformed.
- Electron syntax checks: passed.
- Diff whitespace check: passed; working-tree CRLF warnings remain informational.

Resource inventory on 2026-08-07 found the project-local IndexTTS2 runtime Python
and all checkpoint files/directories listed in `models-runtime.md`. No real model
inference was run as part of this verification.

## Remaining Technical Gaps

- Renderer tests for runtime status cards and IndexTTS2 validation states.
- Electron IPC integration tests for structured backend errors.
- Desktop E2E for generation, Jobs, History, Trash, export, and save-as-voice.
- Real-model smoke tests against project-local VoxCPM2 and IndexTTS2 runtimes.
- Cross-process runtime locking if multiple backend server processes are allowed.
- Hard cancellation for already-running subprocess/model generation.
- Real runtime load/unload/free and CUDA cache cleanup.
- Typed renderer handling for backend `code` and `details`.
- Recovery semantics for queued/running jobs after backend restart.
