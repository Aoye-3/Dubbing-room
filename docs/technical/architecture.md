# 系统架构

## 当前目标

VoxCPM-Box 的目标是本地双模型音频生成 AppShell，而不是把 VoxCPM2 和 IndexTTS-2.5 做成简单模型下拉框。兼容 backend id 仍为 `indextts2`，模型身份单独记录为 `IndexTTS-2.5`。

产品由三个板块组成：

- 通用存储后端：资产、音色库、生成历史、任务、take、runtime 状态。
- VoxCPM2 生产台：声音资产和通用生产。
- IndexTTS-2.5 表演台：台词级情绪和表演精修。

## 当前代码状态

已经存在：

- Electron + React + TypeScript AppShell，以及拆分后的 `app/`、`shared/`、`voxcpm/`、`indextts2/`、`jobs/`、`storage/` 模块。
- Python App backend、Electron IPC bridge 和结构化错误响应。
- Voice Library 与 Generation History，包括收藏、回收站、恢复、永久清理和生成结果提升为音色。
- VoxCPM2 同步生成闭环，以及 IndexTTS-2.5 单 take 兼容入口和多 take job 闭环。
- 固定到上游 commit `a371df7d0746a0ae7fdf075798b6b04e34a0132e` 的 IndexTTS-2.5 源码与 337 文件校验清单。
- IndexTTS-2.5 每个 job 启动一个 JSONL worker、加载一次模型、顺序生成 1-5 个 take；job 结束后退出并释放 lease。
- VoxCPM2 与 IndexTTS2 共用的单进程 `RuntimeCoordinator` GPU lease。
- additive SQLite storage v5：兼容 `voices` / `generations`，并为 generation/job/take 增加 nullable 模型身份与结构化 warnings。
- 进程内 FIFO job queue、queued/running cancel、failed job retry、take 选择及 History 投影。
- Performance Desk 内的多 Take 状态、播放、对比、选择、导出和保存音色，以及全局 Jobs 视图。
- Vitest + jsdom + React Testing Library renderer 测试基线。
- GitHub 安全更新入口及用户数据/runtime 保护检查。

尚未完成：

- VoxCPM2 与 IndexTTS-2.5 的真实模型 smoke test 和并发验收记录；当前 2.5 官方 config/权重未安装。
- runtime 真实 load/unload/free、CUDA cache cleanup 和跨进程锁。
- backend 重启后的 queued/running job 恢复。
- Electron IPC 集成测试和桌面 E2E。
- structured job logs 查询与任务日志 UI。
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
      formMapper.ts              2.5 表单校验和 job payload 映射
      PerformanceDesk.tsx        当前 job/take 对比与操作
    jobs/                         Job queue 和 take comparison

src/voxcpm_app/
  backend_server.py               HTTP App backend
  runtime.py                      RuntimeCoordinator 和 backend status
  generation_service.py           VoxCPM2 adapter / service
  indextts2_service.py            IndexTTS2 adapter / service
  indextts2_worker.py             IndexTTS2 isolated worker
  indextts2_runtime_profile.py    2.5 runtime profile、精度和能力解析
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
  -> one IndexTTS-2.5 subprocess emits JSONL ready/take/complete events
  -> model loads once and runs 1-5 takes sequentially
  -> each successful output becomes an asset
  -> take/job identity, warnings and status updated
  -> legacy generation projection updated
  -> Renderer polls job/take status every 3 seconds
```

当前 IndexTTS-2.5 job 会在提交时创建 1-5 个 take，顺序执行并保留每个 take 的独立状态。首个成功 take 会投影到兼容 History；用户后续选择其他成功 take 时会幂等更新该投影。running cancel 会终止 worker、取消未完成 take，并阻止取消后的 History 投影；最终选择与取消使用同一状态锁收口，避免终态互相覆盖。

## 关键架构决策

- 后端拥有 GPU safety，前端只展示状态。
- VoxCPM2 和 IndexTTS2 默认共享一个 GPU slot。
- 两个模型依赖必须隔离。
- `backend_id=indextts2` 保持兼容，`model_id/model_version/upstream_commit` 负责区分 2.0 历史与 2.5 新数据。
- IndexTTS-2.5 使用“每 job 一个 worker”，不采用应用生命周期常驻模型、vLLM、TensorRT 或流式网络服务。
- 所有产物必须进入通用存储层。
- 旧 `voices` 和 `generations` API 在迁移期保持兼容。
- `main.tsx` 只保留 React 启动入口；业务页面继续按领域模块维护。

## 下一步架构优先级

1. 安装经许可审查的 IndexTTS-2.5 config/权重，完成五语言、四情感、时长、显存和单 GPU slot 真实验收。
2. 为 Electron IPC 和关键桌面用户路径补集成/E2E 自动化。
3. 明确并实现 runtime unload/free、CUDA cache cleanup 和跨进程锁。
4. 设计 backend 重启后的 queue 恢复和 structured job logs。
5. 在发布打包与 Script/Batch/Role 工作流之间确定下一阶段优先级。

