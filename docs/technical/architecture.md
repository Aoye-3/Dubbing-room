# 系统架构

## 当前目标

VoxCPM-Box 的目标是本地双模型音频生成 AppShell，而不是把 VoxCPM2 和 IndexTTS2 做成简单模型下拉框。

产品由三个板块组成：

- 通用存储后端：资产、音色库、生成历史、任务、take、runtime 状态。
- VoxCPM2 生产台：声音资产和通用生产。
- IndexTTS2 表演台：台词级情绪和表演精修。

## 当前代码状态

已经存在：

- Electron + React + TypeScript AppShell，以及拆分后的 `app/`、`shared/`、`voxcpm/`、`indextts2/`、`jobs/`、`storage/` 模块。
- Python App backend、Electron IPC bridge 和结构化错误响应。
- Voice Library 与 Generation History，包括收藏、回收站、恢复、永久清理和生成结果提升为音色。
- VoxCPM2 同步生成闭环，以及 IndexTTS2 同步生成和多 take queued job 闭环。
- IndexTTS2 源码快照：`third_party/index-tts/`，项目内 runtime 和 checkpoint 目录约定。
- VoxCPM2 与 IndexTTS2 共用的单进程 `RuntimeCoordinator` GPU lease。
- additive SQLite storage v4：兼容 `voices` / `generations`，并增加 `assets`、`generation_jobs`、`generation_takes`。
- 进程内 FIFO job queue、queued cancel、failed job retry、take 选择及 History 投影。
- GitHub 安全更新入口及用户数据/runtime 保护检查。

尚未完成：

- VoxCPM2 与 IndexTTS2 的真实模型 smoke test 和并发验收记录。
- runtime 真实 load/unload/free、CUDA cache cleanup 和跨进程锁。
- running job 的硬取消；当前只记录 `cancel requested`。
- Renderer 组件测试、Electron IPC 集成测试和桌面 E2E。
- 更完整的多 take 对比体验、结构化错误 UI 和任务日志。
- Script Breakdown、Role Profiles、跨段 batch workflow 与发布打包。

## 目标模块边界

```text
electron/
  main.js                         Electron IPC 和 App backend 转发
  preload.js                      Renderer 安全 API
  renderer/src/
    app/                          Shell、导航、全局状态
    shared/                       API client、UI primitives、media helpers
    storage/                      资产、音色、历史、任务视图
    voxcpm/                       VoxCPM2 生产台
    indextts2/                    IndexTTS2 表演台
    jobs/                         Job queue 和 take comparison

src/voxcpm_app/
  backend_server.py               HTTP App backend
  runtime.py                      RuntimeCoordinator 和 backend status
  generation_service.py           VoxCPM2 adapter / service
  indextts2_service.py            IndexTTS2 adapter / service
  indextts2_worker.py             IndexTTS2 isolated worker
  db.py                           SQLite schema and migration
  repositories.py                 Persistence repositories
  schemas.py                      Data records
  audio_assets.py                 File storage helpers
  voice_library.py                Voice Library service functions
  generation_history.py           Legacy generation projection
```

## 运行流

### 当前同步流

```text
Renderer
  -> Electron preload
  -> Electron main IPC handler
  -> Python App backend route
  -> GenerationService / IndexTTS2Service
  -> model runner
  -> data/app/generations
  -> generations table
  -> Renderer refreshes history
```

### 当前 job/take 流

```text
Renderer
  -> POST /generation-jobs
  -> generation_jobs row queued
  -> RuntimeCoordinator grants GPU lease
  -> backend adapter runs model
  -> output becomes asset
  -> take/job updated
  -> legacy generation projection updated
  -> Renderer polls job/take status every 3 seconds
```

当前 IndexTTS2 job 会在提交时创建 1-5 个 take（默认 3 个），顺序执行并保留每个 take 的独立状态。首个成功 take 会投影到兼容 History；用户后续选择其他成功 take 时会幂等更新该投影。

## 关键架构决策

- 后端拥有 GPU safety，前端只展示状态。
- VoxCPM2 和 IndexTTS2 默认共享一个 GPU slot。
- 两个模型依赖必须隔离。
- 所有产物必须进入通用存储层。
- 旧 `voices` 和 `generations` API 在迁移期保持兼容。
- `main.tsx` 只保留 React 启动入口；业务页面继续按领域模块维护。

## 下一步架构优先级

1. 完成 VoxCPM2 与 IndexTTS2 真实模型 smoke test，并验证单 GPU slot 约束。
2. 为 Renderer、Electron IPC 和关键桌面用户路径补自动化测试。
3. 明确并实现 runtime unload/free 与 running job cancellation contract。
4. 完善多 take 对比、错误详情和任务日志体验。
5. 在发布打包与 Script/Batch/Role 工作流之间确定下一阶段优先级。

