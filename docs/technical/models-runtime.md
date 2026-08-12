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

### IndexTTS-2.5

职责：

- 单句台词精修。
- 情绪控制。
- 语气和表演版本。
- 多 take 对比。
- 基于已保存音色的角色表演。

当前代码：

- `src/voxcpm_app/indextts2_service.py`
- `src/voxcpm_app/indextts2_worker.py`
- `src/voxcpm_app/indextts2_runtime_profile.py`
- `third_party/index-tts/`
- 前端 `IndexTTS2Page` / `PerformanceDesk`

兼容标识：

- backend id：`indextts2`，保持 API、历史和数据库兼容。
- model id：`IndexTTS-2.5`。
- model version：`2.5`。
- upstream commit：`a371df7d0746a0ae7fdf075798b6b04e34a0132e`。

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
- IndexTTS-2.5 queued/running job 可以 cancel；running cancel 会终止当前 worker 并取消未完成 take。
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
model_id
model_version
upstream_commit
supported_languages
effective_precision
text_emotion_enabled
warnings
paths
```

当前状态值：

- `configured`
- `missing_runtime`
- `missing_checkpoints`
- `busy`
- `loaded`
- `model_version_mismatch`

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
- VoxCPM2 running job 的统一强制中断协议；IndexTTS-2.5 子进程 job 已支持终止。

## IndexTTS-2.5 runtime 路径

默认 source：

```text
third_party/index-tts/
```

默认 runtime python：

```text
data/runtimes/indextts2/.venv/Scripts/python.exe
```

默认 2.5 checkpoints：

```text
third_party/index-tts/checkpoints-2.5/
```

默认 cfg：

```text
third_party/index-tts/checkpoints-2.5/config.yaml
```

必需 checkpoint 文件和目录：

```text
config.yaml
gpt.pth
s2mel.pth
codec.pth
multilingual_zh_ja_yue_char_del.tiktoken
wav2vec2bert_stats.pt
```

文本情感还需要上游 2.5 模型包提供的 QwenEmotion 目录。缺少该目录时基础 2.5 能力可独立判断，`text_emotion_enabled=false`；选择文本情感的请求会在启动 worker 前返回 `text_emotion_unavailable`。

2.0 回滚资产保留在：

```text
third_party/index-tts/checkpoints/
```

适配器不会在 2.5 路径缺失时回退或混用该目录。源码、config、Tiktoken、codec 或权重家族不一致时返回 `model_version_mismatch`。

2026-08-12 本地资源检查：

- `data/runtimes/indextts2/.venv/Scripts/python.exe` 存在。
- 固定 2.5 源码与 `SOURCE_MANIFEST.json` 的 337 个文件哈希一致。
- `checkpoints-2.5` 中只有可追溯的 `pinyin.vocab` 和安装说明；官方 `config.yaml` 与模型权重未安装。
- `/runtime-backends` 因此正确返回 `configured=false`、`state=missing_checkpoints`，不会错误使用 2.0 权重。
- 当前 RTX 5060 Laptop 8GB 环境中 `precision=auto` 解析为 BF16，并返回低显存结构化 warning。

## IndexTTS-2.5 环境隔离

必须放在项目内：

```text
data/runtimes/indextts2/
```

先准备项目内环境变量和缓存目录：

```powershell
.\scripts\prepare_indextts2_runtime.ps1
```

脚本只创建/声明项目内路径，不下载依赖或 checkpoint。后续依赖安装和模型下载也必须沿用该脚本设置的 `UV_*`、`HF_*` 和 cache 环境变量，不能写到 C 盘或用户级目录。

运行时就绪检查以 `/runtime-backends` 的 `indextts2` 条目为准。`third_party/index-tts/tools/gpu_check.py` 是上游辅助工具，不替代 AppShell 的资产族、profile 和项目内路径校验。

基础路径检查：

```powershell
.\scripts\prepare_indextts2_runtime.ps1
Test-Path .\data\runtimes\indextts2\.venv\Scripts\python.exe
Test-Path .\third_party\index-tts\checkpoints-2.5\config.yaml
```

## Runtime profile

配置文件：

```text
data/app/indextts2-runtime.json
```

默认值：

```json
{
  "precision": "auto",
  "allow_text_emotion": true,
  "use_cuda_kernel": false,
  "use_deepspeed": false,
  "use_accel": false,
  "use_torch_compile": false
}
```

Settings 通过 `GET/POST /runtime-backends/indextts2/config` 读写该 profile。保存只影响下一个 job；模型加载参数不进入逐句 payload。`auto` 优先 BF16，不支持时显式回退 FP32 并返回 warning。

## Worker 生命周期与参数

每个 IndexTTS-2.5 job 在整个 `RuntimeCoordinator` lease 内启动一个子进程。worker 导入 `indextts.infer_v2_5.IndexTTS2`，加载一次模型，顺序处理所有 take，然后退出。stdout 只输出 JSONL 事件；上游日志重定向到 stderr 并由父进程持续读取。

事件：

```text
ready
take_started
take_succeeded
take_failed
complete
```

构造期参数来自 runtime profile：

- `use_bf16`
- `use_qwen_emo`（仅 text emotion job 为 true）
- `use_cuda_kernel`
- `use_deepspeed`
- `use_accel`
- `use_torch_compile`
- `device`

逐 take 参数：

- `spk_audio_prompt`
- `text`
- `lang`（外部字段 `language` 映射为 `ZH/EN/JA/ES/AR`）
- `output_path`
- `emo_audio_prompt`
- `emo_alpha`
- `emo_vector`
- `use_emo_text`
- `emo_text`
- `use_random`
- `interval_silence`
- `max_text_tokens_per_segment`
- `duration_factor`
- `text_normalization`
- `top_p`
- `top_k`
- `temperature`
- `length_penalty`
- `num_beams`
- `repetition_penalty`
- `max_mel_tokens`

`do_sample` 不再是可编辑字段；固定上游 2.5 路径实际使用 `True`。service 对专家参数执行白名单和范围校验后，worker 显式传给 `infer()`。

## 失败模式

前后端应识别并展示：

- source snapshot missing。
- runtime python missing。
- checkpoints missing。
- checkpoints incomplete。
- source/config/checkpoint family mismatch。
- auxiliary model download failed。
- CUDA OOM。
- text emotion unavailable / text emotion memory insufficient。
- torch / torchaudio CUDA wheel mismatch。
- DeepSpeed unsupported。
- worker import failed。
- worker JSONL protocol/EOF failed。
- runtime busy。
- request validation failed。
- generated output missing。
- truncation warning。

## 下一步实现顺序

1. 安装经许可审查的 2.5 config/权重，完成五语言、四情感、0.5/1.0/2.0 时长和 8GB 峰值显存真实验收。
2. 验证真实并发请求不会绕过单 GPU lease，并确认取消、OOM、超时后 lease/state 和显存恢复。
3. 定义并实现 runtime unload/free 与 CUDA cache cleanup。
4. 增加跨进程锁或明确限制只能运行一个 Python backend 实例。
5. 为 backend 重启后的 queued/running job 制定恢复策略。
