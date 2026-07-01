# 模型与运行时

## 模型分工

### VoxCPM2

职责：

- 声音设计。
- 声音克隆。
- 极致克隆。
- 通用旁白。
- 多语言生成。
- 可复用音色创建。

当前代码：

- `src/voxcpm_app/generation_service.py`
- `VoxCPMSynthesizer`
- `GenerationService`
- 前端 `GenerationPage`

### IndexTTS2

职责：

- 单句台词精修。
- 情绪控制。
- 语气和表演版本。
- 多 take 对比。
- 基于已保存音色的角色表演。

当前代码：

- `src/voxcpm_app/indextts2_service.py`
- `src/voxcpm_app/indextts2_worker.py`
- `third_party/index-tts/`
- 前端 `IndexTTS2Page`

## 当前 RuntimeCoordinator

文件：

```text
src/voxcpm_app/runtime.py
```

当前能力：

- 单进程 `threading.Lock`。
- `lease(backend_id)`。
- `active_job_id`。
- `started_at`。
- `is_busy()`。
- `is_busy_backend(backend_id)`。
- `last_error(backend_id)`。
- `status(backend_id)`。
- `RuntimeBackendStatus`。
- VoxCPM2 和 IndexTTS2 共享同一个 GPU lease。

当前限制：

- queue 是进程内 FIFO，不会在后端重启后恢复旧的 queued/running job。
- queued job 可以 cancel；running job 目前只记录 cancel requested，不会强制中断。
- 没有 load/unload。
- 没有 CUDA cache cleanup。
- 没有跨进程锁。

## 目标 RuntimeCoordinator

应支持：

```text
backend_id
active_job_id
busy
loaded
configured
device
started_at
last_error
capabilities
```

目标状态：

- `enabled`
- `disabled`
- `configured`
- `missing_runtime`
- `missing_checkpoints`
- `busy`
- `loaded`
- `failed`

目标行为：

- VoxCPM2 和 IndexTTS2 使用同一个 GPU lease。
- 默认 GPU slot = 1。
- 切换模型前释放当前 lease。
- 可选执行 unload。
- 清理 CUDA cache。
- 前端只展示状态，不决定并发。

## IndexTTS2 runtime 路径

默认 source：

```text
third_party/index-tts/
```

默认 runtime python：

```text
data/runtimes/indextts2/.venv/Scripts/python.exe
```

默认 checkpoints：

```text
third_party/index-tts/checkpoints/
```

默认 cfg：

```text
third_party/index-tts/checkpoints/config.yaml
```

必需 checkpoint 文件：

```text
config.yaml
bpe.model
gpt.pth
s2mel.pth
```

当前本地缺失：

- runtime python。
- `config.yaml`。
- `gpt.pth`。
- `s2mel.pth`。
- `bpe.model`。
- 其他辅助模型 cache。

## IndexTTS2 环境隔离

必须放在项目内：

```text
data/runtimes/indextts2/
```

建议环境变量：

```powershell
.\scripts\prepare_indextts2_runtime.ps1
```

建议命令：

```powershell
Set-Location F:\.VoxCPM\VoxCPM\third_party\index-tts
uv sync
uv tool install "huggingface-hub[cli,hf_xet]"
hf download IndexTeam/IndexTTS-2 --local-dir F:\.VoxCPM\VoxCPM\third_party\index-tts\checkpoints
uv run tools/gpu_check.py
```

## Worker 参数事实

当前已传：

- `spk_audio_prompt`
- `text`
- `output_path`
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

缺口：

- `use_accel` 未传。
- `use_torch_compile` 未传。
- `aux_paths` 未传。
- `do_sample` 上游可能实际写死为 true。

## 失败模式

前后端应识别并展示：

- source snapshot missing。
- runtime python missing。
- checkpoints missing。
- checkpoints incomplete。
- auxiliary model download failed。
- CUDA OOM。
- torch / torchaudio CUDA wheel mismatch。
- DeepSpeed unsupported。
- worker import failed。
- worker JSON parse failed。
- runtime busy。
- request validation failed。
- generated output missing。
- truncation warning。

## 下一步实现顺序

1. VoxCPM2 接入 `RuntimeCoordinator`。
2. `RuntimeCoordinator` 扩展 active job 和状态。
3. IndexTTS2 status 完整检查 checkpoints。
4. worker 传 device。
5. 增加 timeout 和错误分类。
6. 配置真实 runtime。
