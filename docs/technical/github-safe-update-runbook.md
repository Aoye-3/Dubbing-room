# GitHub Safe Update Runbook

## Purpose

This document records the implemented update path for the Electron AppShell. It is the maintenance reference for future changes to local storage, media generation, runtime files, and the GitHub update entry.

The update feature is intentionally conservative:

- It only updates tracked source files from the current `origin` GitHub repository.
- It never uploads or indexes local user data.
- It never runs `reset --hard`, never deletes ignored files, and never resolves merge conflicts automatically.
- It only applies updates with `git merge --ff-only refs/remotes/origin/<branch>`.

## Current Implementation

| Layer | File | Responsibility |
| --- | --- | --- |
| Electron main | `electron/update-manager.js` | Fixed Git operations, protected path checks, URL validation, preflight, fetch, apply |
| Electron IPC | `electron/main.js` | Exposes fixed channels: `get-update-status`, `preflight-update`, `fetch-update`, `apply-update` |
| Preload bridge | `electron/preload.js` | Exposes typed renderer-safe methods on `window.voxcpmShell` |
| Renderer API | `electron/renderer/src/shared/api/client.ts` | Wraps update IPC for React pages |
| Renderer page | `electron/renderer/src/updates/UpdatePage.tsx` | Shows remote, commits, ahead/behind, blockers, protected paths, and logs |
| Navigation | `electron/renderer/src/app/navigation.tsx` | Adds the left-side `updates` entry |
| Shared types | `electron/renderer/src/shared/types.ts` and `electron/renderer/src/vite-env.d.ts` | Defines `UpdateStatus`, `UpdateActionResult`, and `UpdateRequest` |

## User Data Boundary

The AppShell treats `data/app/**` as local user data. The updater must not modify, upload, delete, or reinitialize this tree.

Current user-data paths:

```text
data/app/app.sqlite3
data/app/voices/
data/app/generations/
data/app/tmp/
```

Current storage chain:

- Imported reusable voices are stored under `data/app/voices/` and recorded in the `voices` table.
- Generated audio is stored under `data/app/generations/` and recorded through `generations` or `assets`.
- Temporary uploaded references and intermediate files use `data/app/tmp/`.
- Job/take output assets are stored as local files and referenced by `generation_takes.output_asset_id`.
- Selecting an IndexTTS2 take updates the selected take and keeps the legacy History projection available.
- Prompt text is currently stored as part of generation/job/take records, not as a separate prompt library.

Future user-data paths should stay under `data/app/`, for example:

```text
data/app/projects/
data/app/config/
data/app/prompt-presets/
```

## Local Runtime Boundary

These paths are local runtime, dependency, cache, model, test, or training artifacts. They are not user creative data, but they are also not public repository content.

```text
data/runtimes/
data/model-cache/
data/pytest-tmp/
.pytest-tmp/
.venv/
node_modules/
dist/
.npm-cache/
.local-ffmpeg/
*.log
logs/
runs/
tensorboard/
lora/
checkpoints/
```

IndexTTS2 checkpoint handling has a special repository exception:

```text
third_party/index-tts/checkpoints/config.yaml
third_party/index-tts/checkpoints/pinyin.vocab
```

The config and vocabulary are allowed in the repository; model weights remain ignored.

## Public Repository Content

The updater may receive updates to tracked project files such as:

```text
src/
electron/
scripts/
conf/
examples/
assets/
docs/
tests/
third_party/index-tts/ source files, excluding ignored checkpoint weights
package.json
package-lock.json
pyproject.toml
uv.lock
vite.config.ts
tsconfig.json
README.md
```

Examples and defaults in `conf/` are development templates. User-specific configuration should not be written there; prefer SQLite or ignored files under `data/app/config/`.

## Update Flow

### 1. Status

`getUpdateStatus(projectDir, options)` collects:

- current branch
- current commit
- `origin` URL
- dirty tracked files
- protected path ignore status
- remote tracking commit for `origin/<branch>`
- ahead/behind counts
- blockers

The UI uses this result to show whether the app is blocked, up to date, or has an update available.

### 2. Preflight

`preflightUpdate` is a read-only status check.

It blocks when:

- the branch name is unsafe
- the requested GitHub URL does not normalize to the current `origin`
- the current branch is not the requested target branch
- tracked files are dirty
- protected local paths are not ignored

### 3. Fetch

`fetchUpdate` runs only a fixed Git command:

```text
git fetch origin +refs/heads/<branch>:refs/remotes/origin/<branch>
```

Fetch is still blocked by dirty tracked files, URL mismatch, unsafe branch names, and unignored protected paths. It may run while the current branch differs from the target branch, because it only updates the remote tracking ref and does not touch the working tree.

### 4. Apply

`applyUpdate` requires preflight to pass and `behind > 0`, then runs:

```text
git merge --ff-only refs/remotes/origin/<branch>
```

If fast-forward is impossible, the updater stops and reports the Git error. It does not run normal merge, rebase, checkout, reset, clean, stash, or conflict resolution.

After a successful apply, the UI tells the user to restart AppShell. It does not restart the app automatically.

## Security Constraints

Renderer code cannot pass arbitrary shell commands. It can only call fixed IPC channels with:

```ts
type UpdateRequest = {
  repositoryUrl: string;
  branch: string;
};
```

The main process validates:

- GitHub URLs by normalizing both requested URL and current `origin`.
- Branch names with a conservative allowlist.
- Protected paths with `git check-ignore --quiet -- <path>`.
- Dirty tracked files with `git status --porcelain --untracked-files=no`.

The implementation uses `execFile("git", args, ...)` with fixed argument arrays rather than shell command strings.

## Maintenance Checklist

When changing storage, runtime paths, or update behavior:

- Update `PROTECTED_PATHS` in `electron/update-manager.js`.
- Update `.gitignore` so user data, runtime files, caches, logs, weights, and training outputs stay ignored.
- Update this runbook if a path changes ownership classification.
- Keep renderer update actions mapped to fixed IPC methods only.
- Keep update apply behavior `ff-only` unless a new ADR supersedes this decision.
- Add migration tests for any SQLite schema changes; migrations must be additive for user data.

## Verification

Run these checks after updater or storage changes:

```text
npm.cmd run typecheck
.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_storage.py tests\test_voxcpm_app_service_cli.py tests\test_voxcpm_app_generation_service.py tests\test_voxcpm_app_indextts2_service.py --basetemp data\pytest-tmp
```

Useful local updater smoke check:

```text
node -e "const u=require('./electron/update-manager'); (async()=>{ const s=await u.getUpdateStatus(process.cwd(), { repositoryUrl:'https://github.com/Aoye-3/Dubbing-room.git', branch:'main' }); console.log(JSON.stringify({ state:s.state, branch:s.currentBranch, ahead:s.ahead, behind:s.behind, blockers:s.blockers, protected:s.protectedPaths.filter(p=>!p.ignored).map(p=>p.path) }, null, 2)); })().catch(e=>{ console.error(e); process.exit(1); });"
```

Expected safe states:

- Clean `main`, no remote update: `state = "upToDate"`, `blockers = []`.
- Clean `main`, remote ahead: `state = "updateAvailable"`, `blockers = []`.
- Dirty tracked files: `state = "blocked"`.
- `data/app/app.sqlite3` not ignored: `state = "blocked"`.
- Requested GitHub URL differs from `origin`: `state = "blocked"`.
- Non-fast-forward remote: `applyUpdate` returns `blocked` and does not modify files.
