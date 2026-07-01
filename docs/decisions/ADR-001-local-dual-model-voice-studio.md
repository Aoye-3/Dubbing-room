# ADR-001: Local Dual-Model Voice Studio

## Status
Accepted

## Date
2026-07-01

## Context
Dubbing-room is evolving from the earlier VoxCPM-Box AppShell into a local AIGC voice workflow studio. The product needs to combine two model roles:

- `VoxCPM2` for general voice generation, narration, cloning, and seed voice assets.
- `IndexTTS2` for line-level performance, emotion control, multi-take refinement, and final take selection.

The app must stay local-first: runtime files, caches, SQLite data, generated audio, and test temp files belong inside the current repository drive. The project must not depend on cloud accounts, external databases, external job services, worktrees, temporary clones, or C: drive caches.

The current code already has a local Electron AppShell, Python HTTP backend, SQLite storage, a process-local runtime lease, an in-memory FIFO job queue, Voice Library, History, IndexTTS2 generation, and job/take tables. The renderer is still too concentrated in one large application component, so the next architecture step is domain-oriented frontend modularization.

## Decision
Build Dubbing-room as a local dual-model voice studio organized around workflow domains, not as a single-model VoxCPM extension shell.

Key decisions:

- Keep `VoxCPM2` and `IndexTTS2` as distinct backend adapters behind stable AppShell APIs.
- Use additive SQLite schema evolution for local assets, voices, generations, jobs, and takes.
- Use a single process-local GPU/runtime lease so only one backend owns generation at a time.
- Use the local FIFO generation job queue for queued work, while documenting that it is not yet persistent across process restarts.
- Move the renderer toward domain directories: `app/`, `shared/`, `voxcpm/`, `indextts2/`, `jobs/`, and `storage/`.
- Route renderer-to-backend access through `shared/api` rather than direct page-level `window.voxcpmShell` calls.
- Keep the legacy Gradio/developer route available for upstream VoxCPM compatibility checks.

## Alternatives Considered

### Continue As A VoxCPM AppShell
- Pros: Smaller short-term diff and less renderer movement.
- Cons: Does not describe the IndexTTS2 workflow, multi-take selection, local asset lifecycle, or queue/runtime boundaries.
- Rejected: The product direction is now a dual-model voice workflow, not a VoxCPM-only wrapper.

### Cloud Job Service And External Database
- Pros: Easier multi-device sync and durable queue semantics.
- Cons: Violates the local-first product requirement and increases operational complexity.
- Rejected: This phase explicitly requires local operation without cloud accounts or external databases.

### Parallel Runtime Ownership
- Pros: Potentially faster for users with large GPU capacity.
- Cons: Higher OOM risk and unclear user feedback during mixed VoxCPM2/IndexTTS2 generation.
- Rejected: The current product needs predictable local execution before parallel scheduling.

### Delay Renderer Modularization
- Pros: Avoids immediate frontend churn.
- Cons: Keeps product domains coupled in one large file and makes future take workflow, unload UI, batch lines, and WebSocket state harder to add safely.
- Rejected: The renderer structure is now a product architecture blocker.

## Consequences
- Documentation and README should describe Dubbing-room as an `IndexTTS2 + VoxCPM2` local AIGC voice workflow studio.
- New renderer features should enter the domain directories rather than enlarging the application entry file.
- Backend API changes should preserve legacy IPC and synchronous generation routes during migration.
- Storage migrations must remain additive unless a separate migration plan is accepted.
- Runtime unload, persistent queue recovery, and full multi-take productization remain follow-up work, not assumptions.
