# 双模型互补应用壳 PRD

## 产品定位

VoxCPM-Box 将从单模型 AppShell 演进为本地双模型音频生成工作台，面向视频配音、AIGC 短片配音、角色声音资产管理和台词级表演精修。

产品不是简单的“模型下拉切换器”。VoxCPM2 和 IndexTTS2 负责不同环节，并通过同一个通用存储后端互补：

- 通用存储后端：统一保存音频资产、可复用音色、生成任务、take、历史、模型运行状态、路径和日志。
- VoxCPM2 生产台：创建和维护声音资产，承担通用旁白、多语言生产、声音设计、可控克隆和极致克隆。
- IndexTTS2 表演台：基于已有角色音色，对单句台词做情绪、语气、表演版本和多 take 精修。

## 目标用户

- 需要本地完成视频旁白或 AIGC 短片配音的创作者。
- 需要管理角色音色、复用声音资产和保留生成历史的用户。
- 需要先生成基础配音，再对重点台词做情绪表演精修的用户。

## 模型职责

### VoxCPM2

VoxCPM2 是默认的声音资产和通用生产引擎。

它负责：

- 通过自然语言声音描述做 Voice Design。
- 使用上传音频或已保存音色做 Voice Cloning。
- 使用参考音频加 transcript 做 Ultimate Cloning。
- 通用旁白、多语言生产和批量音频生产。
- 产出可复用的声音资产，供后续 IndexTTS2 台词精修使用。

VoxCPM2 的输出必须进入通用存储后端，并可以保存为 Voice Library 中的可复用音色。

### IndexTTS2

IndexTTS2 是台词级情绪和表演精修引擎。

它负责：

- 单句台词的情绪表达。
- 同一句台词的多个 take。
- 可用时支持情绪音频、情绪文本、情绪向量等情绪来源控制。
- 使用通用 Voice Library 中的角色音色进行台词精修。
- 未来仅在上游 release 暴露可靠 duration control 后，再承担时长对齐类流程。

IndexTTS2 不应被设计成另一个通用生产入口。它的 UI 应围绕“台词行、角色音色、情绪控制、多 take 对比”组织。

## 应用三板块

### 通用存储后端

用途：

- 展示 AppShell 后端健康、数据库路径、媒体目录、日志和模型运行状态。
- 提供 VoxCPM2 与 IndexTTS2 共用的资产层。
- 管理已保存音色、生成任务、输出文件和未来清理工具。

核心界面：

- 后端状态和日志。
- App 数据路径。
- Voice Library 健康状态。
- 生成历史和任务状态。
- VoxCPM2 与 IndexTTS2 的模型运行状态。

### VoxCPM2 生产台

用途：

- 创建新的声音资产。
- 生成通用旁白和可复用音频。
- 保留当前 Voice Design、Voice Cloning、Ultimate Cloning 三类流程。

核心界面：

- 声音设计。
- 声音克隆。
- 极致克隆。
- 已保存音色选择器。
- 输出音频播放。
- 保存生成结果为可复用音色。
- VoxCPM2 参数复用和历史回填。

### IndexTTS2 表演台

用途：

- 在基础角色音色已经存在后，精修重点台词。
- 生成多个情绪或表演版本，并统一进入项目历史。

核心界面：

- 台词列表。
- 来自共享 Voice Library 的角色音色选择器。
- 情绪来源控制。
- 表演参数。
- 多 take 对比。
- 将选定 take 提交到通用历史和资产库。

## 主流程

1. 用户在 VoxCPM2 生产台导入或创建可复用音色。
2. 音色保存到通用 Voice Library。
3. 用户用 VoxCPM2 生成通用旁白或角色基础台词。
4. 重点台词进入 IndexTTS2 表演台。
5. IndexTTS2 使用已保存的角色音色生成情绪或表演 take。
6. 用户选定 take 后，结果进入通用存储后端，并出现在共享历史中。

## 运行时和显存策略

前端可以展示模型状态，但不能决定模型并发。

后端通过 `RuntimeCoordinator` 统一调度模型：

- 默认 GPU slot 数量为 1。
- VoxCPM2 和 IndexTTS2 不能同时加载或推理。
- 模型后端状态至少包括 `enabled`、`disabled`、`unavailable`、`loaded`、`busy`、`failed`。
- 切换活跃模型前，必须先释放当前后端，再加载下一个后端。
- 释放时应调用模型适配器的 unload hook、Python garbage collection，并在 CUDA 可用时清理 CUDA cache。
- disabled 或 unavailable 的模型必须返回结构化状态，不允许进入调度。

这个规则存在于后端，因为两个模型都可能占用大量 CUDA 显存。只在 UI 上禁用按钮不能保证安全。

## MVP 范围

第一阶段只完成双模型架构规划：

- 文档化三板块产品结构。
- 明确目标前端和后端代码结构。
- 定义 asset、job、take、runtime status 等通用存储词汇。
- 定义单 GPU lease 的 RuntimeCoordinator 设计。
- 同步 README 和 app-dev 文档。

PRD 之后的第一轮实现应先做结构拆分和 fake backend 测试，再接入真实 IndexTTS2 推理。

## 非目标

- 不捆绑 IndexTTS2 权重。
- 不自动 clone IndexTTS2 仓库。
- 不把依赖、模型缓存、生成文件或虚拟环境写到 `C:`。
- 不让 VoxCPM2 与 IndexTTS2 同时推理。
- 不把 IndexTTS2 参数塞进 VoxCPM2 字段。
- 不继续把所有前端代码堆进 `electron/renderer/src/main.tsx`。
- 不移除原始 Gradio 开发路线。

## 前端架构方向

接入 IndexTTS2 UI 之前，renderer 应先拆分：

```text
electron/renderer/src/
  app/
    App.tsx
    navigation.ts
    i18n.ts
    shellStore.ts
  shared/
    api/
    components/
    media/
  storage/
    pages/
    components/
  voxcpm/
    pages/
    components/
    types.ts
  indextts2/
    pages/
    components/
    types.ts
```

`main.tsx` 应变成轻量 bootstrap 文件。功能状态应放进 feature module 或 shared hooks。

## 后端架构方向

Python app 层应演进为桌面 TTS 工作流后端：

```text
src/voxcpm_app/
  storage/
  runtime/
  backends/
    voxcpm2.py
    indextts2.py
  jobs/
  voice_library.py
  generation_history.py
  backend_server.py
```

核心后端概念：

- `AssetStore`：保存音频文件、checksum、duration、sample rate、media type 和项目相对路径。
- `GenerationJob`：跟踪 queued/running/succeeded/failed/cancelled 的工作。
- `GenerationTake`：保存一条台词或一次请求的某个输出版本。
- `TTSBackend`：VoxCPM2 和 IndexTTS2 共用的模型适配器契约。
- `RuntimeCoordinator`：管理模型启用状态、GPU lease、load/unload 和 busy 状态。

## 验收标准

- 产品文档将 VoxCPM2 和 IndexTTS2 描述为互补模块，而不是可互换按钮。
- 文档明确通用存储后端是两个模型互补的连接层。
- 架构文档定义稳定的前端拆分和后端 runtime 拆分。
- API 文档包含模型运行状态和 job/take 词汇。
- 数据设计包含未来 `assets`、`generation_jobs`、`generation_takes` 概念。
- README 说明双模型方向和当前实现状态。
