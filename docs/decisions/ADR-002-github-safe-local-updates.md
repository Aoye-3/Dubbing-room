# ADR-002: Safe GitHub Updates For Local AppShell

## Status
Accepted

## Date
2026-07-06

## Context

Dubbing-room is a local-first Electron AppShell with Python services, SQLite user data, generated audio, reusable voices, model runtimes, caches, and checkpoints living inside the opened repository directory.

Users need a visible update entry in the AppShell so a local install can pull improvements from the public GitHub repository. At the same time, the update mechanism must not damage local creative work:

- `data/app/**` contains user data and generated media.
- `.venv/`, `node_modules/`, `.npm-cache/`, `.local-ffmpeg/`, `data/runtimes/`, model caches, logs, training outputs, and checkpoints are local runtime state.
- The app must not clone or copy the repository elsewhere for update operations.
- The app must not use worktrees, temporary clones, `reset --hard`, `git clean`, or automatic conflict resolution.
- Renderer code must not be able to pass arbitrary shell commands to Electron main.

## Decision

Implement the v1 updater as a fixed, same-repository, fast-forward-only GitHub update path.

Key decisions:

- The update source must normalize to the current `origin` GitHub repository.
- The target branch defaults to `main` and must pass a conservative branch-name allowlist.
- Electron main exposes fixed IPC handlers: `get-update-status`, `preflight-update`, `fetch-update`, and `apply-update`.
- Renderer code sends only `repositoryUrl` and `branch`; it cannot provide arbitrary Git arguments.
- `fetch` updates only the remote tracking ref with a fixed refspec.
- `apply` runs only `git merge --ff-only refs/remotes/origin/<branch>`.
- Preflight blocks when tracked files are dirty, protected paths are not ignored, the URL differs from `origin`, the current branch is not the target branch, or the branch name is unsafe.
- The UI reports blockers, protected paths, commits, ahead/behind counts, and log summaries.
- Successful apply asks the user to restart AppShell; the updater does not restart automatically.

## Alternatives Considered

### Pull From Any GitHub Repository

- Pros: Flexible for forks or alternative distributions.
- Cons: Higher supply-chain risk and unclear compatibility with local data migrations.
- Rejected: v1 should only update from the repository already configured as `origin`.

### `git pull` With Default Merge Behavior

- Pros: Familiar and shorter implementation.
- Cons: Can create merge commits, trigger conflicts, or mutate the working tree in ways that are hard to explain from the UI.
- Rejected: v1 must be predictable and stop instead of resolving conflicts.

### `reset --hard origin/main`

- Pros: Simple way to force the code to match remote.
- Cons: Destroys local tracked changes and violates the local-data safety requirement.
- Rejected: The updater must never discard user or developer work automatically.

### Clone Or Worktree-Based Update Staging

- Pros: Can inspect remote updates outside the current checkout.
- Cons: Violates the workspace policy for this project and increases path/cache complexity on local installs.
- Rejected: All update operations must stay inside the currently opened repository.

### Auto-Restart After Update

- Pros: User sees new code immediately.
- Cons: Can interrupt running generation jobs or leave model/runtime processes in a confusing state.
- Rejected: v1 reports success and asks the user to restart when ready.

## Consequences

- The updater is deliberately unable to resolve divergent histories. A user or maintainer must handle non-fast-forward cases manually.
- Local developer changes must be committed before applying an update.
- Ignored user data and runtime files are preserved because Git does not manage them and preflight verifies the key paths.
- Future storage paths must be added to both `.gitignore` and `PROTECTED_PATHS`.
- Any future support for forks, signed releases, migration preview, backup automation, or conflict handling requires a new ADR or a superseding decision.

## Related Documents

- `docs/technical/data-storage-and-update-policy.md`
- `docs/technical/github-safe-update-runbook.md`
- `electron/update-manager.js`
