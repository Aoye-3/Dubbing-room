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
```

Python 检查：

```bat
.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_storage.py tests\test_voxcpm_app_service_cli.py tests\test_voxcpm_app_generation_service.py tests\test_voxcpm_app_indextts2_service.py -q --basetemp data\pytest-tmp
```

## 当前覆盖

已有覆盖：

- Voice Library storage。
- Generation History。
- service CLI。
- VoxCPM2 fake synthesizer。
- IndexTTS2 fake runner。
- speaker required。
- emotion source validation。
- RuntimeCoordinator busy。
- `/runtime-backends`。
- `/indextts2/generate`。

缺口：

- Renderer tests。
- Electron IPC integration tests。
- RuntimeCoordinator 覆盖 VoxCPM2。
- checkpoint 完整性检查。
- worker timeout。
- device 传递。
- job queue。
- assets/jobs/takes migration。
- selected take projection。
- 真实 IndexTTS2 smoke test。

## 下一阶段测试计划

### RuntimeCoordinator

新增测试：

- VoxCPM2 fake job 持有 lease 时，IndexTTS2 fake job 失败或排队。
- IndexTTS2 fake job 持有 lease 时，VoxCPM2 fake job 失败或排队。
- lease 内异常会写 `last_error`。
- lease 结束后释放 busy。
- active backend 和 active job 状态正确。

### IndexTTS2 runtime status

新增测试：

- source snapshot missing。
- runtime python missing。
- config missing。
- required checkpoint missing。
- all files present -> configured true。
- `INDEXTTS2_MODEL_DIR` 覆盖默认路径。
- `INDEXTTS2_CFG_PATH` 覆盖默认路径。

### Worker

新增测试：

- worker payload 包含 device。
- worker 返回 invalid JSON 时 service 失败落库。
- worker return code 非 0 时失败落库。
- worker timeout 时失败落库。
- stdout 多行日志时仍解析最后一行 JSON。

### Storage v2

新增测试：

- 空库创建 assets/jobs/takes。
- 旧库 additive migration。
- VoiceRecord 旧 shape 兼容。
- GenerationRecord 旧 shape 兼容。
- asset create/list/get。
- job create/update/list。
- take create/select。
- selected take 镜像 legacy generation。

### Frontend

新增测试方向：

- typecheck covers new types。
- runtime missing disables generate。
- emotion mode 切换只提交一个 emotion source。
- advanced 参数 payload 正确。
- generated output audio URL 正确。
- take selected state 正确。

## 真实模型验收

需要人工或集成环境执行：

1. 确认没有 C 盘 cache。
2. `uv run tools/gpu_check.py` 通过。
3. `/runtime-backends` 显示 IndexTTS2 configured。
4. same voice 生成成功。
5. emotion audio 生成成功。
6. emotion vector 生成成功。
7. emotion text 生成成功。
8. 输出 wav 进入 `data/app/generations/`。
9. History 可播放。
10. 并发请求不会同时运行两个 GPU backend。

## 每轮收尾

每轮实现结束前：

- 清理 `data/pytest-tmp`。
- 确认 `git status --short`。
- 不提交权重、cache、venv。
- 汇报哪些测试已跑，哪些未跑。

