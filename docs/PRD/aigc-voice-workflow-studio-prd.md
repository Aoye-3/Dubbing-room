# VoxCPM-Box AIGC 语音工作流配音室 PRD

## 1. 文档信息

- 版本：v0.1
- 状态：Draft / product direction
- 日期：2026-07-01
- 适用范围：VoxCPM-Box Electron AppShell、Python 本地后端、IndexTTS2 runtime、VoxCPM2 runtime、本地素材库、任务队列、多 take 工作流。
- 相关文档：
  - [双模型音频生成应用壳完整功能实现 PRD](dual-model-audio-appshell-full-implementation-prd.md)
  - [技术文档索引](../technical/README.md)
  - [App 开发文档索引](../app-dev/README.md)

## 2. 背景与定位

VoxCPM-Box 的产品定位从“基于 VoxCPM 的延展开发”升级为“基于 IndexTTS2 和 VoxCPM2 的本地 AIGC 语音工作流配音室”。

这个产品不是模型 demo 集合，也不是简单的多模型下拉菜单。它面向创作者、AIGC 短片制作者和本地语音资产管理用户，提供从角色音色准备、台词演绎、多 take 比较、最佳 take 选择到历史归档和复用的完整配音工作流。

双模型职责：

- `VoxCPM2`：负责通用语音生成、旁白、基础音色产出、声音资产准备和 Voice Library 种子资产。
- `IndexTTS2`：负责台词级演绎、情绪控制、speaker reference 复用、多 take 精修和最终配音版本选择。
- `VoxCPM-Box AppShell`：负责把模型能力组织成产品工作流，包括本地存储、runtime 显存互斥、任务队列、素材管理、历史记录和前端工作台。

## 3. 产品目标

### 3.1 用户目标

- 用户可以在本地机器上完成语音配音生产，不依赖云端账户、云端数据库或外部任务服务。
- 用户可以先用 VoxCPM2 生成或整理角色声音，再在 IndexTTS2 中对具体台词进行精细演绎。
- 用户可以为同一句台词生成多个 take，并播放、比较、选择最佳版本。
- 用户可以把选中的 take 保存到 History，也可以沉淀为 Voice Library 中的可复用声音资产。
- 用户不会因为误触两个模型同时生成而导致 GPU OOM 或应用卡死。
- 用户可以清楚知道模型是否已配置、是否忙碌、缺少哪些 runtime/checkpoint 文件。

### 3.2 产品目标

- 建立稳定的本地双模型音频工作台，而不是继续堆叠单页面 MVP。
- 将 `IndexTTS2` 工作台确立为台词演绎和多 take 的核心工作流。
- 将 `VoxCPM2` 工作台确立为通用生成、声音资产准备和旁白能力入口。
- 建立可扩展前端架构，为后续批量台词、角色项目、时间线、WebSocket 状态流和更多模型接入留出清晰边界。
- 统一本地资产、任务、take、历史和 runtime 状态的数据模型。

### 3.3 成功指标

- 用户可以完成 `VoxCPM2 -> Save Voice -> IndexTTS2 -> Multiple Takes -> Select Take -> History Playback` 的闭环。
- 所有 generation 输出、take 输出和 reference audio 都进入统一资产管理。
- 同一时刻最多一个 GPU job 持有 runtime lease。
- 前端主入口不再由单个大型 `main.tsx` 承担全部页面和业务逻辑。
- README 和文档入口能准确表达产品定位、启动方式和架构边界。

## 4. 范围

### 4.1 本期范围

- 重写产品 README 和文档入口，明确 AIGC 语音工作流配音室定位。
- 完成 renderer 模块化重构：
  - `app/`
  - `shared/`
  - `voxcpm/`
  - `indextts2/`
  - `jobs/`
  - `storage/`
- 建立 renderer API client，页面不直接访问 `window.voxcpmBox`。
- 产品化 IndexTTS2 多 take 工作流。
- 补齐 RuntimeStatusCard 和 unload contract。
- 补充关键测试和手动验收流程。

### 4.2 非本期范围

- 不自动下载真实模型权重。
- 不引入云端账户、同步、多设备协作。
- 不引入外部数据库、外部队列或远程任务服务。
- 不移除原始 Gradio 开发入口。
- 不实现强制中断 running GPU job；本期只保证 queued job 可取消，running job 可记录 cancel requested。
- 不做完整视频时间线编辑器。
- 不做模型训练、微调或权重管理市场。

### 4.3 约束

- 所有 runtime、cache、checkpoint、数据库、输出和测试临时目录必须位于当前仓库所在驱动器内。
- 禁止使用 worktree、外部 clone 或 C 盘缓存作为开发和运行路径。
- 所有 schema 迁移必须 additive，不破坏旧 `voices` 和 `generations`。
- 旧 IPC 和旧同步 API 在迁移期继续保留。

## 5. 用户与场景

### 5.1 目标用户

- AIGC 短片创作者：需要为角色、旁白和片段台词快速生成多个配音版本。
- 本地配音工作流用户：需要管理 reference audio、角色声音、历史输出和可复用 take。
- 开发型创作者：愿意配置本地模型 runtime，并希望控制模型权重、缓存和输出路径。
- 语音资产整理用户：需要把生成结果沉淀为可复用素材，而不是只下载一次性 wav。

### 5.2 核心场景

#### 场景 A：角色声音准备

1. 用户进入 VoxCPM2 工作台。
2. 输入文本和参考音频或声音设定。
3. 生成一段基础语音。
4. 保存为 Voice Library 中的角色声音。

#### 场景 B：台词演绎精修

1. 用户进入 IndexTTS2 工作台。
2. 输入单句台词。
3. 选择 Voice Library 中的角色声音作为 speaker reference。
4. 选择 emotion audio、emotion vector 或 emotion text 中的一种控制方式。
5. 提交生成任务。
6. 获得一个 take，继续生成更多 take。
7. 播放、比较并选择最佳 take。

#### 场景 C：任务队列观察与恢复

1. 用户进入 Jobs 页面。
2. 查看 queued、running、succeeded、failed、cancelled 任务。
3. 取消尚未运行的任务。
4. 重试失败任务。
5. 查看任务关联的 takes 和错误摘要。

#### 场景 D：runtime 配置排障

1. 用户打开 IndexTTS2 工作台。
2. RuntimeStatusCard 显示未配置。
3. 用户看到具体缺失文件，例如 `config.yaml`、`bpe.model`、`gpt.pth`、`s2mel.pth`。
4. 用户按文档把文件放入项目内 runtime 目录。
5. 刷新后状态变为 configured。

## 6. 信息架构

### 6.1 顶层导航

- `VoxCPM2`：通用生成、旁白、声音资产准备。
- `IndexTTS2`：台词演绎、多 take、情绪控制。
- `Jobs`：任务队列、失败恢复、take 状态观察。
- `Voices`：Voice Library。
- `History`：旧兼容历史和 selected output。
- `Settings`：runtime 路径、设备、应用设置。

### 6.2 Renderer 目标目录结构

```text
electron/renderer/src/
  app/
    App.tsx
    AppShell.tsx
    routes.tsx
    i18n.ts
  shared/
    api/
      client.ts
    components/
    types.ts
    audio.ts
    format.ts
  voxcpm/
    VoxCPMPage.tsx
    VoicePromptPanel.tsx
    VoxCPMRuntimeCard.tsx
  indextts2/
    IndexTTS2Page.tsx
    LineEditorPanel.tsx
    SpeakerReferencePanel.tsx
    EmotionControlPanel.tsx
    AdvancedSamplingPanel.tsx
    TakeComparisonPanel.tsx
    RuntimeStatusCard.tsx
  jobs/
    JobListPage.tsx
    JobStatusBadge.tsx
    JobTakeList.tsx
  storage/
    VoiceLibraryPage.tsx
    HistoryPage.tsx
```

### 6.3 后端领域边界

- Runtime layer：统一 GPU lease、backend status、unload、错误摘要。
- Generation services：VoxCPM2 和 IndexTTS2 的模型适配。
- Storage layer：assets、voices、generations、generation_jobs、generation_takes。
- Queue layer：FIFO generation job 执行、cancel、retry。
- API layer：旧同步接口和新 job/take/runtime 接口。

## 7. 功能需求

### FR1：产品文档与 README 定位

必须支持：

- README 标题和首屏描述体现 `IndexTTS2 + VoxCPM2` 双模型配音室定位。
- README 说明本地运行、runtime 准备、缓存路径、测试命令和架构边界。
- `docs/README.md` 和 `docs/PRD/README.md` 指向当前主 PRD。
- 旧的 AppShell/VoxCPM 延展文档保留为历史和底层实现参考。

验收标准：

- 新读者可以从 README 理解项目不是单模型 demo，而是本地 AIGC 语音工作流配音室。
- 文档不承诺自动下载真实模型权重。

### FR2：前端模块化

必须支持：

- `main.tsx` 只保留 React bootstrap。
- Shell、导航、i18n、路由进入 `app/`。
- API client、通用类型、音频播放工具进入 `shared/`。
- VoxCPM2、IndexTTS2、Jobs、Storage 分别进入业务目录。
- 页面组件不直接访问 `window.voxcpmBox`。

验收标准：

- `npm.cmd run typecheck` 通过。
- `npm.cmd run build` 通过。
- 现有页面导航和主要按钮行为不回退。

### FR3：IndexTTS2 台词工作台

必须支持：

- 单句台词输入。
- speaker reference 选择或上传。
- emotion audio、emotion vector、emotion text 三类控制方式。
- 高级采样参数面板。
- job 提交。
- take 列表展示。
- take 播放、选择。
- selected take 镜像到 History。
- selected take 保存为 Voice Library 音色。

验收标准：

- 同一句台词可以多次提交并形成多个 take。
- 同一 job 下只能有一个 selected take。
- 多 emotion source 混用时后端返回可读错误，前端展示该错误。

### FR4：VoxCPM2 生产台

必须支持：

- 保留现有 VoxCPM2 生成能力。
- 运行时状态从统一 runtime backend 获取。
- busy 或 configured false 时禁用生成入口。
- 成功输出可以保存为 Voice Library 声音资产。

验收标准：

- 旧 `generateAudio` IPC 不破坏。
- 成功生成后旧 History 仍可读。
- 与 IndexTTS2 并发点击时不会同时运行 GPU job。

### FR5：Jobs 任务视图

必须支持：

- 展示 `queued`、`running`、`succeeded`、`failed`、`cancelled`、`deleted`。
- `queued` job 可取消。
- `failed` job 可重试。
- job detail 展示 backend、model、mode、input_text、error_summary。
- IndexTTS2 job 展示 takes。

验收标准：

- 创建 job 后立即返回 queued。
- worker 串行执行 jobs。
- failed job 有可读 error_summary。

### FR6：RuntimeStatusCard 与 unload

必须支持：

- 展示 backend display name、configured、loaded、busy、device、last_error、active_job_id、started_at。
- `configured === false` 时展示缺失 runtime/checkpoint 文件。
- idle backend 可 unload。
- busy backend unload 返回可读错误。

验收标准：

- unload 后 runtime status 可见变化。
- unload 不影响旧 History 和 Voice Library。

### FR7：本地资产与兼容历史

必须支持：

- `assets` 记录音频路径、kind、sha256、mime_type、duration_seconds、sample_rate。
- `generation_jobs` 记录 backend、model、mode、status、params、output。
- `generation_takes` 记录 job、take_index、status、output、is_selected。
- 旧 `voices` 和 `generations` 保持可读。

验收标准：

- 空库可初始化。
- v1 旧库可 additive migrate。
- selected take 镜像旧 `generations`。
- 旧 Voice Library 和 History 查询不回退。

## 8. 数据与接口

### 8.1 Job status

```text
queued
running
succeeded
failed
cancelled
deleted
```

### 8.2 Asset kind

```text
voice
reference
generation_output
take_output
uploaded
```

### 8.3 RuntimeBackendStatus

```text
backend_id
display_name
enabled
configured
loaded
busy
device
last_error
capabilities
active_job_id
started_at
```

### 8.4 Required API

```text
GET  /runtime-backends
POST /runtime-backends/:id/unload

POST /generation-jobs
GET  /generation-jobs
GET  /generation-jobs/:id
POST /generation-jobs/:id/cancel
POST /generation-jobs/:id/retry
GET  /generation-jobs/:id/takes
POST /generation-takes/:id/select
```

### 8.5 Legacy API

迁移期必须保留：

```text
POST /generate-audio
POST /indextts2/generate
```

旧 IPC 必须保留：

```text
generateAudio
generateIndexTTS2
getRuntimeBackends
listVoices
listGenerations
```

## 9. 非功能需求

### 9.1 本地优先

- 不需要云端账户。
- 不依赖外部数据库。
- 不依赖外部 job service。
- 不自动上传音频资产。

### 9.2 路径安全

- runtime root：`data/runtimes/indextts2/`
- app data root：`data/app/`
- test temp root：`data/pytest-tmp/`
- checkpoint、cache、venv、Torch extensions 都必须在当前仓库所在驱动器内。

### 9.3 可恢复性

- 生成失败必须记录到 job/take error_summary。
- 失败任务不能导致应用崩溃。
- Renderer HTTP/IPC promise 必须有 timeout 或失败反馈。

### 9.4 可测试性

- 真实模型调用必须可被 fake runner 替代。
- RuntimeCoordinator 必须可测试 busy、release、error。
- Storage migration 必须覆盖空库和旧库。
- 前端拆分必须保持 TypeScript 类型检查通过。

## 10. 实施路线

### Phase 1：PRD 与 README

- 新增本 PRD。
- 更新 `docs/PRD/README.md`。
- 更新 `docs/README.md`。
- 后续更新根 README，重写项目定位。

### Phase 2：Renderer 解耦

- 建立目录骨架。
- 抽出 shared types 和 API client。
- 拆 AppShell、routes、i18n。
- 拆 VoxCPM2、IndexTTS2、Jobs、Storage 页面。

### Phase 3：IndexTTS2 多 take 产品化

- TakeComparisonPanel 接入真实 takes。
- selected take 镜像 History。
- selected take 保存为 Voice Library。

### Phase 4：Runtime 生命周期

- 实现真实 unload contract。
- RuntimeStatusCard 接入 unload。
- busy unload 返回可读错误。

### Phase 5：验证与收口

- 补后端 tests。
- 补 renderer type-level checks。
- 跑完整静态检查、构建和 Python 测试。
- 手动验收完整配音工作流。

## 11. 验收标准

### 静态检查

```powershell
npm.cmd run typecheck
npm.cmd run build
node --check electron\main.js
node --check electron\preload.js
```

### Python 测试

```powershell
.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_storage.py tests\test_voxcpm_app_service_cli.py tests\test_voxcpm_app_generation_service.py tests\test_voxcpm_app_indextts2_service.py -q --basetemp data\pytest-tmp
```

### 手动验收

- VoxCPM2 生成输出。
- 保存 VoxCPM2 输出为 Voice Library。
- IndexTTS2 使用 Voice Library 声音生成多个 take。
- 播放并选择 selected take。
- selected take 出现在 History。
- selected take 可保存为 Voice Library。
- 同时点击 VoxCPM2 和 IndexTTS2 生成不会并行占用 GPU。
- 未配置 IndexTTS2 时 UI 禁用生成并展示缺失原因。
- runtime/cache/output/db 均在当前仓库所在驱动器内。

## 12. 风险

### 前端拆分回归

风险：大规模拆分可能影响现有 UI 行为。

处理：以业务域拆分，每拆一个域就跑 typecheck/build，优先保持旧功能可用。

### Runtime unload 语义不清

风险：不同模型的加载、缓存和释放方式不同。

处理：先定义统一 contract，再分别实现 backend adapter；busy 状态先拒绝 unload。

### 真实 IndexTTS2 环境缺失

风险：没有 checkpoint 时无法做真实 smoke。

处理：fake runner 保证产品路径可测；真实 smoke 作为配置完成后的手动验收。

### 旧 History 兼容

风险：新 take/job 体系与旧 generations 产生重复或遗漏。

处理：仅 selected take 镜像旧 History，并加测试覆盖。

## 13. 待确认问题

- 根 README 的最终项目名是否保留 `VoxCPM-Box`，还是改为更明确的副标题，例如 `VoxCPM-Box Voice Studio`。
- IndexTTS2 多 take 的默认生成次数：每次点击只生成一个 take，还是支持一次生成 N 个 take。
- Voice Library 是否需要区分 `role voice`、`reference clip`、`take-derived voice`。
- Settings 是否在本轮承担 runtime 路径编辑，还是只做只读状态展示。
