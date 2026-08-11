# 测试与验收

## 当前测试入口

Python 测试：

```text
tests/test_voxcpm_app_storage.py
tests/test_voxcpm_app_service_cli.py
tests/test_voxcpm_app_generation_service.py
tests/test_voxcpm_app_indextts2_service.py
```

前端检查：

```bat
npm.cmd run typecheck
npm.cmd run build
node --check electron\main.js
node --check electron\preload.js
node --check electron\dev-runner.js
```

Python 检查：

```bat
.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_storage.py tests\test_voxcpm_app_service_cli.py tests\test_voxcpm_app_generation_service.py tests\test_voxcpm_app_indextts2_service.py -q --basetemp data\pytest-tmp
```

## 最新基线验证

验证日期：2026-08-07。

| 检查 | 结果 |
| --- | --- |
| targeted Python AppShell suite | 45 passed in 10.01s |
| `npm.cmd run typecheck` | passed |
| `npm.cmd run build` | passed，1717 modules transformed |
| Electron main/preload/dev-runner syntax | passed |
| `git diff --check` | passed；仅有工作区 CRLF 提示 |

本轮验证没有执行真实 VoxCPM2 或 IndexTTS2 推理。

## 当前自动化覆盖

### Storage 与历史

- 空库初始化和 v1 -> v2 additive migration。
- Voice Library 生命周期、audio copy、soft delete 和 last-used 更新。
- Generation History 成功/失败、收藏、回收站、恢复和永久清理。
- 生成结果提升为 voice，并维护 History/Voice 双向关联。
- assets/jobs/takes 生命周期、selected take 唯一性和幂等 History 投影。
- failed take 不能被选择。

### Runtime 与模型 service

- VoxCPM2 fake synthesizer 和 generation job id 进入 runtime state。
- IndexTTS2 fake runner、speaker 必填和 emotion source 互斥校验。
- emotion vector 总值上限和 text emotion fallback。
- 单 GPU `RuntimeCoordinator` lease，以及 VoxCPM2 持有 lease 时 IndexTTS2 拒绝执行。
- IndexTTS2 source/runtime/config/checkpoint 缺失状态和项目外路径拒绝。
- worker device 传递、timeout、错误 code 保留和 missing output 分类。
- `/runtime-backends`、`/generate-audio`、`/indextts2/generate` 的成功/错误响应。

### Jobs、takes 与兼容接口

- generation job create/list/get 和 VoxCPM2 queued execution。
- queued job cancel、failed job retry 基础路径。
- IndexTTS2 多 take 聚合，每个 take 的成功/失败状态。
- take playback asset payload、选择 take 和 selected take 保存为 voice。
- legacy app-service 与同步生成接口继续工作。

## 尚缺自动化覆盖

- Renderer 组件测试：runtime 卡片、禁用态、emotion payload 和 result panel。
- Electron IPC 集成测试：非 2xx 结构化错误、media URL、原生导出和 update bridge。
- 桌面 AppShell E2E：生成、播放、保存音色、History、Trash、Jobs 用户路径。
- RuntimeCoordinator 反向竞争场景：IndexTTS2 持有 lease 时 VoxCPM2 请求。
- backend 重启时 queued/running job 的恢复策略。
- running job cancel、真实 unload/free 和跨进程锁。
- 真实 VoxCPM2 / IndexTTS2 smoke 与显存并发验收。

## 下一阶段自动化计划

1. 为 API client 和 Electron IPC 增加结构化错误保真测试。
2. 为 VoxCPM2、IndexTTS2、Jobs 和 History 的关键状态增加 Renderer 测试。
3. 增加最小桌面 smoke：AppShell 启动、backend ready、页面导航和基础数据加载。
4. 补双向 runtime lease 竞争、异常释放和 running cancel contract 测试。

## 真实模型验收

需要人工或集成环境执行：

资源清单状态（2026-08-07）：IndexTTS2 项目内 runtime Python 和文档列出的必需 checkpoint 文件/目录均存在，但尚未执行真实推理。

1. 运行 `scripts/prepare_indextts2_runtime.ps1`，确认所有 cache/runtime 环境变量仍指向当前项目驱动器。
2. 请求 `/runtime-backends`，确认 VoxCPM2 与 IndexTTS2 的 `configured`、`device`、`state` 和缺失项详情符合实际。
3. VoxCPM2 Voice Design、Voice Clone、Ultimate Clone 各生成一次。
4. IndexTTS2 same voice、emotion audio、emotion vector、emotion text 各生成一次。
5. 确认 worker 返回可解析 JSON，输出 wav 进入 `data/app/generations/`，History 和 Jobs 均可播放。
6. 将一次 VoxCPM2 输出和一次 selected take 保存为 Voice Library 音色并复用。
7. 并发发起双 backend 请求，确认不会同时占用 GPU，且失败/完成后 lease 正确释放。
8. 确认没有 runtime、cache、checkpoint、生成文件或 pytest 临时文件写到 C 盘或仓库外。
9. 在本文件记录硬件、device、命令、生成模式、结果和失败详情。

## 每轮收尾

每轮实现结束前：

- 清理 `data/pytest-tmp`。
- 确认 `git status --short`。
- 不提交权重、cache、venv。
- 汇报哪些测试已跑，哪些未跑。
