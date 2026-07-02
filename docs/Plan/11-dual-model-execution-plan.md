# Dual-Model AppShell Execution Plan

## Overview

This plan turns the dual-model PRD into executable work for the local VoxCPM-Box AppShell. The target is a usable local voice workflow studio with three clear product areas:

- Common Storage Backend: shared voices, generated audio, jobs, takes, history, media paths, logs, and runtime status.
- VoxCPM2 Production Desk: voice design, voice cloning, ultimate cloning, multilingual narration, reusable voice creation.
- IndexTTS2 Performance Desk: line-level performance refinement, emotion control, multi-take comparison, selected-take submission.

VoxCPM2 and IndexTTS2 are complementary backends, not interchangeable model choices. All model outputs must pass through shared storage and runtime coordination.

## Source Inputs

- Product PRD: `docs/app-dev/10-dual-model-integration-prd.md`
- Architecture: `docs/app-dev/02-architecture.md`
- API contracts: `docs/app-dev/04-api-contracts.md`
- UI workflows: `docs/app-dev/05-ui-workflows.md`
- Runtime notes: `docs/technical/models-runtime.md`
- Backend API notes: `docs/technical/backend-api.md`
- Testing notes: `docs/technical/testing-acceptance.md`
- Upstream IndexTTS2: `https://github.com/index-tts/index-tts`
- Upstream VoxCPM2: `https://github.com/OpenBMB/VoxCPM`

## Ground Rules

- Work only inside the current repository.
- Do not use git worktrees, clones, temporary project copies, or C: drive project caches.
- Keep model weights, runtime environments, generated files, pytest basetemp, and caches inside the current workspace.
- Preserve upstream model and Gradio source boundaries. Put product behavior in AppShell, app services, adapters, storage, and docs.
- Frontend displays runtime state but never decides GPU concurrency. Backend `RuntimeCoordinator` owns scheduling.
- Keep old synchronous routes compatible while moving internals toward job/take APIs.

## Current Baseline

- Electron React AppShell exists.
- Local Python AppShell backend exists.
- Voice Library and Generation History storage exist.
- VoxCPM2 generation service exists.
- IndexTTS2 service, worker boundary, and AppShell route exist.
- RuntimeCoordinator provides a shared in-process GPU lease.
- Queue/job primitives exist but are not yet the primary product entry.
- Real IndexTTS2 inference still requires project-local runtime and checkpoints.
- Runtime status is useful but not yet a full configured/missing/loaded/error contract.

## Architecture Decisions

- Keep a single shared GPU lease with default slot count 1.
- Keep VoxCPM2 cache under `data/runtimes/voxcpm2/hf-cache`.
- Keep IndexTTS2 runtime under `data/runtimes/indextts2/`.
- Keep IndexTTS2 source snapshot under `third_party/index-tts/`.
- Keep IndexTTS2 checkpoints under `third_party/index-tts/checkpoints/` unless explicitly configured.
- Add structured runtime and worker errors before adding richer UI workflows.
- Prefer vertical slices: backend contract, service behavior, renderer payload, tests, and manual acceptance for each product flow.

## Dependency Graph

```text
Runtime status and model asset checks
  -> Backend structured errors
  -> Settings and runtime status UI
  -> Safe generate button states

Storage v2 schema for assets/jobs/takes
  -> Job API
  -> Take API
  -> History projection
  -> IndexTTS2 multi-take UI

VoxCPM2 adapter contract
  -> VoxCPM2 renderer params
  -> Voice save and reuse flow
  -> IndexTTS2 speaker selection

IndexTTS2 adapter contract
  -> Emotion source validation
  -> Performance Desk params
  -> Multi-take generation
  -> Selected take submission
```

## Milestones

1. Runtime Readiness: model assets, status, and errors are reliable.
2. Parameterized Workbenches: VoxCPM2 and IndexTTS2 pages submit complete, model-appropriate payloads.
3. Job and Take Product Loop: long-running generation, multi-take comparison, and history projection work.
4. Real Model Acceptance: real VoxCPM2 and IndexTTS2 smoke tests pass in a project-local runtime.
5. Hardening and Documentation: tests, docs, and packaging notes reflect the implemented behavior.

## Execution Status (2026-07-02)

Phase 1 and Phase 2 have been implemented on branch
`codex/model-api-adapter-alignment`.

Completed scope:

- Runtime status now reports backend state and diagnostics through `/runtime-backends`.
- VoxCPM2 generation now forwards length and retry controls, uses a project-local cache by default, and keeps Ultimate Clone reference text separate from instruction control.
- IndexTTS2 now validates project-local runtime paths, reports missing checkpoint details, classifies worker failures, verifies output files, and forwards acceleration toggles.
- Settings now shows runtime readiness cards for both model backends.
- VoxCPM2 and IndexTTS2 workbenches now expose the Phase 2 parameters.

Verification completed:

- `.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_storage.py tests\test_voxcpm_app_service_cli.py tests\test_voxcpm_app_generation_service.py tests\test_voxcpm_app_indextts2_service.py --basetemp data\pytest-tmp` -> 37 passed.
- `npm.cmd run typecheck` -> passed.
- `npm.cmd run build` -> passed.
- `node --check electron\main.js` -> passed.
- `node --check electron\preload.js` -> passed.
- `git diff --check` -> passed with CRLF warnings only.

See [Phase 1/2 Runtime and UI Implementation Notes](../technical/phase-1-2-runtime-ui-implementation.md) for the current runtime, API, renderer, and testing contract.

## Phase 1: Runtime Readiness

### Task 1: Normalize Runtime Backend Status

**Description:** Extend runtime status so `/runtime-backends` reports whether each backend is configured, missing runtime, missing checkpoints, busy, loaded, or failed.

**Acceptance criteria:**
- [ ] VoxCPM2 status includes backend id, display name, enabled, configured, busy, loaded, device, capabilities, active job id, and last error.
- [ ] IndexTTS2 status reports missing source snapshot, runtime python, config, checkpoint, and auxiliary model files separately enough for UI display.
- [ ] Busy state comes from backend lease state, not renderer assumptions.

**Verification:**
- [ ] Add or update Python tests for `/runtime-backends`.
- [ ] Run `.\.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_indextts2_service.py tests\test_voxcpm_app_generation_service.py --basetemp data\pytest-tmp`.

**Dependencies:** None

**Files likely touched:**
- `src/voxcpm_app/runtime.py`
- `src/voxcpm_app/backend_server.py`
- `src/voxcpm_app/generation_service.py`
- `src/voxcpm_app/indextts2_service.py`
- `tests/test_voxcpm_app_generation_service.py`
- `tests/test_voxcpm_app_indextts2_service.py`

**Estimated scope:** Medium

### Task 2: Enforce Project-Local Runtime Paths

**Description:** Ensure all default runtime, cache, checkpoint, and test temp paths stay inside the current project workspace.

**Acceptance criteria:**
- [ ] VoxCPM2 default cache path is under `data/runtimes/voxcpm2/hf-cache`.
- [ ] IndexTTS2 default runtime path is under `data/runtimes/indextts2/`.
- [ ] IndexTTS2 default checkpoint path remains `third_party/index-tts/checkpoints/`.
- [ ] No default path points to C:, OS temp, user cache, or a cloned repo.

**Verification:**
- [ ] Add tests for default path resolution.
- [ ] Run Python tests with `--basetemp data\pytest-tmp`.
- [ ] Manually inspect `/runtime-backends` output.

**Dependencies:** Task 1

**Files likely touched:**
- `src/voxcpm_app/paths.py`
- `src/voxcpm_app/generation_service.py`
- `src/voxcpm_app/indextts2_service.py`
- `docs/technical/models-runtime.md`

**Estimated scope:** Small

### Task 3: Add Structured Runtime Errors

**Description:** Return consistent JSON errors for validation, missing runtime, missing checkpoints, runtime busy, worker failure, timeout, and missing output.

**Acceptance criteria:**
- [ ] Backend errors include `error`, `type`, `code`, and optional `details`.
- [ ] Synchronous legacy routes still return compatible failure records where expected.
- [ ] Frontend can distinguish configuration failures from synthesis failures.

**Verification:**
- [ ] Add backend route tests for non-2xx error payloads.
- [ ] Run `.\.venv\Scripts\python.exe -m pytest tests --basetemp data\pytest-tmp`.

**Dependencies:** Task 1

**Files likely touched:**
- `src/voxcpm_app/backend_server.py`
- `src/voxcpm_app/indextts2_service.py`
- `src/voxcpm_app/generation_service.py`
- `tests/test_voxcpm_app_generation_service.py`
- `tests/test_voxcpm_app_indextts2_service.py`

**Estimated scope:** Medium

### Checkpoint: Runtime Readiness

- [ ] `/runtime-backends` is the single source of truth for renderer model status.
- [ ] Missing runtime and missing checkpoints are visible before generation starts.
- [ ] Existing generation and IndexTTS2 fake-runner tests still pass.
- [ ] `npm.cmd run typecheck` passes.

## Phase 2: Parameterized Workbenches

### Task 4: Complete VoxCPM2 Production Desk Payload

**Description:** Expose the stable VoxCPM2 generation controls in the renderer and send them through the existing backend contract.

**Acceptance criteria:**
- [ ] Voice Design submits text plus optional natural-language control.
- [ ] Voice Clone submits saved voice or uploaded reference.
- [ ] Ultimate Clone submits reference audio plus transcript and does not mix control instruction into generated text.
- [ ] Payload supports `cfg_value`, `inference_timesteps`, `min_len`, `max_len`, `normalize`, `denoise`, and `retry_badcase` settings.

**Verification:**
- [ ] Add frontend type coverage for the payload.
- [ ] Add fake-backend or component-level payload tests if available.
- [ ] Run `npm.cmd run typecheck`.

**Dependencies:** Task 1

**Files likely touched:**
- `electron/renderer/src/voxcpm/VoxCPMPage.tsx`
- `electron/renderer/src/shared/types.ts`
- `electron/renderer/src/shared/api/client.ts`
- `src/voxcpm_app/generation_service.py`
- `tests/test_voxcpm_app_generation_service.py`

**Estimated scope:** Medium

### Task 5: Complete IndexTTS2 Performance Desk Payload

**Description:** Shape the IndexTTS2 page around line-level performance: script line, selected voice, emotion source, performance parameters, and generation action.

**Acceptance criteria:**
- [ ] Page requires a speaker from upload or Voice Library.
- [ ] Emotion modes are mutually exclusive: same voice, audio prompt, vector, or text prompt.
- [ ] Text emotion mode can use the line text when no explicit emotion text is supplied.
- [ ] Emotion vector total is blocked above `0.8` in UI and still validated in backend.
- [ ] Payload includes inference parameters and acceleration toggles supported by the worker boundary.

**Verification:**
- [ ] Add frontend payload/type checks.
- [ ] Add backend tests for emotion source validation and worker payload.
- [ ] Run `npm.cmd run typecheck`.
- [ ] Run `.\.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_indextts2_service.py --basetemp data\pytest-tmp`.

**Dependencies:** Task 1

**Files likely touched:**
- `electron/renderer/src/indextts2/IndexTTS2Page.tsx`
- `electron/renderer/src/shared/types.ts`
- `electron/renderer/src/shared/api/client.ts`
- `src/voxcpm_app/indextts2_service.py`
- `src/voxcpm_app/indextts2_worker.py`
- `tests/test_voxcpm_app_indextts2_service.py`

**Estimated scope:** Medium

### Task 6: Add Runtime Status to Settings

**Description:** Make model readiness and path diagnostics visible in the AppShell Settings or runtime status area.

**Acceptance criteria:**
- [ ] Settings shows VoxCPM2 and IndexTTS2 status from `/runtime-backends`.
- [ ] Missing runtime/checkpoint messages are readable and actionable.
- [ ] Active job and busy backend are visible.
- [ ] Renderer does not implement its own GPU safety logic.

**Verification:**
- [ ] Run `npm.cmd run typecheck`.
- [ ] Manual check with IndexTTS2 checkpoints absent.
- [ ] Manual check while a fake long-running job holds the runtime lease, if available.

**Dependencies:** Task 1, Task 3

**Files likely touched:**
- `electron/renderer/src/app/routes.tsx`
- `electron/renderer/src/app/AppShell.tsx`
- `electron/renderer/src/shared/api/client.ts`
- `electron/renderer/src/shared/types.ts`

**Estimated scope:** Small

### Checkpoint: Parameterized Workbenches

- [ ] VoxCPM2 page sends mode-appropriate parameters.
- [ ] IndexTTS2 page sends exactly one emotion source.
- [ ] Settings reports model readiness without attempting generation.
- [ ] Frontend typecheck passes.

## Phase 3: Job and Take Product Loop

### Task 7: Make Generation Job API the Preferred Internal Entry

**Description:** Move synchronous generation routes toward a compatibility wrapper over job creation and immediate execution.

**Acceptance criteria:**
- [ ] `POST /generation-jobs` creates a queued job for `voxcpm2` or `indextts2`.
- [ ] `GET /generation-jobs` lists current jobs.
- [ ] `GET /generation-jobs/:job_id` returns one job.
- [ ] Existing `/generate-audio` and `/indextts2/generate` still work.
- [ ] Legacy routes pass `generation_job_id` into runtime lease state.

**Verification:**
- [ ] Add backend API tests for create/list/get.
- [ ] Add compatibility tests for old routes.
- [ ] Run `.\.venv\Scripts\python.exe -m pytest tests --basetemp data\pytest-tmp`.

**Dependencies:** Task 3

**Files likely touched:**
- `src/voxcpm_app/backend_server.py`
- `src/voxcpm_app/job_queue.py`
- `src/voxcpm_app/job_store.py`
- `src/voxcpm_app/generation_service.py`
- `src/voxcpm_app/indextts2_service.py`
- `tests/`

**Estimated scope:** Medium

### Task 8: Add Storage v2 for Assets, Jobs, and Takes

**Description:** Add additive SQLite schema support for reusable audio assets, generation jobs, and generation takes without breaking existing voices and generations.

**Acceptance criteria:**
- [ ] Empty database creates assets, generation_jobs, and generation_takes tables.
- [ ] Existing database migration is additive.
- [ ] Existing VoiceRecord and GenerationRecord shapes remain compatible.
- [ ] A take can be created, listed, and selected.

**Verification:**
- [ ] Add storage migration tests.
- [ ] Run `.\.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_storage.py --basetemp data\pytest-tmp`.

**Dependencies:** Task 7 can start with current schema, but this task must finish before full multi-take UI.

**Files likely touched:**
- `src/voxcpm_app/db.py`
- `src/voxcpm_app/repositories.py`
- `src/voxcpm_app/job_store.py`
- `src/voxcpm_app/schemas.py`
- `tests/test_voxcpm_app_storage.py`

**Estimated scope:** Medium

### Task 9: Implement IndexTTS2 Multi-Take Flow

**Description:** Let one line request create multiple IndexTTS2 takes, compare them, and select one for shared history.

**Acceptance criteria:**
- [ ] User can request more than one take for the same line.
- [ ] Each take has independent output audio and status.
- [ ] Selecting a take marks it as selected and projects it into shared history.
- [ ] Failed takes preserve their error summaries without failing the entire job when other takes succeed.

**Verification:**
- [ ] Add fake-runner tests for multiple takes.
- [ ] Add API tests for take list and select.
- [ ] Run Python tests with `--basetemp data\pytest-tmp`.
- [ ] Run `npm.cmd run typecheck`.

**Dependencies:** Task 8

**Files likely touched:**
- `src/voxcpm_app/indextts2_service.py`
- `src/voxcpm_app/job_queue.py`
- `src/voxcpm_app/job_store.py`
- `src/voxcpm_app/generation_history.py`
- `electron/renderer/src/indextts2/IndexTTS2Page.tsx`
- `electron/renderer/src/jobs/JobListPage.tsx`

**Estimated scope:** Medium

### Task 10: Connect History Reuse and Save-as-Voice

**Description:** Complete the loop from generated output to reusable voice and parameter reuse.

**Acceptance criteria:**
- [ ] Successful VoxCPM2 outputs can be saved as Voice Library entries.
- [ ] Selected IndexTTS2 takes appear in History and can be replayed.
- [ ] History reuse restores backend id, mode, selected voice when available, text, control, and parameters.
- [ ] Deleted voices do not break old history records.

**Verification:**
- [ ] Add service tests for generated-output voice save.
- [ ] Run `npm.cmd run typecheck`.
- [ ] Manual AppShell flow: generate, save voice, reuse voice, regenerate.

**Dependencies:** Task 8, Task 9

**Files likely touched:**
- `src/voxcpm_app/voice_library.py`
- `src/voxcpm_app/generation_history.py`
- `src/voxcpm_app/backend_server.py`
- `electron/renderer/src/storage/HistoryPage.tsx`
- `electron/renderer/src/storage/VoiceLibraryPage.tsx`
- `electron/renderer/src/voxcpm/VoxCPMPage.tsx`
- `electron/renderer/src/indextts2/IndexTTS2Page.tsx`

**Estimated scope:** Medium

### Checkpoint: Job and Take Product Loop

- [ ] Job API creates, lists, gets, and executes jobs.
- [ ] IndexTTS2 multi-take generation works with fake runner.
- [ ] Selected take appears in shared history.
- [ ] Generated VoxCPM2 output can become an IndexTTS2 speaker through Voice Library.

## Phase 4: Real Model Acceptance

### Task 11: VoxCPM2 Real Smoke Test

**Description:** Run one real VoxCPM2 generation for each supported production mode.

**Acceptance criteria:**
- [ ] Voice Design generates audio with no reference audio.
- [ ] Voice Clone generates audio with uploaded or saved voice.
- [ ] Ultimate Clone generates audio with reference audio plus prompt transcript.
- [ ] Outputs are copied to `data/app/generations/`.
- [ ] History can play the generated media URL.

**Verification:**
- [ ] Manual smoke checklist recorded in `docs/technical/testing-acceptance.md`.
- [ ] Confirm no model cache or generated output is written outside the workspace.

**Dependencies:** Task 4, Task 10

**Files likely touched:**
- `docs/technical/testing-acceptance.md`
- Test fixture notes or scripts under `scripts/` if needed.

**Estimated scope:** Small

### Task 12: IndexTTS2 Real Smoke Test

**Description:** Run real IndexTTS2 generation for the supported emotion modes after runtime and checkpoints are configured.

**Acceptance criteria:**
- [ ] Same voice mode succeeds.
- [ ] Emotion audio mode succeeds.
- [ ] Emotion vector mode succeeds.
- [ ] Emotion text mode succeeds with and without explicit emotion text.
- [ ] Worker returns parseable JSON and output file exists.
- [ ] Outputs are copied to `data/app/generations/`.

**Verification:**
- [ ] Manual smoke checklist recorded in `docs/technical/testing-acceptance.md`.
- [ ] Confirm no runtime, cache, checkpoint, or generated output is written outside the workspace.

**Dependencies:** Task 5, Task 9

**Files likely touched:**
- `docs/technical/testing-acceptance.md`
- `scripts/prepare_indextts2_runtime.ps1` if a script is added later.

**Estimated scope:** Small

### Task 13: Concurrency and Failure Hardening

**Description:** Verify real and fake paths do not allow VoxCPM2 and IndexTTS2 to run at the same time under the default single GPU slot policy.

**Acceptance criteria:**
- [ ] Concurrent requests serialize, queue, or fail according to documented policy.
- [ ] Lease release happens after success, failure, timeout, and output-missing cases.
- [ ] `last_error` updates on failure and does not poison later successful runs.
- [ ] Running cancellation is recorded even if hard interruption is not yet supported.

**Verification:**
- [ ] Add RuntimeCoordinator tests.
- [ ] Add worker timeout tests.
- [ ] Manual concurrent AppShell request check.

**Dependencies:** Task 7

**Files likely touched:**
- `src/voxcpm_app/runtime.py`
- `src/voxcpm_app/job_queue.py`
- `src/voxcpm_app/indextts2_service.py`
- `src/voxcpm_app/generation_service.py`
- `tests/`

**Estimated scope:** Medium

### Checkpoint: Real Model Acceptance

- [ ] VoxCPM2 real smoke passes.
- [ ] IndexTTS2 real smoke passes.
- [ ] Runtime state stays accurate through success, failure, and busy cases.
- [ ] No cache, runtime, checkpoint, generated file, or pytest temp path is on C:.

## Phase 5: Hardening, Docs, and Packaging Notes

### Task 14: Update Technical Documentation

**Description:** Keep implementation docs aligned with actual API, paths, runtime behavior, and testing commands.

**Acceptance criteria:**
- [ ] `docs/technical/models-runtime.md` lists actual status fields and paths.
- [ ] `docs/technical/backend-api.md` lists implemented job, take, runtime, and compatibility routes.
- [ ] `docs/technical/testing-acceptance.md` lists exact commands and manual smoke steps.
- [ ] `docs/app-dev/06-implementation-roadmap.md` reflects completed and remaining milestones.

**Verification:**
- [ ] Review docs against route names and code paths.
- [ ] Run `git diff --check`.

**Dependencies:** Tasks 1-13

**Files likely touched:**
- `docs/technical/models-runtime.md`
- `docs/technical/backend-api.md`
- `docs/technical/testing-acceptance.md`
- `docs/app-dev/06-implementation-roadmap.md`

**Estimated scope:** Small

### Task 15: Add Packaging Readiness Notes

**Description:** Document what must be bundled or configured for a future desktop release.

**Acceptance criteria:**
- [ ] Notes cover Electron renderer, Python runtime, local FFmpeg, SQLite data root, model cache, IndexTTS2 runtime, checkpoints, and logs.
- [ ] Notes clearly state what remains source-development only.
- [ ] Notes preserve legacy Gradio route as a separate developer path.

**Verification:**
- [ ] Review against current launch scripts.
- [ ] Run `node --check electron\main.js` and `node --check electron\preload.js`.

**Dependencies:** Task 14

**Files likely touched:**
- `docs/technical/README.md`
- `docs/technical/testing-acceptance.md`
- `docs/app-dev/09-voxcpm-box-scope-and-upstream-sync.md`

**Estimated scope:** Small

### Checkpoint: Complete

- [ ] All targeted Python tests pass with `--basetemp data\pytest-tmp`.
- [ ] `npm.cmd run typecheck` passes.
- [ ] `npm.cmd run build` passes.
- [ ] `node --check electron\main.js` passes.
- [ ] `node --check electron\preload.js` passes.
- [ ] Real smoke test status is recorded.
- [ ] Docs match implemented routes, payloads, paths, and product scope.

## Parallel Execution Plan

Use configured subagents only for bounded, non-overlapping work.

- Code exploration agent: map current API, renderer payloads, job queue, history, and runtime call paths before implementation.
- Backend agent A: Runtime status, structured errors, project-local paths.
- Backend agent B: Job/take storage and API. Starts after the API shape is agreed.
- Frontend agent: VoxCPM2 and IndexTTS2 payload UI, runtime status display.
- Main agent: owns branch hygiene, interface decisions, integration review, tests, docs, and final verification.

Avoid parallel edits to the same files. If backend and frontend both need `shared/types.ts` or API contract changes, define the contract first, then split.

## Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| IndexTTS2 dependencies conflict with VoxCPM2 environment | High | Keep IndexTTS2 in project-local isolated runtime and call through subprocess worker. |
| Model downloads write outside workspace | High | Set explicit cache/runtime paths and verify before real smoke tests. |
| GPU OOM from simultaneous model loads | High | Keep single backend lease and add unload/free path before broad real testing. |
| Frontend enables invalid generation before backend is configured | Medium | Drive UI from `/runtime-backends`; backend remains final authority. |
| Job/take schema breaks existing history | Medium | Use additive migrations and compatibility projection tests. |
| Upstream API changes around VoxCPM2 seed or IndexTTS2 sampling | Medium | Only expose locally supported parameters; document deferred upstream-only fields. |
| Multi-take flow becomes too large | Medium | First support sequential fake-runner multi-take, then real worker multi-take. |
| Real smoke tests are slow or hardware-dependent | Medium | Keep fake-runner tests as CI baseline and mark real tests as manual acceptance. |

## Open Questions

- Should `generation-jobs` immediately execute by default, or should the renderer explicitly call a run action after creation?
- Should failed takes be visible in History, or only in Job detail?
- Should selected IndexTTS2 takes be saveable as reusable voices, or should only VoxCPM2 outputs become Voice Library entries by default?
- Should running-job cancellation remain cooperative in MVP, or do we need hard subprocess termination before release?
- Should VoxCPM2 denoiser stay disabled by default in AppShell for cache predictability, with an advanced toggle later?

## Deferred Work

- Streaming generation UI.
- Hard cancellation of in-process VoxCPM2 generation.
- Cross-process runtime lock.
- Automatic model download UI.
- Cloud sync and user accounts.
- Model training, LoRA management, or model-level voice tuning.
- Duration control for IndexTTS2 until upstream exposes a stable release path for it.
