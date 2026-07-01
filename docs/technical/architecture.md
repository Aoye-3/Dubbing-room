# 系统架构

## 当前目标

VoxCPM-Box 的目标是本地双模型音频生成 AppShell，而不是把 VoxCPM2 和 IndexTTS2 做成简单模型下拉框。

产品由三个板块组成：

- 通用存储后端：资产、音色库、生成历史、任务、take、runtime 状态。
- VoxCPM2 生产台：声音资产和通用生产。
- IndexTTS2 表演台：台词级情绪和表演精修。

## 当前代码状态

已经存在：

- Electron + React AppShell。
- Python App backend。
- Voice Library。
- Generation History。
- VoxCPM2 最小生成闭环。
- IndexTTS2 前端页、IPC、后端路由和 worker。
- IndexTTS 源码快照：`third_party/index-tts/`。
- `RuntimeCoordinator` 初版。

尚未完成：

- 双模型共享 runtime coordinator。
- 真实 IndexTTS2 runtime/checkpoints。
- 通用 assets/jobs/takes 存储层。
- 异步任务队列。
- IndexTTS2 多 take 产品化。
- 前端模块拆分。

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

### 目标 job 流

```text
Renderer
  -> POST /generation-jobs
  -> generation_jobs row queued
  -> RuntimeCoordinator grants GPU lease
  -> backend adapter runs model
  -> output becomes asset
  -> take/job updated
  -> legacy generation projection updated
  -> Renderer polls or subscribes to job status
```

## 关键架构决策

- 后端拥有 GPU safety，前端只展示状态。
- VoxCPM2 和 IndexTTS2 默认共享一个 GPU slot。
- 两个模型依赖必须隔离。
- 所有产物必须进入通用存储层。
- 旧 `voices` 和 `generations` API 在迁移期保持兼容。
- `main.tsx` 不应继续作为长期承载所有功能的文件。

## 下一步架构优先级

1. RuntimeCoordinator 覆盖 VoxCPM2 和 IndexTTS2。
2. IndexTTS2 真实 runtime/checkpoints 接入。
3. assets / generation_jobs / generation_takes additive migration。
4. job queue。
5. 前端模块拆分和多 take UI。

