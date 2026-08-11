# Implementation Roadmap

## Phase 1: Documentation and Conventions

Current status: implemented; this documentation set and ADRs define the current paths, data boundaries, and upstream-preservation rules. Ongoing maintenance is still required when implementation changes.

Inputs:

- Current `app.py` Gradio UI.
- Current Electron shell.
- This documentation set.
- VoxCPM-Box ordinary-user scenarios: video narration, AIGC short-film dubbing, repeated voice reuse, script breakdown, batch tasks, and role profiles.

Outputs:

- Agreed data paths.
- Agreed table names and status enum.
- Implementation tasks ready for AI-assisted development.

Acceptance:

- All app docs use the same paths and table names.
- First-scope exclusions are clear.
- Upstream source preservation is documented as a default rule.

## Phase 2: Electron React App Shell

Current status: implemented as the default AppShell route.

Tasks:

- Keep Electron as the desktop entry.
- Add a Vite, React, and TypeScript renderer.
- Add `lucide-react` and use it for all sidebar and common action icons.
- Add left sidebar pages for Voice Design, Voice Cloning, Ultimate Cloning, Voice Library, History, and Settings.
- Keep AppShell lifecycle in `electron/main.js`.
- Send AppShell status to the renderer through IPC.
- Render native generation pages without embedding the current Gradio WebUI.

Acceptance:

- `npm.cmd run dev` opens the app shell instead of raw Gradio directly.
- All six pages render.
- Generation pages do not contain an iframe or webview for Gradio.
- The original Gradio WebUI still starts from `start_voxcpm.bat`.
- No hand-drawn SVG icons are introduced for shell navigation or common actions.

## Phase 3: Storage Layer

Current status: implemented for local SQLite metadata, voice audio copy, generation output copy, and service-level tests.

Tasks:

- Create `src/voxcpm_app/`.
- Add path helpers for `data/app/`.
- Add SQLite initialization and migrations.
- Add repositories for `voices` and `generations`.
- Add file-copy and checksum helpers.

Acceptance:

- A test can create a voice record and generation record in a temporary app data root.
- Soft-delete behavior hides records from default lists.
- Audio files are copied to the expected directories.

## Phase 4: App Service Integration

Current status: implemented beyond the first minimal loop. The AppShell starts a local Python backend, imports uploaded voices, generates audio with uploaded or saved voices, stores generated outputs, saves generated output as a voice, and refreshes Voice Library and History through IPC-backed backend calls. History now includes favorites, Trash, restore, permanent purge, export, and promotion-to-voice linkage.

Tasks:

- Add Voice Library selector to the AppShell generation UI.
- Add Save Voice action for uploaded reference audio.
- Add Generation History panel.
- Connect native AppShell controls to app-layer service contracts.
- Store successful output audio under `data/app/generations/`.

Acceptance:

- Saved voices survive app restart.
- A saved voice can be reused for generation.
- Successful and failed generations appear in history.

## Phase 5: Native Shell Feature Integration

Current status: partially implemented. Voice Library, History, Jobs, Settings runtime cards, result export, and the safe GitHub update page are connected. Settings cleanup controls, richer narration/dubbing workflows, and release-grade UX remain incomplete.

Tasks:

- Connect the Voice Library page to app services.
- Connect the History page to app services.
- Add Settings controls for device mode, local FFmpeg status, data path, and cleanup actions.
- Gradually replace Gradio-only controls with native React controls where the app service contract is stable.
- Add product flows for video spoken narration and AIGC short-film dubbing as AppShell workflows, not model rewrites.

Acceptance:

- Saved voices can be imported, listed, selected, edited, and soft-deleted from the app shell.
- History can be viewed, replayed, reused, regenerated, and soft-deleted from the app shell.
- Settings shows runtime and local dependency status without exposing model internals.

## Phase 6: Script, Batch, and Role Workflows

Current status: not started as product workflows. The existing FIFO generation queue is a backend primitive and does not yet provide script breakdown, multi-segment batch orchestration, or role profiles.

Tasks:

- Add Script Breakdown as an app-layer workflow for splitting long scripts into lines, scenes, or generation tasks.
- Add Batch Task Queue as an app-layer workflow for multi-segment generation tracking.
- Add Role Profiles as app-layer metadata for character names, notes, voice selection, and prompt guidance.
- Connect these workflows to Voice Library and Generation History through app adapters/services.

Acceptance:

- A script can be split into reusable generation tasks.
- Batch tasks can track status without relying on Gradio temporary state.
- Role profiles can reuse saved voices and prompt guidance.
- No model internals or core upstream source files are rewritten for these product workflows.

## Phase 7: Tests, Upstream Sync, and Packaging Preparation

Current status: partially implemented. Storage/service/job/take automation, typecheck, renderer build, Electron syntax checks, update runbook, and packaging considerations exist. Renderer/IPC/E2E automation, real-model smoke records, and distributable desktop packaging remain open.

Tasks:

- Add storage-layer tests.
- Add callback-level tests for generation history lifecycle.
- Add Electron lifecycle smoke test.
- Add upstream-sync checks for the legacy/developer Gradio route and AppShell route.
- Document future packaging requirements.

Acceptance:

- Tests verify schema creation, voice save, history save, soft delete, and output path behavior.
- Upstream pull verification confirms both preserved source behavior and AppShell startup.
- Packaging notes list Python runtime, Electron files, local FFmpeg, SQLite data location, and model cache considerations.

## Current Dual-Model Implementation Status

Status date: 2026-08-07

Phase 1 runtime readiness, Phase 2 parameterized workbenches, and the basic Phase 3 job/take product loop from `docs/Plan/11-dual-model-execution-plan.md` are implemented in the current code baseline.

Implemented:

- `/runtime-backends` exposes backend state, global busy status, active backend,
  runtime paths, missing checkpoint details, and project-local override errors.
- VoxCPM2 generation forwards length and bad-case retry controls and uses
  `data/runtimes/voxcpm2/hf-cache` as the default model cache.
- IndexTTS2 validates runtime/checkpoint readiness, preserves worker error
  codes/details, enforces emotion vector total <= `0.8`, and forwards
  acceleration toggles.
- Settings renders runtime readiness cards for VoxCPM2 and IndexTTS2.
- VoxCPM2 and IndexTTS2 pages expose the implemented Phase 2 controls.
- Additive storage provides `assets`, `generation_jobs`, and `generation_takes` while preserving legacy Voice Library and History records.
- Generation job APIs provide create/list/get, queued cancel, retry, and take list/select operations.
- IndexTTS2 queued jobs create 1-5 takes, project a selected successful take to History, and expose playback assets.
- Generated outputs and successful takes can be copied into Voice Library for reuse.
- History supports favorites, Trash, restore, permanent purge, export, and promotion-to-voice linkage.

Verified:

- Python targeted tests: 45 passed in 10.01s.
- TypeScript typecheck: passed.
- Renderer build: passed; 1717 modules transformed.
- Electron syntax checks: passed.
- Diff whitespace check: passed; working-tree CRLF warnings only.
- IndexTTS2 project-local runtime Python and the documented checkpoint inventory are present.

Next roadmap focus:

- Run and record real VoxCPM2 and IndexTTS2 smoke tests; resource presence alone is not inference acceptance.
- Add Renderer, Electron IPC, and desktop E2E coverage for status/error and core user flows.
- Define real unload/free, running cancellation, restart recovery, and cross-process runtime behavior.
- Productize take comparison and decide whether Phase 6 workflows or desktop packaging comes next.
