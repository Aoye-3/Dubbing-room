# Dubbing-room / VoxCPM-Box

**Dubbing-room** 是一个基于 `VoxCPM2` 与 `IndexTTS2` 的本地 AIGC 语音工作流配音室。它从早期的 VoxCPM-Box AppShell 演进而来，目标不再只是给 VoxCPM 增加桌面外壳，而是把声音资产、台词演绎、多 take、任务队列、生成历史和本地 runtime 管理组织成一个完整的配音工作台。

新公开地址：

- [Aoye-3/Dubbing-room](https://github.com/Aoye-3/Dubbing-room)

上游与相关项目：

- [OpenBMB/VoxCPM](https://github.com/OpenBMB/VoxCPM)
- [index-tts/index-tts](https://github.com/index-tts/index-tts)

## 迁移与项目关系

本项目正在从 **VoxCPM-Box** 迁移到 **Dubbing-room**。

- **Dubbing-room**：新的产品定位和仓库地址，面向本地 AIGC 配音工作流。
- **原始 VoxCPM-Box**：早期项目名和 AppShell 阶段，主要目标是在 VoxCPM 基础上增加 Electron 桌面应用层、Voice Library、History 和本地数据服务。
- **VoxCPM / VoxCPM2**：上游语音生成能力来源。Dubbing-room 保留原始 Gradio/developer route，用于上游兼容、模型行为验证和回归检查。
- **IndexTTS2**：作为可选本地 runtime 接入，负责台词级表演控制、情绪控制、多 take 精修和 selected take 输出。

简化理解：

```text
OpenBMB/VoxCPM
  -> 提供 VoxCPM/VoxCPM2 上游模型能力和原始开发入口

VoxCPM-Box
  -> 早期桌面 AppShell、Voice Library、History、本地应用层探索

Dubbing-room
  -> 当前产品方向：IndexTTS2 + VoxCPM2 的本地 AIGC 语音工作流配音室
```

Dubbing-room 不是官方 VoxCPM 项目，也不是 IndexTTS2 官方项目。它是一个独立的本地桌面应用层，复用和适配两类模型能力，并把它们组织成创作工作流。

## 产品定位

Dubbing-room 面向这些任务：

- 用 VoxCPM2 快速生成旁白、角色声音或基础声音资产。
- 把生成结果保存到 Voice Library，作为后续 speaker reference。
- 用 IndexTTS2 对单句台词做情绪、语气和表演精修。
- 为同一句台词生成多个 take，播放、比较并选择最佳版本。
- 将 selected take 写入 History，并可继续保存为可复用声音。
- 在本地管理 runtime、checkpoints、cache、SQLite 数据库和音频输出。

双模型职责不是下拉菜单式切换，而是工作流分工：

| 模块 | 职责 |
|---|---|
| `VoxCPM2` | 通用语音生成、旁白、声音克隆、基础声音资产准备 |
| `IndexTTS2` | 台词级演绎、情绪控制、多 take 精修、最终版本选择 |
| AppShell backend | 本地存储、任务队列、runtime 显存互斥、History/Voice Library 兼容 |
| Electron renderer | 配音室工作台、Jobs 视图、声音资产管理和操作反馈 |

## 当前状态

已完成或正在接入：

- Electron + React + TypeScript AppShell。
- Python 本地后端和 Electron IPC bridge。
- Voice Library 与 Generation History 的本地 SQLite/file 存储基础。
- VoxCPM2 AppShell 生成闭环。
- IndexTTS2 表演台页面、IPC、后端生成入口和 `third_party/index-tts/` 源码快照。
- 统一 `RuntimeCoordinator`，用于防止 VoxCPM2 和 IndexTTS2 同时占用 GPU。
- Additive storage v2：`assets`、`generation_jobs`、`generation_takes`。
- 单进程 FIFO generation job queue。
- Jobs 页面基础能力：queued/running/succeeded/failed/cancelled、取消 queued job、重试 failed job、查看 takes。

仍在推进：

- 前端从大型 `main.tsx` 拆分到 `app/`、`shared/`、`voxcpm/`、`indextts2/`、`jobs/`、`storage/`。
- IndexTTS2 多 take 比较面板产品化。
- selected take 保存为 Voice Library 音色。
- 真实 runtime unload contract。
- 根 README、技术文档和 ADR 的持续同步。

## 快速开始

### AppShell route

启动 Dubbing-room 桌面 AppShell：

```bat
start_electron_shell.bat
```

或无可见终端启动：

```bat
start_electron_shell.vbs
```

开发模式：

```bat
npm.cmd install
npm.cmd run dev
```

### Legacy / developer Gradio route

保留原始 VoxCPM WebUI，用于上游兼容检查：

```bat
start_voxcpm.bat
```

直接运行示例：

```bat
python run_with_local_ffmpeg.py app.py --port 8808 --device cuda
```

## IndexTTS2 runtime

IndexTTS2 是可选本地 runtime。仓库不会默认捆绑 IndexTTS2 权重。

准备项目内 runtime/cache 目录：

```powershell
.\scripts\prepare_indextts2_runtime.ps1
```

默认 runtime root：

```text
data/runtimes/indextts2/
```

需要放置或配置的关键文件包括：

```text
data/runtimes/indextts2/.venv/Scripts/python.exe
third_party/index-tts/checkpoints/config.yaml
third_party/index-tts/checkpoints/bpe.model
third_party/index-tts/checkpoints/gpt.pth
third_party/index-tts/checkpoints/s2mel.pth
```

所有 runtime、cache、checkpoint、输出和数据库都应留在当前仓库所在驱动器内，不应写入 C 盘缓存或外部临时目录。

## 常用检查

Frontend type check：

```bat
npm.cmd run typecheck
```

Frontend build：

```bat
npm.cmd run build
```

Electron script syntax check：

```bat
node --check electron\main.js
node --check electron\preload.js
node --check electron\dev-runner.js
```

Python AppShell tests：

```bat
.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_storage.py tests\test_voxcpm_app_service_cli.py tests\test_voxcpm_app_generation_service.py tests\test_voxcpm_app_indextts2_service.py -q --basetemp data\pytest-tmp
```

## 项目结构

```text
electron/                         Electron main process and React renderer
electron/renderer/src/jobs/        Jobs view and take list UI
src/voxcpm_app/                    Python AppShell backend
src/voxcpm_app/runtime.py          RuntimeCoordinator and backend status
src/voxcpm_app/job_queue.py        FIFO generation job queue
src/voxcpm_app/job_store.py        assets/jobs/takes service helpers
third_party/index-tts/             IndexTTS2 source snapshot
docs/                              Product, technical, PRD, and app-dev docs
scripts/prepare_indextts2_runtime.ps1
```

目标 renderer 结构：

```text
electron/renderer/src/app/         App bootstrap, routes, shell, i18n
electron/renderer/src/shared/      API client, shared types, reusable components
electron/renderer/src/voxcpm/      VoxCPM2 production workspace
electron/renderer/src/indextts2/   IndexTTS2 line performance workspace
electron/renderer/src/jobs/        Job queue and take inspection
electron/renderer/src/storage/     Voice Library and History
```

本地数据结构：

```text
data/app/app.sqlite3
data/app/voices/
data/app/generations/
data/app/tmp/
data/runtimes/indextts2/
```

## 文档入口

- [文档总入口](docs/README.md)
- [当前主 PRD：AIGC 语音工作流配音室](docs/PRD/aigc-voice-workflow-studio-prd.md)
- [完整双模型实现 PRD](docs/PRD/dual-model-audio-appshell-full-implementation-prd.md)
- [技术文档索引](docs/technical/README.md)
- [App 开发文档](docs/app-dev/README.md)
- [RuntimeCoordinator ADR](docs/app-dev/adr/0002-dual-model-runtime-coordinator.md)

## 上游同步策略

当同步 OpenBMB/VoxCPM 上游变化时：

1. 优先保持原始 VoxCPM 文件和入口可运行。
2. 验证 legacy/developer Gradio route。
3. 验证 Dubbing-room AppShell route。
4. 如果上游启动参数、模型调用方式或依赖发生变化，再更新 AppShell adapters/services。
5. 尽量避免修改模型内部实现；产品功能放在应用层。

适合回馈上游 VoxCPM 的内容：

- Windows 兼容修复。
- 本地 FFmpeg/path 处理。
- CLI 或文档修正。
- 对所有 VoxCPM 用户有价值的小 bugfix。

适合留在 Dubbing-room 的内容：

- Electron AppShell。
- Voice Library / History。
- IndexTTS2 台词工作台。
- Job queue / takes / runtime status。
- 本地 SQLite/file 数据模型。
- AIGC 配音工作流产品功能。

## License

Dubbing-room 需要遵守上游 VoxCPM 的许可证和归属要求。分发模型权重、源码或打包 runtime 前，请检查 [OpenBMB/VoxCPM](https://github.com/OpenBMB/VoxCPM) 的许可证。

IndexTTS2 有独立的上游许可证和模型使用条款。当前仓库仅保留 `third_party/index-tts/` 源码快照，不默认捆绑 IndexTTS2 权重；商业使用或大规模再分发前需要单独审查 [index-tts/index-tts](https://github.com/index-tts/index-tts) 的许可证和模型条款。
