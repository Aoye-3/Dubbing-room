# 测试与验收

## 当前测试入口

Python 测试：

```text
tests/test_voxcpm_app_storage.py
tests/test_voxcpm_app_service_cli.py
tests/test_voxcpm_app_generation_service.py
tests/test_voxcpm_app_indextts2_service.py
tests/test_voxcpm_app_indextts2_runtime_profile.py
tests/test_voxcpm_app_indextts25_stage_b.py
tests/test_verify_indextts_source_manifest.py
```

前端测试与检查：

```bat
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
node --check electron\main.js
node --check electron\preload.js
node --check electron\dev-runner.js
```

Python 检查：

```bat
.venv\Scripts\python.exe -m pytest tests -q --basetemp data\pytest-final-all
```

## 最新基线验证

验证日期：2026-08-12。

| 检查 | 结果 |
| --- | --- |
| full Python suite | 142 passed in 24.84s |
| renderer Vitest suite | 6 files / 35 tests passed |
| pinned source verification | 337 upstream files and mapped Pinyin asset verified |
| `npm.cmd run typecheck` | passed |
| `npm.cmd run build` | passed，1720 modules transformed |
| Electron main/preload/dev-runner syntax | passed |
| `git diff --check` | passed；仅有工作区 CRLF 提示 |

本轮验证没有执行真实 VoxCPM2 或 IndexTTS-2.5 推理。2.5 官方 config/权重未安装，runtime 正确报告 `missing_checkpoints`。

## 当前自动化覆盖

### Storage 与历史

- 空库初始化、旧库 additive migration 和 schema v5 nullable identity/warnings。
- Voice Library 生命周期、audio copy、soft delete 和 last-used 更新。
- Generation History 成功/失败、收藏、回收站、恢复和永久清理。
- 生成结果提升为 voice，并维护 History/Voice 双向关联。
- assets/jobs/takes 生命周期、selected take 唯一性和幂等 History 投影。
- failed take 不能被选择。

### Runtime 与模型 service

- VoxCPM2 fake synthesizer 和 generation job id 进入 runtime state。
- IndexTTS-2.5 fake model/runner、speaker/language 必填和四种 emotion source 互斥校验。
- 五语言、duration、text normalization、八维向量和 expert generation kwargs 映射。
- text emotion capability gate、Qwen 条件加载、init/infer OOM 专用错误。
- 单 GPU `RuntimeCoordinator` lease，以及 VoxCPM2 持有 lease 时 IndexTTS2 拒绝执行。
- 固定源码 manifest、2.0/2.5 资产族、source/runtime/config/checkpoint 缺失和项目外路径拒绝。
- runtime profile 原子持久化、BF16 解析、低显存 warning、Settings API。
- JSONL worker ready/take/complete、一次加载多 Take、device、timeout、EOF、错误 code 和 missing output。
- `/runtime-backends`、`/generate-audio`、`/indextts2/generate` 的成功/错误响应。

### Jobs、takes 与兼容接口

- generation job create/list/get 和 VoxCPM2 queued execution。
- queued/running cancel、确定性 finalization race、lease 释放和 failed job retry。
- IndexTTS-2.5 多 take 聚合、部分失败、每个 take 的 identity/warnings/终态。
- take playback asset payload、选择 take 和 selected take 保存为 voice。
- legacy app-service 与同步生成接口继续工作。

### Renderer

- 单一 IndexTTS-2.5 form mapper 的五语言、四情感、duration/vector/text capability 校验。
- ZH/EN/JA pronunciation annotation 语法和 ES/AR 条件显隐。
- Settings profile load/save、checkbox persistence 和 structured error。
- Performance Desk bounded polling、terminal cleanup、部分失败、选择、导出、保存和 action error。
- Electron plain structured rejection 的统一错误分类，避免旧页面显示 `[object Object]`。
- History 的 model/version/language/duration/warnings 展示。

## 尚缺自动化覆盖

- Electron IPC 集成测试：非 2xx 结构化错误、media URL、原生导出和 update bridge。
- 桌面 AppShell E2E：生成、播放、保存音色、History、Trash、Jobs 用户路径。
- RuntimeCoordinator 反向竞争场景：IndexTTS2 持有 lease 时 VoxCPM2 请求。
- backend 重启时 queued/running job 的恢复策略。
- 真实 unload/free、CUDA cleanup 和跨进程锁。
- 真实 VoxCPM2 / IndexTTS2 smoke 与显存并发验收。

## 下一阶段自动化计划

1. 为真实 Electron IPC 增加 media URL、原生导出和 update bridge 集成测试。
2. 增加最小桌面 smoke：AppShell 启动、backend ready、页面导航和基础数据加载。
3. 补 RuntimeCoordinator 反向竞争和跨进程实例保护测试。
4. 设计并测试 backend 重启后的 queue 恢复策略。

## 真实模型验收

需要人工或集成环境执行：

资源清单状态（2026-08-12）：IndexTTS-2.5 固定源码和项目内 runtime Python 存在；官方 `checkpoints-2.5/config.yaml` 与模型权重未安装，不能执行真实推理。2.0 checkpoint 只作为回滚资产保留，禁止混用。

1. 运行 `scripts/prepare_indextts2_runtime.ps1`，确认所有 cache/runtime 环境变量仍指向当前项目驱动器。
2. 请求 `/runtime-backends`，确认 VoxCPM2 与 IndexTTS2 的 `configured`、`device`、`state` 和缺失项详情符合实际。
3. VoxCPM2 Voice Design、Voice Clone、Ultimate Clone 各生成一次。
4. IndexTTS-2.5 对 ZH/EN/JA/ES/AR 执行基础与跨语言音色生成。
5. same voice、emotion audio、emotion vector、emotion text 各生成一次；8GB 文本情感要记录 warning、峰值显存和 OOM code。
6. 验证 `duration_factor` 0.5/1.0/2.0 的输出时长单调变化，并执行 Pinyin/CMU/Kana 标注。
7. 三 Take 验证一次加载、部分失败、running cancel、显存释放和 JSONL 完整事件。
8. 确认输出为可播放 22.05 kHz WAV，selected take 可进入 History、导出并保存为 Voice Library 音色。
9. 并发发起双 backend 请求，确认不会同时占用 GPU，且失败/完成后 lease 正确释放。
10. 确认没有 runtime、cache、checkpoint、生成文件或 pytest 临时文件写到 C 盘或仓库外。
11. 记录硬件、驱动、CUDA、source commit、model dir、峰值显存、耗时、模式和失败详情；不提交私人参考音频或权重。

## 每轮收尾

每轮实现结束前：

- 清理 `data/pytest-tmp`。
- 确认 `git status --short`。
- 不提交权重、cache、venv。
- 汇报哪些测试已跑，哪些未跑。
