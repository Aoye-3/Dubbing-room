# 双模型音频生成应用壳完整功能实现 PRD

## 文档状态

- 状态：Draft / implementation planning
- 日期：2026-07-01
- 范围：VoxCPM-Box AppShell，覆盖 VoxCPM2、IndexTTS2、通用存储后端、运行时调度、任务队列和前端工作流。
- 非范围：不在本 PRD 中直接修改代码；不捆绑 IndexTTS2 或 VoxCPM2 权重；不创建外部 checkout 或 worktree。

## 背景

VoxCPM-Box 已经从单一 VoxCPM 桌面壳推进到双模型互补方向。当前代码已经具备 IndexTTS2 前端页、Electron IPC、Python 后端任务入口、源码快照和 fake runner 测试，但仍处于应用壳骨架阶段。

下一阶段目标不是把两个模型做成下拉切换，而是形成一个稳定的本地音频生成工作台：

- VoxCPM2 负责声音资产、通用生产、旁白和基础音色产出。
- IndexTTS2 负责台词级情绪、语气、表演版本和多 take 精修。
- 通用存储后端负责连接两者，统一保存资产、任务、take、历史和模型状态。
- 后端 runtime coordinator 负责显存互斥，前端只展示状态和提交任务。

## 用户目标

目标用户包括：

- 本地配音创作者。
- AIGC 短片和角色声音资产管理用户。
- 需要批量旁白和重点台词精修的内容生产者。
- 希望在本地机器上保留音频资产、历史和模型权重控制权的开发型用户。

用户希望完成：

1. 用 VoxCPM2 快速创建或整理角色声音资产。
2. 保存 VoxCPM2 输出为可复用音色。
3. 在 IndexTTS2 表演台选择已有音色，对单句台词做情绪和表演精修。
4. 为同一句台词生成多个 take，并比较、播放、选择最佳版本。
5. 所有输出都进入统一历史和资产库。
6. 不因为误点两个模型同时生成而爆显存。

## 产品定位

VoxCPM-Box 是一个本地双模型音频生成应用壳，不是 Gradio 页面集合，也不是模型下拉菜单。产品结构应分为三个板块：

### 通用存储后端

职责：

- 管理音频资产。
- 管理 Voice Library。
- 管理 generation jobs。
- 管理 generation takes。
- 管理生成历史。
- 管理模型启用状态、配置状态、busy 状态、错误和日志。
- 管理本地路径、缓存和权重目录。

### VoxCPM2 生产台

职责：

- 声音设计。
- 声音克隆。
- 极致克隆。
- 通用旁白。
- 多语言和批量生产。
- 生成可保存为 Voice Library 的声音资产。

### IndexTTS2 表演台

职责：

- 单句台词输入。
- 选择角色音色或上传 speaker reference。
- emotion audio / emotion vector / emotion text 控制。
- 生成多 take。
- 比较 take、选择 take。
- 将选中 take 回写统一历史和资产库。

## 当前实际接入状态

当前已经完成：

- 前端 `IndexTTS2 表演台` 导航和页面。
- `generateIndexTTS2(payload)` Electron IPC。
- `getRuntimeBackends()` Electron IPC。
- 后端 `/indextts2/generate`。
- 后端 `/runtime-backends`。
- `IndexTTS2Service` 和 `SubprocessIndexTTS2Runner`。
- `indextts2_worker.py` 通过 `indextts.infer_v2.IndexTTS2` 调用真实 infer。
- `RuntimeCoordinator` 初版单锁。
- IndexTTS2 fake runner 测试。
- `third_party/index-tts/` 源码快照。

当前尚未完成：

- 真实 IndexTTS2 runtime 环境。
- 真实 IndexTTS2 checkpoints。
- VoxCPM2 接入同一个 `RuntimeCoordinator`。
- 跨模型任务队列。
- assets / generation_jobs / generation_takes 结构化存储。
- IndexTTS2 多 take 落库。
- 前端拆分到 `electron/renderer/src/indextts2/`。
- 前端自动化测试。

## 关键问题

### 显存互斥尚未真正覆盖双模型

当前 `RuntimeCoordinator` 只在 IndexTTS2 路径使用。VoxCPM2 的 `GenerationService` 仍使用自己的 `_generation_lock`。因此 `/generate-audio` 和 `/indextts2/generate` 理论上仍可能同时运行并抢 GPU。

### 任务层还不是统一 job 模型

当前生成接口是同步式请求，成功或失败后返回一条 `GenerationRecord`。这能支持 MVP，但不适合多 take、队列、取消、重试、进度、日志和运行中状态展示。

### 存储仍是 v1 兼容模型

当前数据库核心是 `voices` 和 `generations`。IndexTTS2 参数被塞进 `generations.control_instruction` JSON，属于过渡实现。长期需要新增 `assets`、`generation_jobs`、`generation_takes`。

### 真实 runtime 缺配置和完整性检查

当前默认寻找：

- `data/runtimes/indextts2/.venv/Scripts/python.exe`
- `third_party/index-tts/checkpoints/config.yaml`

但本地尚无 `.venv` 和完整 checkpoints。后端状态也只检查 `config.yaml`，还需要检查 `bpe.model`、`gpt.pth`、`s2mel.pth`、必要辅助模型和 cache。

### 前端页面可用但还不是最终结构

IndexTTS2 页面当前在 `main.tsx` 内，适合 MVP，但不适合继续扩展多 take、任务队列、日志和高级 runtime 控制。

## 外部参考

### Meta Voicebox

Voicebox 是非自回归 flow-matching 语音生成模型，可做零样本 TTS、跨语种风格迁移、降噪、内容编辑和 diverse sample generation。它适合作为产品能力地图参考，但没有公开可直接复用的应用壳代码。

### ComfyUI

可借鉴点：

- 异步队列。
- history。
- interrupt / free。
- models / system stats。
- 前端通过任务提交和状态流驱动，不直接绑定模型函数。

对本项目的启发：VoxCPM-Box 应建立音频版任务层，所有生成先成为 job，再由 runtime coordinator 执行。

### TTS WebUI

可借鉴点：

- 多模型 extension。
- React UI + Gradio UI 并存。
- 依赖冲突是常态，模型应隔离环境。
- 输出、收藏、模型扩展和 API 是应用层能力。

对本项目的启发：VoxCPM2 与 IndexTTS2 不应共享 Python runtime。

### GPT-SoVITS

可借鉴点：

- WebUI 和 API 分离。
- 推理 API 单独存在。
- 参数面板围绕 reference audio、text、sampling、batch 组织。
- 权重切换需要运行锁。

对本项目的启发：如果未来支持同模型多权重，需要 job 绑定权重快照。

### RVC WebUI

可借鉴点：

- 多 Tab 工作流。
- 模型加载/卸载。
- 显式 `torch.cuda.empty_cache()`。
- batch 和 realtime 分区。

对本项目的启发：需要显式释放模型和释放显存操作，并在 UI 中展示状态。

### Amphion

可借鉴点：

- 按 TTS、VC、SVC、codec、vocoder 组织能力。
- 模型能力分层清楚。

对本项目的启发：前端导航应按任务意图和模型职责组织，而不是按模型名称堆 Tab。

## 功能需求

### FR1：统一 RuntimeCoordinator

必须支持：

- 全局 GPU slot，默认 1。
- `backend_id`。
- `active_job_id`。
- `busy`。
- `last_error`。
- `started_at`。
- `lease`。
- VoxCPM2 和 IndexTTS2 都必须通过同一 coordinator。

应支持：

- `queued` 状态。
- `cancel_requested`。
- timeout。
- 显式 unload / free。
- CUDA cache cleanup hook。

验收：

- fake VoxCPM2 运行时，fake IndexTTS2 无法同时获得 GPU lease。
- fake IndexTTS2 运行时，fake VoxCPM2 无法同时获得 GPU lease。
- `/runtime-backends` 能显示哪个 backend 正在运行。

### FR2：IndexTTS2 真实 runtime 配置

必须支持：

- 项目内隔离 runtime：`data/runtimes/indextts2/`。
- 项目内 cache。
- 项目内 checkpoints。
- 不写 C 盘缓存。
- 不污染现有 `.venv`。

必要环境变量：

- `UV_PROJECT_ENVIRONMENT`
- `UV_CACHE_DIR`
- `UV_PYTHON_INSTALL_DIR`
- `UV_PYTHON_CACHE_DIR`
- `UV_TOOL_DIR`
- `UV_TOOL_BIN_DIR`
- `HF_HOME`
- `HF_HUB_CACHE`
- `HF_XET_CACHE`
- `TORCH_EXTENSIONS_DIR`
- `XDG_CACHE_HOME`

验收：

- `.venv` 在 `data/runtimes/indextts2/.venv`。
- HF cache 在项目目录内。
- `uv run tools/gpu_check.py` 通过。
- `/runtime-backends` 显示 IndexTTS2 configured。

### FR3：IndexTTS2 参数真实性

必须支持：

- `spk_audio_prompt`
- `emo_audio_prompt`
- `emo_alpha`
- `emo_vector`
- `use_emo_text`
- `emo_text`
- `use_random`
- `interval_silence`
- `max_text_tokens_per_segment`
- `top_p`
- `top_k`
- `temperature`
- `length_penalty`
- `num_beams`
- `repetition_penalty`
- `max_mel_tokens`

需要修正：

- worker 应把 `device` 传入 `IndexTTS2(...)`。
- 如果上游 `do_sample` 实际写死，应从 UI 隐藏或标注“不生效”。
- `use_accel`、`use_torch_compile`、`aux_paths` 可作为 runtime 高级参数，而不是普通生成参数。

验收：

- same voice、emotion audio、emotion vector、emotion text 四类模式均可提交。
- 后端拒绝多个 emotion source 混用。
- 参数越界返回可读错误。
- 输出 wav 进入统一历史。

### FR4：通用资产层

新增 `assets` 表：

```text
id
kind
path
sha256
mime_type
duration_seconds
sample_rate
created_at
deleted_at
```

资产类型：

- `voice`
- `reference`
- `generation_output`
- `take_output`
- `uploaded`

验收：

- 上传 reference audio 进入 assets。
- VoxCPM2 输出进入 assets。
- IndexTTS2 take 输出进入 assets。
- Voice Library 可引用 asset。

### FR5：generation_jobs

新增 `generation_jobs` 表：

```text
id
backend_id
model_id
mode
status
input_text
voice_id
params_json
output_asset_id
error_summary
legacy_generation_id
created_at
updated_at
deleted_at
```

状态：

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`
- `deleted`

验收：

- VoxCPM2 和 IndexTTS2 都通过 job 创建。
- 旧 History 仍能显示 selected output。
- job 记录 backend、model、params。

### FR6：generation_takes

新增 `generation_takes` 表：

```text
id
job_id
backend_id
take_index
label
status
params_json
output_asset_id
is_selected
error_summary
created_at
updated_at
```

验收：

- IndexTTS2 同一句台词可生成多个 take。
- 每个 take 有独立输出 asset。
- 用户可选择一个 take。
- 选中 take 镜像到旧 `generations`，保持 History 兼容。

### FR7：任务 API

新增或规划接口：

```text
POST /generation-jobs
GET /generation-jobs
GET /generation-jobs/:id
POST /generation-jobs/:id/cancel
POST /generation-jobs/:id/retry
GET /generation-jobs/:id/takes
POST /generation-takes/:id/select
GET /runtime-backends
POST /runtime-backends/:id/unload
```

MVP 可保留：

- `/generate-audio`
- `/indextts2/generate`

但内部应逐步转向 job 层。

### FR8：前端信息架构

下一步目标结构：

```text
electron/renderer/src/app/
electron/renderer/src/shared/
electron/renderer/src/storage/
electron/renderer/src/voxcpm/
electron/renderer/src/indextts2/
electron/renderer/src/jobs/
```

IndexTTS2 页面拆分：

- `IndexTTS2Page`
- `LineEditorPanel`
- `SpeakerReferencePanel`
- `EmotionControlPanel`
- `AdvancedSamplingPanel`
- `TakeComparisonPanel`
- `RuntimeStatusCard`

验收：

- `main.tsx` 只保留 Shell、路由和顶层状态。
- IndexTTS2 页功能不回退。
- typecheck/build 通过。

## 非功能需求

### 本地优先

- 所有 runtime、cache、checkpoints、输出、数据库都必须在当前仓库所在驱动器内。
- 禁止写 C 盘缓存。
- 禁止 worktree。
- 禁止自动 clone 到外部目录。

### 可恢复性

- 生成失败必须写入 job/take/generation 的 error summary。
- worker stdout/stderr 应保存到日志。
- 任务失败不应让 AppShell 崩溃。

### 安全性

- 不提交模型权重。
- 不提交 runtime venv。
- 不提交 cache。
- 媒体服务必须限制在 project root 内。

### 可测试性

- 所有真实模型接口必须可 fake runner 测试。
- RuntimeCoordinator 必须可测试 busy / release / failure。
- 数据库迁移必须可在空库和旧库上测试。

## 分阶段实施计划

### Phase 1：Runtime 安全层

优先级最高。

工作项：

1. 扩展 `RuntimeCoordinator`。
2. VoxCPM2 接入同一个 coordinator。
3. `/runtime-backends` 返回真实双模型 busy 状态。
4. IndexTTS2 未配置时前端禁用生成。
5. Electron HTTP 转发增加 timeout。

验收：

- fake 双模型并发不会同时获得 GPU lease。
- UI 显示 busy / missing / failed。
- VoxCPM2 现有功能不回退。

### Phase 2：真实 IndexTTS2 runtime

工作项：

1. 增加 runtime setup 文档或脚本。
2. 配置项目内 uv/HF/Torch cache。
3. 下载 checkpoints 到项目内。
4. 完整检查 checkpoint 清单。
5. worker 传入 `device`。
6. 运行 same_voice smoke test。

验收：

- 真实 wav 输出。
- 输出进入 `data/app/generations/`。
- History 可播放。

### Phase 3：存储 v2 additive migration

工作项：

1. 新增 `assets`。
2. 新增 `generation_jobs`。
3. 新增 `generation_takes`。
4. 给旧表加 nullable 兼容列。
5. 保持旧 API shape。

验收：

- 旧库可迁移。
- 旧页面不崩。
- 新 job/take 可查询。

### Phase 4：任务队列

工作项：

1. 建立单进程队列。
2. job 创建后立即返回。
3. 后端串行执行 GPU job。
4. 支持 cancel pending job。
5. 写入日志和错误。

验收：

- 前端能看到 queued/running/succeeded/failed。
- busy 不再表现为 HTTP 卡死。

### Phase 5：前端拆分和多 take UI

工作项：

1. 拆 `main.tsx`。
2. 新增 jobs 页面或侧栏。
3. 新增 take comparison。
4. 选中 take。
5. 保存 take 为 voice。

验收：

- 用户能完成 VoxCPM2 -> Voice Library -> IndexTTS2 -> selected take -> History 的完整流。

## 验收测试总表

### 静态检查

```bat
npm.cmd run typecheck
npm.cmd run build
node --check electron\main.js
node --check electron\preload.js
```

### Python 测试

```bat
.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_storage.py tests\test_voxcpm_app_service_cli.py tests\test_voxcpm_app_generation_service.py tests\test_voxcpm_app_indextts2_service.py -q --basetemp data\pytest-tmp
```

### 新增测试

- RuntimeCoordinator 双模型互斥。
- VoxCPM2 接入 coordinator。
- IndexTTS2 checkpoint 完整性检查。
- device 传递。
- worker timeout。
- job/take migration。
- selected take 镜像旧 History。

### 真实模型验收

- 不写 C 盘 cache。
- GPU check 通过。
- same voice 生成成功。
- emotion audio 生成成功。
- emotion vector 生成成功。
- emotion text 生成成功。
- 并发请求只允许一个 GPU job 运行。

## 主要风险

### 依赖冲突

IndexTTS2 固定依赖和 VoxCPM2 当前环境可能冲突，因此必须隔离 runtime。

### 显存不足

如果两个模型同时加载或推理，可能导致 CUDA OOM。必须先完成统一 coordinator。

### 上游参数不生效

`do_sample` 在当前 IndexTTS2 上游实现中可能被写死，需要 UI 标注或隐藏。

### 数据库迁移风险

不能破坏现有 Voice Library 和 History，因此 v2 存储必须 additive。

### 前端复杂度

继续堆 `main.tsx` 会增加维护风险，Phase 5 前必须拆分。

## 推荐下一步

下一轮实现顺序：

1. RuntimeCoordinator 接管 VoxCPM2 和 IndexTTS2。
2. IndexTTS2 runtime/checkpoints 真实接入。
3. additive 存储迁移。
4. job queue。
5. 前端拆分和多 take。

这个顺序的理由：先修显存闸门，再接真实模型。否则真实模型一旦配置成功，当前并发缺口会立刻变成高风险问题。

