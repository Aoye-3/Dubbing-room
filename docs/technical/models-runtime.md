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
- 前端 `electron/renderer/src/voxcpm/VoxCPMPage.tsx`

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

## Runtime 状态契约

`GET /runtime-backends` 当前返回：

```text
backend_id
display_name
enabled
active_job_id
busy
loaded
configured
device
started_at
last_error
capabilities
state
details
```

当前状态值：

- `configured`
- `missing_runtime`
- `missing_checkpoints`
- `busy`
- `loaded`

`enabled` / `configured` / `loaded` / `busy` 是独立布尔字段。运行失败通过 `last_error` 和结构化错误响应表示，当前不会把 `state` 设置为单独的 `failed` 值。

当前行为：

- VoxCPM2 和 IndexTTS2 使用同一个 GPU lease。
- 默认 GPU slot = 1。
- lease 在成功或异常退出时释放。
- 前端只展示状态，不决定并发。

尚未实现：

- 真实 load/unload/free；当前 unload route 只返回 `unloaded: false`。
- CUDA cache cleanup。
- 跨进程 runtime lock。
- running job 的强制中断。

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

必需 checkpoint 文件和目录：

```text
config.yaml
bpe.model
gpt.pth
s2mel.pth
wav2vec2bert_stats.pt
feat1.pt
feat2.pt
qwen0.6bemo4-merge/
hf_cache/semantic_codec_model.safetensors
hf_cache/campplus_cn_common.bin
hf_cache/bigvgan/config.json
hf_cache/bigvgan/bigvgan_generator.pt
hf_cache/w2v-bert-2.0/
```

2026-08-07 本地资源检查：

- `data/runtimes/indextts2/.venv/Scripts/python.exe` 存在。
- 上述 checkpoint 文件和目录均存在。
- 这只表示文件清单就绪，不代表模型能够成功加载或完成 GPU 推理；真实 smoke test 仍未记录。

## IndexTTS2 环境隔离

必须放在项目内：

```text
data/runtimes/indextts2/
```

先准备项目内环境变量和缓存目录：

```powershell
.\scripts\prepare_indextts2_runtime.ps1
```

脚本只创建/声明项目内路径，不下载依赖或 checkpoint。后续依赖安装和模型下载也必须沿用该脚本设置的 `UV_*`、`HF_*` 和 cache 环境变量，不能写到 C 盘或用户级目录。

运行时就绪检查以 `/runtime-backends` 的 `indextts2` 条目为准；仓库当前没有 `tools/gpu_check.py`，不要把该命令作为验收入口。

基础路径检查：

```powershell
.\scripts\prepare_indextts2_runtime.ps1
Test-Path .\data\runtimes\indextts2\.venv\Scripts\python.exe
Test-Path .\third_party\index-tts\checkpoints\config.yaml
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
- `do_sample`
- `top_p`
- `top_k`
- `temperature`
- `length_penalty`
- `num_beams`
- `repetition_penalty`
- `max_mel_tokens`
- `use_fp16`
- `use_cuda_kernel`
- `use_deepspeed`
- `use_accel`
- `use_torch_compile`

补充状态：

- acceleration flags 已传到 IndexTTS2 构造边界。
- `device` 已从 service payload 传给 worker/model。
- worker timeout、末行 JSON 解析、结构化错误保留和输出文件校验已有自动化覆盖。
- `do_sample` 在 VoxCPM2 上游路径仍可能写死；本地 contract 保留该字段但不能承诺改变上游采样行为。

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

1. 在当前项目内 runtime/checkpoint 上完成 VoxCPM2 与 IndexTTS2 真实 smoke test。
2. 验证真实并发请求不会绕过单 GPU lease，并确认异常后 lease/state 恢复。
3. 定义并实现 unload/free 和 running cancellation contract。
4. 增加跨进程锁或明确限制只能运行一个 Python backend 实例。
5. 把 structured runtime error 的 `code` / `details` 保留到 Electron/Renderer UI。
