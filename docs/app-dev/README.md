# VoxCPM App Development Docs

This documentation describes VoxCPM-Box application-layer development on top of the current VoxCPM project. It intentionally avoids model internals and focuses on desktop app behavior, local data, user workflows, app adapters/services, and implementation boundaries.

下一阶段产品方向是双模型 AppShell：通过共享本地存储后端连接 VoxCPM2 与 IndexTTS2。VoxCPM2 负责声音资产和通用生产，IndexTTS2 负责台词级情绪和表演精修。

## Current App-Layer State

- The main generation UI is implemented with Gradio Blocks in `app.py`.
- The original Gradio route remains available through `start_voxcpm.bat` and direct `app.py` commands.
- The Electron AppShell route is a separate React app mode launched through `start_electron_shell.bat` or `start_electron_shell.vbs`.
- `run_with_local_ffmpeg.py` prepares project-local FFmpeg access before launching Python entrypoints.
- The current Electron renderer uses Vite, React, TypeScript, and `lucide-react`.
- A local app storage layer now exists under `src/voxcpm_app/` for Voice Library and Generation History metadata.
- The Electron AppShell reads Voice Library and History records through IPC-backed app service calls.
- Native save-voice actions, generation execution, and history recording now run through the AppShell backend.
- IndexTTS2 now has an AppShell 表演台, Electron IPC bridge, `/indextts2/generate` backend route, fake-runner tests, and a `third_party/index-tts/` source snapshot. Real inference still requires project-local runtime and checkpoints.
- VoxCPM-Box targets ordinary-user voiceover workflows while preserving upstream source behavior.
- 双模型集成 PRD 定义 Phase 5 之后的方向：通用存储后端、VoxCPM2 生产台、IndexTTS2 表演台。

## First Scope

The first app-development scope is:

- Voice Library: save uploaded reference voices for reuse.
- Generation History: record generated outputs and their reusable parameters.
- Local app data management: store structured metadata in SQLite and audio files on disk.

Product scenarios tracked by VoxCPM-Box:

- Video spoken narration.
- AIGC short-film dubbing.
- Repeated voice reuse.
- Script breakdown and batch task workflows.
- Role profiles and saved voices.
- Line-level emotion and performance refinement with IndexTTS2.

Out of scope for the first implementation:

- Cloud sync.
- User accounts.
- Model training or model-level voice tuning.
- Multi-device collaboration.
- Removing the original Gradio developer route.
- Hand-drawn sidebar or action SVG icons.

## Document Index

- [01 Product PRD](01-product-prd.md)
- [02 Architecture](02-architecture.md)
- [03 Data Design](03-data-design.md)
- [04 API Contracts](04-api-contracts.md)
- [05 UI Workflows](05-ui-workflows.md)
- [06 Implementation Roadmap](06-implementation-roadmap.md)
- [07 Test Acceptance](07-test-acceptance.md)
- [08 Frontend App Shell](08-frontend-app-shell.md)
- [09 VoxCPM-Box Scope and Upstream Sync](09-voxcpm-box-scope-and-upstream-sync.md)
- [10 双模型互补应用壳 PRD](10-dual-model-integration-prd.md)
- [完整双模型功能实现 PRD](../PRD/dual-model-audio-appshell-full-implementation-prd.md)
- [Technical Documentation Index](../technical/README.md)
- [ADR 0001: Local SQLite and File Storage](adr/0001-local-sqlite-and-file-storage.md)
- [ADR 0002: 双模型 RuntimeCoordinator](adr/0002-dual-model-runtime-coordinator.md)

## Default App Data Layout

Development data root:

```text
F:\.VoxCPM\VoxCPM\data\app\
```

Relative project paths:

```text
data/app/app.sqlite3
data/app/voices/
data/app/generations/
data/app/tmp/
```

The SQLite database stores metadata. Audio files stay on disk and are referenced by relative paths and checksums.

## Roadmap Overview

1. Phase 1: Documentation and app data conventions.
2. Phase 2: Electron React app shell with native app-mode pages.
3. Phase 3: Storage layer and SQLite schema.
4. Phase 4: App service integration for Voice Library and History.
5. Phase 5: Tests, migration checks, and packaging preparation.
6. Phase 6: 双模型 AppShell 架构，包括通用存储、VoxCPM2 生产台和 IndexTTS2 表演精修。
