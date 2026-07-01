# ADR 0002: 双模型 RuntimeCoordinator

## 状态

Accepted

## 日期

2026-06-27

## 背景

VoxCPM-Box 计划将 VoxCPM2 和 IndexTTS2 集成为互补的本地音频生成能力。VoxCPM2 负责声音资产和通用生产，IndexTTS2 负责台词级情绪和表演精修。

两个模型都可能占用大量 CUDA 显存。如果它们同时加载或同时推理，应用很容易耗尽 GPU 内存。当前 AppShell 后端只有 `GenerationService` 内部锁，这个锁只保护现有 VoxCPM2 synthesizer 路径，不足以支撑多个模型后端。

应用还需要一个共享存储层，让两个模型复用音色、历史、任务和生成产物，而不是各自形成数据孤岛。

## 决策

采用通用存储后端加单进程级 `RuntimeCoordinator`。

通用存储后端拥有用户数据：

- 音频资产
- 可复用音色
- 生成任务
- 生成 take
- 历史记录
- 媒体路径

模型后端只作为统一接口后的 adapter。VoxCPM2 和 IndexTTS2 不直接拥有 app storage 或 UI state。

`RuntimeCoordinator` 拥有模型运行状态：

- `enabled`
- `loaded`
- `busy`
- `device`
- `last_error`
- `capabilities`
- 默认 slot 数量为 `1` 的全局 GPU lease

任何后端在 CUDA 上加载或推理前，都必须先获得 coordinator lease。从一个后端切换到另一个后端时，必须先卸载当前后端，再加载下一个后端。

## 备选方案

### 只在前端切换模型

renderer 可以在某个模型运行时禁用另一个模型的按钮。

拒绝原因：UI 状态无法防住并发 IPC、后端重试、直接服务调用或未来队列任务。显存安全必须在真正执行模型的后端 enforced。

### 每个模型各自维护存储

每个模型可以维护自己的音色、任务和输出。

拒绝原因：产品目标是能力互补。VoxCPM2 输出必须能被 IndexTTS2 复用，IndexTTS2 take 也必须进入同一套历史和资产系统。

### 启动时同时预热两个模型

两个后端都可以常驻显存，以便快速切换。

拒绝原因：第一版面向本地桌面 GPU，不能假设显存足够。只有在 runtime status、显存预算和 unload 行为实现后，才重新评估 warm loading。

## 后果

- 后端必须向 renderer 暴露模型状态。
- 第一版 IndexTTS2 集成应先做 fake backend 测试和 runtime state，再接真实推理。
- `generate-audio` 可以保留为兼容入口，但长任务应逐步迁移到 queued jobs。
- 现有 VoxCPM2 生成行为仍是默认路径，同时引入通用 runtime 层。
- 未来打包必须让模型缓存、可选运行时和 app data 留在当前项目盘符内，除非用户明确选择另一个受支持位置。
