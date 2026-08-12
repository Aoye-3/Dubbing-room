# IndexTTS-2.5 Replacement And Performance Desk Plan

## Overview

This plan replaces the current IndexTTS 2.0 runtime adapter with a pinned IndexTTS-2.5 adapter while preserving Dubbing-room's shared Voice Library, History, jobs/takes, media paths, and `indextts2` backend identity. It also reshapes the Performance Desk around the 2.5 language, duration, pronunciation, emotion, and capability contracts.

This plan is now in staged execution. Implementation status and remaining real-model gates are tracked in [IndexTTS-2.5 implementation status](../technical/indextts25-implementation-status.md).

Plan date: 2026-08-12.

## Execution Snapshot

| Workstream | Status | Evidence |
| --- | --- | --- |
| Pinned source and manifest | Implemented | Fixed commit, license hash, 337-file manifest, mapped Pinyin asset, verifier tests |
| Versioned runtime and Settings | Implemented | 2.0/2.5 isolation, mismatch diagnostics, persisted profile, API/IPC/UI tests |
| Job worker and storage | Implemented and review-verified | One process/load per job, JSONL events, cancellation race coverage, schema-v5 identity and warnings |
| Performance Desk | Implemented and review-verified | Validated job mapper, take comparison/actions, pronunciation helpers, structured errors, renderer tests |
| Real model acceptance | Blocked by user-installed assets | Official 2.5 config and weights are absent; runtime correctly reports `missing_checkpoints` |

The detailed checklists below remain the acceptance record. The consolidated automated run passed 142 Python tests and 35 renderer tests, plus typecheck, production build, Electron syntax, source verification, and diff checks. Hardware/model items remain open until the licensed assets are installed.

Research inputs:

- Local source, runtime, API, renderer, tests, and docs audit.
- [IndexTTS-2.5 upstream contract baseline](../technical/indextts25-upstream-contract.md).
- [ADR 0004: Versioned IndexTTS-2.5 Runtime Adapter](../app-dev/adr/0004-indextts25-versioned-runtime-adapter.md).
- Official upstream pinned at [`a371df7d0746a0ae7fdf075798b6b04e34a0132e`](https://github.com/index-tts/index-tts/commit/a371df7d0746a0ae7fdf075798b6b04e34a0132e).

## Success Criteria

The replacement is complete only when all of the following are true:

- Runtime readiness identifies an exact pinned 2.5 source and a complete 2.5 checkpoint family.
- A 2.0/2.5 source, config, or checkpoint mismatch fails before model construction with a structured error.
- The worker imports `infer_v2_5`, maps BF16 and optional QwenEmotion correctly, and supplies required `lang` plus `duration_factor`.
- Existing Voice Library entries and existing 2.0 History/job/take records remain readable.
- New jobs, takes, and generations record IndexTTS-2.5 and the effective parameter set.
- The Performance Desk supports the five official languages, proportional duration control, conditional text emotion, and language-aware pronunciation guidance.
- Multi-take comparison is available from the Performance Desk flow, not only through a separate Jobs navigation detour.
- Automated adapter, API, storage, renderer, and mismatch tests pass.
- Real-model acceptance is recorded for supported core flows on the target machine.
- Distribution and voice-authorization requirements receive human review.

## Scope

In scope:

- pinned upstream source snapshot and manifest;
- project-local 2.5 runtime and checkpoint-family preparation;
- runtime readiness/capability contract;
- worker, service, API, IPC, job/take, History, and type changes;
- Performance Desk information architecture and controls;
- targeted automated and real-model acceptance;
- documentation and rollback runbook.

Out of scope for this replacement:

- vLLM production serving;
- TensorRT/Triton for 2.5;
- a public HTTP streaming protocol;
- model training or fine-tuning;
- arbitrary renderer-to-HuggingFace generation kwargs;
- changing the stable `indextts2` backend id;
- inventing unsupported Spanish/Arabic pronunciation annotation tools;
- bundling or redistributing model weights before license review.

## Evidence-Based Current Baseline

| Area | Current local behavior | Migration impact |
| --- | --- | --- |
| Source | Vendored IndexTTS 2.0 without upstream SHA manifest | Replace with pinned 2.5 snapshot and add traceability |
| Model assets | 2.0 BPE, feature matrices, Qwen directory, auxiliary codec inventory | Use separate 2.5 Tiktoken and `codec.pth` inventory |
| Worker import | `indextts.infer_v2.IndexTTS2` | Change to `infer_v2_5` |
| Precision | `use_fp16` | Replace with `use_bf16`; publish support/fallback |
| Language | No explicit language field | Require `ZH | EN | JA | ES | AR` |
| Duration | No proportional duration control | Add `duration_factor` 0.5..2.0 |
| Text emotion | Assumed present | Conditional on `use_qwen_emo` and runtime capability |
| Emotion | Four mutually exclusive modes; vector total <= 0.8 | Preserve discriminated contract |
| Process | One new model-loading subprocess per take | Benchmark before retaining or changing lifecycle |
| API identity | `backend_id=indextts2`, `model_id=IndexTTS2` | Keep backend id; version model identity |
| UI | Sync and queue payload construction duplicated; takes shown in Jobs page | Share typed mapper; make queue/multi-take the primary desk flow |
| Tests | Strong fake-runner/service/storage coverage; no renderer tests or real model record | Add version/mapping/UI tests and real acceptance |

## Target Contract

### Runtime status

Extend the existing `RuntimeBackendStatus` without replacing its compatibility fields:

```json
{
  "backend_id": "indextts2",
  "display_name": "IndexTTS-2.5",
  "configured": true,
  "state": "configured",
  "model_id": "IndexTTS-2.5",
  "model_version": "2.5",
  "upstream_commit": "a371df7d0746a0ae7fdf075798b6b04e34a0132e",
  "languages": ["ZH", "EN", "JA", "ES", "AR"],
  "precision_modes": ["fp32", "bf16"],
  "supports_duration_factor": true,
  "supports_text_emotion": true,
  "supports_streaming": false,
  "warnings": []
}
```

`supports_text_emotion` reflects whether QwenEmotion is actually configured for the worker profile. `precision_modes` reflects the selected device, not a static model claim.

### Generation request

Keep the existing external naming style for a surgical migration:

```typescript
type IndexTTS25Language = "ZH" | "EN" | "JA" | "ES" | "AR";

type IndexTTS25Payload = {
  text: string;
  language: IndexTTS25Language;
  speaker: UploadReference | SavedVoiceReference;
  emotion_mode: "same_voice" | "audio_prompt" | "vector" | "text_prompt";
  emotion_audio?: UploadReference;
  emo_alpha: number;
  emo_vector?: EmotionVector8;
  emo_text?: string;
  use_random: boolean;
  duration_factor: number;
  text_normalization: boolean;
  interval_silence: number;
  max_text_tokens_per_segment: number;
  top_p: number;
  top_k: number;
  temperature: number;
  length_penalty: number;
  num_beams: number;
  repetition_penalty: number;
  max_mel_tokens: number;
  take_count?: number;
};
```

Model-load settings such as BF16, CUDA kernel, DeepSpeed, acceleration engine, Torch compile, and QwenEmotion belong to runtime settings/capabilities. They must not be duplicated in every line-performance request after the migration.

The current `do_sample` UI is removed or shown read-only until the pinned upstream call path actually honors it.

### Identity and compatibility

- Stable backend id: `indextts2`.
- New model id: `IndexTTS-2.5`.
- New model version: `2.5`.
- Old records without version metadata are interpreted as legacy/unknown and displayed without rewriting stored history.
- Old `source_mode=indextts2-performance` remains valid.
- Existing project-relative audio and 22.05 kHz WAV handling remains valid.

## Frontend Operation And Information Architecture

### Primary Performance Desk

Use a three-region desktop layout while keeping current AppShell visual conventions:

```text
Left rail                Main authoring area                  Right production area
Runtime/version          Script and language                 Current job status
Readiness/action         Speaker reference                   Take comparison
Queue action             Duration factor                     Playback/selection
                         Emotion mode and fields              Save/export
                         Pronunciation helper
                         Expert accordion
```

The primary action is `Generate takes`. A secondary `Quick preview` may retain the synchronous single-take compatibility route, but it must be labelled as one take and share the same typed payload builder.

### Always-visible controls

- target script;
- language: Chinese, English, Japanese, Spanish, Arabic;
- speaker from Voice Library or uploaded audio;
- duration factor slider from 0.5 to 2.0, default 1.0, labelled with `faster` and `slower` guidance rather than target seconds;
- emotion mode;
- mode-specific emotion control;
- take count 1..5;
- generate action.

### Conditional controls

- emotion reference audio only for `audio_prompt`;
- eight-vector editor, total meter, and random option only for `vector`;
- emotion description only for `text_prompt`;
- text-emotion mode disabled with an explanation when runtime capability is false;
- pronunciation annotation helper for ZH, EN, and JA only;
- a reference-audio notice that upstream uses at most the first 15 seconds.

### Expert controls

- text normalization;
- interval silence;
- maximum text tokens per segment;
- top-p, top-k, temperature, beam count, penalties, and maximum mel tokens.

Runtime-load controls move to Settings:

- FP32/BF16 profile;
- CUDA kernel;
- DeepSpeed;
- acceleration engine;
- Torch compile;
- QwenEmotion loading.

Changing a runtime-load setting must state that it applies to subsequent worker/model loads. It must not masquerade as a per-take creative parameter.

### Take comparison

The right production area polls the created job and displays 1..5 takes with:

- take number and status;
- audio playback;
- exact language, duration, emotion, and expert parameter summary;
- structured warning/error summary;
- select action;
- selected marker;
- save selected take as Voice Library entry;
- export selected audio.

The existing Jobs page remains a global queue/history view. It is not the required navigation step for comparing the current Performance Desk request.

### Validation and disabled states

Generate is disabled when:

- AppShell or backend is unavailable;
- runtime is missing, mismatched, or busy without queue acceptance;
- text is empty;
- speaker reference is missing;
- language is missing/unsupported;
- the selected emotion mode lacks its required input;
- vector total exceeds 0.8;
- text emotion is unavailable;
- duration factor is outside 0.5..2.0.

All backend validation remains authoritative. Renderer validation is only immediate feedback.

## Dependency Graph

```text
Pinned source manifest + 2.5 asset-family detector
  -> runtime readiness and capabilities
  -> worker constructor/infer mapping
  -> service/API types and structured errors
  -> sync compatibility + queued multi-take
  -> Performance Desk controls and take comparison
  -> real-model acceptance
  -> 2.0 asset retirement and documentation completion
```

## Phase 0: Freeze The Reproducible Baseline

### Task 1: Add upstream source manifest and acquisition verification

**Description:** Define a tracked manifest for the vendored IndexTTS snapshot, including upstream repository, full commit, acquisition date, license hash, and expected source files.

**Acceptance criteria:**

- [ ] The manifest identifies the pinned 2.5 commit and license.
- [ ] A check distinguishes the current untracked 2.0 snapshot from the accepted 2.5 snapshot.
- [ ] Source refresh instructions do not clone, create a worktree, or write outside the current repository.

**Verification:**

- [ ] Run the manifest/source verification command against the vendored tree.
- [ ] Review the source diff and license before accepting the snapshot.

**Dependencies:** None

**Files likely touched:**

- `third_party/index-tts/UPSTREAM_MANIFEST.json`
- `scripts/verify_indextts_upstream.py`
- `.gitignore`
- `docs/technical/indextts25-upstream-contract.md`

**Estimated scope:** Medium

### Task 2: Define a non-destructive 2.5 runtime and asset layout

**Description:** Prepare a project-local 2.5 environment and model directory without overwriting the existing 2.0 assets used for rollback.

**Acceptance criteria:**

- [ ] Runtime, UV, HF, Torch, and compiler caches remain under `data/runtimes/indextts2/`.
- [ ] 2.5 checkpoints live in a distinct project-local directory during migration.
- [ ] The preparation script reports exact install/download commands and does not imply that creating folders installed the model.
- [ ] No dependency, cache, build output, virtual environment, or model asset is placed on C:.

**Verification:**

- [ ] Inspect all resolved paths before dependency installation or model download.
- [ ] Confirm that the existing 2.0 directory is unchanged.

**Dependencies:** Task 1

**Files likely touched:**

- `scripts/prepare_indextts2_runtime.ps1`
- `src/voxcpm_app/indextts2_service.py`
- `README.md`

**Estimated scope:** Small

### Checkpoint: Reproducible baseline

- [ ] Human confirms the pinned commit and license review boundary.
- [ ] Source and asset rollback paths are explicit.
- [ ] No implementation proceeds against unversioned `main`.

## Phase 1: Versioned Runtime Readiness

### Task 3: Replace the 2.0 checkpoint inventory with version-aware detection

**Description:** Detect source, config, and model asset family before launching any worker.

**Acceptance criteria:**

- [ ] A complete 2.5 inventory reports configured.
- [ ] 2.0 source plus 2.5 assets and 2.5 source plus 2.0 assets report `model_version_mismatch`.
- [ ] Missing Tiktoken, codec, config, or auxiliary assets are listed separately.
- [ ] Runtime status includes model id, model version, upstream commit, languages, precision modes, and capability booleans.

**Verification:**

- [ ] Add status tests for complete, missing, mixed, and project-external paths.
- [ ] Run `\.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_indextts2_service.py --basetemp data\pytest-tmp`.

**Dependencies:** Tasks 1-2

**Files likely touched:**

- `src/voxcpm_app/indextts2_service.py`
- `src/voxcpm_app/runtime.py`
- `tests/test_voxcpm_app_indextts2_service.py`

**Estimated scope:** Medium

### Task 4: Separate runtime-load settings from line request parameters

**Description:** Define one validated worker profile for device, BF16, QwenEmotion, and optional acceleration features.

**Acceptance criteria:**

- [ ] `use_fp16` is not sent to the 2.5 constructor.
- [ ] BF16 is enabled only when the selected device supports it; fallback is visible.
- [ ] Text-emotion capability matches QwenEmotion availability.
- [ ] Per-line payloads cannot arbitrarily change the active worker profile.

**Verification:**

- [ ] Unit tests cover BF16 supported, BF16 fallback, Qwen enabled, and Qwen disabled profiles.

**Dependencies:** Task 3

**Files likely touched:**

- `src/voxcpm_app/indextts2_service.py`
- `src/voxcpm_app/indextts2_worker.py`
- `electron/renderer/src/shared/types.ts`
- `tests/test_voxcpm_app_indextts2_service.py`

**Estimated scope:** Medium

### Checkpoint: Runtime contract

- [ ] Settings can explain exactly why 2.5 is ready or unavailable.
- [ ] Text emotion is never offered when the worker profile cannot load it.
- [ ] Mixed model families fail before GPU allocation.

## Phase 2: Worker And Backend Cutover

### Task 5: Add failing 2.5 worker contract tests

**Description:** Pin the intended constructor and inference mapping with a fake `infer_v2_5.IndexTTS2` before changing the worker.

**Acceptance criteria:**

- [ ] Tests require `lang`, `duration_factor`, and `text_normalization` at inference.
- [ ] Tests require `use_bf16` and optional `use_qwen_emo` at construction.
- [ ] Tests prove four emotion modes are mutually exclusive.
- [ ] Tests prove expert values are validated rather than forwarded arbitrarily.

**Verification:**

- [ ] Run the new tests and observe the expected pre-implementation failures.

**Dependencies:** Task 4

**Files likely touched:**

- `tests/test_voxcpm_app_indextts2_service.py`

**Estimated scope:** Small

### Task 6: Switch the worker to the 2.5 module and contract

**Description:** Import `infer_v2_5`, construct the pinned 2.5 model, and map only the approved inference inputs.

**Acceptance criteria:**

- [ ] The worker imports `indextts.infer_v2_5.IndexTTS2`.
- [ ] `lang`, duration factor, text normalization, emotion, silence, and expert values reach `infer` with correct defaults.
- [ ] `do_sample` is not advertised as configurable while upstream ignores it.
- [ ] Missing output, timeout, mismatch, BF16 fallback, Qwen unavailable, and truncation warnings produce structured codes/details.

**Verification:**

- [ ] Worker contract tests pass.
- [ ] Existing failure, timeout, output, and project-local cache tests pass.

**Dependencies:** Task 5

**Files likely touched:**

- `src/voxcpm_app/indextts2_worker.py`
- `src/voxcpm_app/indextts2_service.py`
- `tests/test_voxcpm_app_indextts2_service.py`

**Estimated scope:** Medium

### Task 7: Version generation, job, take, and History metadata

**Description:** Preserve the stable backend id while attributing new results to 2.5 and retaining old records.

**Acceptance criteria:**

- [ ] New queued jobs use model id `IndexTTS-2.5`.
- [ ] New generation/take parameter snapshots include language, duration factor, and model version.
- [ ] Existing legacy rows load without destructive backfill.
- [ ] History reuse restores supported 2.5 fields and handles legacy missing fields with documented defaults.

**Verification:**

- [ ] Add storage/job/history compatibility fixtures for old and new records.
- [ ] Run targeted storage and generation-service tests.

**Dependencies:** Task 6

**Files likely touched:**

- `src/voxcpm_app/job_queue.py`
- `src/voxcpm_app/job_store.py`
- `src/voxcpm_app/generation_history.py`
- `tests/test_voxcpm_app_generation_service.py`
- `tests/test_voxcpm_app_storage.py`

**Estimated scope:** Medium

### Checkpoint: Backend cutover

- [ ] Sync one-take and queued multi-take fake-runner flows pass.
- [ ] Old data remains readable.
- [ ] New data records an exact model identity.
- [ ] Backend and Electron preserve structured error code/details.

## Phase 3: Performance Desk Contract And UI

### Task 8: Introduce a single typed 2.5 form-to-request mapper

**Description:** Remove the current drift risk between duplicated sync and queue payload construction.

**Acceptance criteria:**

- [ ] Sync preview and queued generation use one pure typed mapper.
- [ ] Language and duration are required and range-checked.
- [ ] Emotion is represented as a discriminated union.
- [ ] Runtime-load flags are absent from line requests.

**Verification:**

- [ ] Add mapper unit tests for all languages, all emotion modes, invalid vector total, and invalid duration.
- [ ] Run `npm.cmd run typecheck`.

**Dependencies:** Task 7

**Files likely touched:**

- `electron/renderer/src/shared/types.ts`
- `electron/renderer/src/indextts2/IndexTTS2Page.tsx`
- a focused mapper test/module under `electron/renderer/src/indextts2/`

**Estimated scope:** Medium

### Task 9: Add language, duration, pronunciation, and capability-aware controls

**Description:** Implement the always-visible and conditional controls defined above.

**Acceptance criteria:**

- [ ] Five official languages are selectable and sent as API values.
- [ ] Duration factor is labelled as proportional duration/speed, not target seconds.
- [ ] ZH/EN/JA annotation helpers insert the 2.5 syntax; ES/AR do not claim unsupported helpers.
- [ ] Text emotion is visibly experimental and disabled when unsupported.
- [ ] Reference audio explains the 15-second upstream truncation.
- [ ] Generate is disabled for all known invalid states.

**Verification:**

- [ ] Renderer tests cover field visibility, disabled states, and emitted payloads.
- [ ] Run typecheck and renderer build.

**Dependencies:** Task 8

**Files likely touched:**

- `electron/renderer/src/indextts2/IndexTTS2Page.tsx`
- `electron/renderer/src/app/i18n.ts`
- `electron/renderer/src/styles.css`
- renderer tests

**Estimated scope:** Medium

### Task 10: Integrate current-job take comparison into the desk

**Description:** Make queued generation the main workflow and show its takes in the Performance Desk's production area.

**Acceptance criteria:**

- [ ] Submitting returns a current job and begins bounded polling.
- [ ] Takes show status, playback, warnings/errors, parameter summary, and selection.
- [ ] Selected take can be exported and saved as a voice.
- [ ] The global Jobs page remains usable and is not duplicated wholesale.
- [ ] Leaving the page stops its polling without changing the job.

**Verification:**

- [ ] Component tests cover partial take failure, selection, save, and polling cleanup.
- [ ] Manual flow: submit three takes, compare, select, save, and find the selected result in History.

**Dependencies:** Task 9

**Files likely touched:**

- `electron/renderer/src/indextts2/IndexTTS2Page.tsx`
- a small reusable take presentation component if justified by current Jobs code
- `electron/renderer/src/jobs/JobListPage.tsx`
- `electron/renderer/src/shared/api/client.ts`
- renderer tests

**Estimated scope:** Medium

### Checkpoint: Performance Desk

- [ ] A user can configure, submit, compare, select, save, and export without leaving the desk.
- [ ] Basic controls are understandable without reading model internals.
- [ ] Expert and runtime-load controls are separated.
- [ ] Frontend tests, typecheck, and build pass.

## Phase 4: Worker Lifecycle Decision And Real Acceptance

### Task 11: Benchmark cold-load and multi-take lifecycle

**Description:** Measure the current per-take subprocess design before accepting it or replacing it.

**Acceptance criteria:**

- [ ] Record one-take and three-take startup time, synthesis time, peak VRAM, and teardown behavior.
- [ ] Record failure recovery and RuntimeCoordinator lease release.
- [ ] Compare per-take subprocess with one persistent worker per queued job if the cold-load cost is material.
- [ ] Update ADR 0004 to Accepted with the chosen lifecycle or replace it with a superseding ADR.

**Verification:**

- [ ] Benchmark record includes hardware, driver, CUDA, precision profile, model/source commit, and input fixture hashes.

**Dependencies:** Task 7

**Files likely touched:**

- `docs/technical/models-runtime.md`
- `docs/app-dev/adr/0004-indextts25-versioned-runtime-adapter.md`
- worker/service code only if the evidence selects a lifecycle change

**Estimated scope:** Medium

### Task 12: Run the real-model acceptance matrix

**Description:** Verify the product contract against real 2.5 weights on the target machine.

**Acceptance criteria:**

- [ ] ZH, EN, JA, ES, and AR basic synthesis succeeds.
- [ ] Cross-language speaker reference succeeds for the supported target-language matrix.
- [ ] Same voice, emotion audio, vector, and available text emotion modes succeed.
- [ ] Duration factors 0.5, 1.0, and 2.0 produce monotonic duration changes.
- [ ] ZH Pinyin, EN CMU, and JA Kana annotations are exercised.
- [ ] Qwen-disabled capability degradation, BF16 fallback, >15-second reference, low-VRAM long text, and max-mel warning are recorded.
- [ ] Output remains playable 22.05 kHz int16 WAV and integrates with take selection, History, export, and Voice Library.

**Verification:**

- [ ] Save a dated acceptance record with sanitized inputs, output metadata, expected/actual results, logs, and environment identity.
- [ ] Do not commit private voice references or model weights.

**Dependencies:** Tasks 6, 10, 11

**Files likely touched:**

- `docs/technical/testing-acceptance.md`
- `docs/technical/models-runtime.md`
- sanitized test fixture metadata

**Estimated scope:** Medium

### Checkpoint: Real model

- [ ] The chosen lifecycle is evidence-backed.
- [ ] Core language, duration, emotion, pronunciation, and integration flows pass.
- [ ] Known upstream limitations are visible rather than hidden.

## Phase 5: Cutover, Rollback, And Documentation

### Task 13: Make 2.5 the supported default and retire 2.0 runtime assumptions

**Description:** Switch user-facing defaults only after real acceptance, while retaining a bounded rollback path until sign-off.

**Acceptance criteria:**

- [ ] UI, status, job defaults, and setup docs identify IndexTTS-2.5.
- [ ] No active code path imports `infer_v2` for the AppShell 2.5 backend.
- [ ] No readiness check requires 2.0 BPE/feature assets for 2.5.
- [ ] Rollback restores the previous source/config/runtime pointer without rewriting user data.
- [ ] Obsolete 2.0 assets are removed only after explicit human approval and backup/retention review.

**Verification:**

- [ ] Search for stale AppShell `use_fp16`, `infer_v2`, 2.0 checkpoint assumptions, and ambiguous `model_id` writes.
- [ ] Execute the rollback rehearsal before deleting anything.

**Dependencies:** Task 12

**Files likely touched:**

- `README.md`
- `docs/technical/models-runtime.md`
- `docs/technical/backend-api.md`
- `docs/technical/frontend.md`
- `docs/app-dev/04-api-contracts.md`
- `docs/app-dev/05-ui-workflows.md`
- `docs/app-dev/06-implementation-roadmap.md`
- setup/runtime scripts

**Estimated scope:** Medium

### Task 14: Complete license, authorization, and release review

**Description:** Confirm that the planned distribution and product flow comply with the upstream license and voice-use requirements.

**Acceptance criteria:**

- [ ] Human review decides whether source, runtime, and weights may be bundled or must remain user-installed.
- [ ] Required notices and derivative-work statements are included where applicable.
- [ ] Voice upload/clone flows include authorization and misuse guidance.
- [ ] README does not describe the custom license as unconditional commercial permission.

**Verification:**

- [ ] Release checklist records reviewer and decision date.

**Dependencies:** Task 1; must complete before distribution

**Files likely touched:**

- `README.md`
- license/notice documentation
- relevant upload/clone UI copy

**Estimated scope:** Small

### Checkpoint: Replacement complete

- [ ] Automated suites, typecheck, build, Electron checks, and diff checks pass.
- [ ] Real-model acceptance is recorded.
- [ ] Documentation reflects implemented behavior rather than planned behavior.
- [ ] 2.0 rollback/retirement is explicitly approved.
- [ ] Product and license review is complete.

## Verification Command Set

Use the repository-local environments and caches:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_indextts2_service.py tests\test_voxcpm_app_generation_service.py tests\test_voxcpm_app_storage.py --basetemp data\pytest-tmp
npm.cmd run typecheck
npm.cmd run build
node --check electron\main.js
node --check electron\preload.js
git diff --check
```

Add focused renderer test commands when the test runner is introduced. Real-model commands must use `data/runtimes/indextts2/` and a project-local model directory.

## Risks And Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| No formal 2.5 tag/package version | Reproducibility failure | Pin full source SHA and validate a tracked manifest |
| Mixed 2.0/2.5 assets | Import/load errors or undefined output | Separate directories and asset-family preflight |
| Repeated model load for each take | Slow multi-take workflow | Benchmark early; decide persistent-per-job worker from evidence |
| Text emotion unavailable on low VRAM | UI offers a failing control | Publish effective capability and disable with explanation |
| BF16 unsupported | Worker failure | Device capability preflight and visible FP32 fallback |
| Upstream ignores `do_sample` input | Misleading UI | Remove/disable until verified fixed |
| Arabic normalization branch differs | Incorrect numbers/punctuation | Dedicated Arabic acceptance fixtures |
| Long reference silently truncated | User confusion | Show 15-second notice and structured warning |
| Electron drops error details | Unactionable failures | Preserve structured code/details across HTTP/IPC/client |
| Model license misunderstood | Distribution/commercial risk | Human review and required notices before release |
| Old records lose identity | History ambiguity | Stable backend id plus explicit model/version on new records |
| Update damages user assets | Data loss | Keep user/model/runtime paths protected and rehearse rollback |

## Open Questions Requiring Human Review

- Which target GPU classes define release support and the low-VRAM product profile?
- Should the final supported setup download weights into a dedicated `third_party` model directory or a versioned `data/runtimes` model directory? Both must remain project-local; the decision affects backup and update policy.
- After benchmarking, is per-take isolation acceptable, or should one queued job reuse one resident model process?
- Should text emotion be enabled by default on capable GPUs, or remain an opt-in runtime profile because of memory cost?
- May the distributable package include the IndexTTS source/runtime, and may it include weights under the intended release model?
- How long should the 2.0 rollback assets be retained after 2.5 acceptance?

These questions do not block contract tests and non-destructive adapter work. They do block final runtime topology, packaging, and 2.0 asset deletion.
