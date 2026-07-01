# API Contracts

These contracts describe application-layer behavior. They do not describe model internals.

双模型 AppShell 的 API contract 应“知道模型差异”，但以通用存储为中心。VoxCPM2 和 IndexTTS2 请求必须通过 common storage、job 和 runtime status contract，而不是各自拥有一套孤立 API。

## Service Layer Contracts

### Voice Library

#### `create_voice`

Input:

```json
{
  "source_audio_path": "string",
  "display_name": "string",
  "tags": ["string"],
  "notes": "string",
  "source": "upload"
}
```

Output:

```json
{
  "id": "uuid",
  "display_name": "string",
  "audio_path": "data/app/voices/{id}.wav",
  "audio_sha256": "string",
  "created_at": "iso-8601"
}
```

Behavior:

- Copy the source audio file into `data/app/voices/`.
- Compute SHA-256.
- Insert a `voices` row.
- Return the created voice metadata.

`source` may be `upload` for user-selected reference audio or `generated` when the user saves a successful generation output as a reusable voice.

#### `list_voices`

Input:

```json
{
  "include_deleted": false,
  "query": "optional string",
  "tag": "optional string"
}
```

Output:

```json
{
  "items": [
    {
      "id": "uuid",
      "display_name": "string",
      "tags": ["string"],
      "audio_path": "string",
      "last_used_at": "iso-8601 or null"
    }
  ]
}
```

#### `update_voice`

Editable fields:

- `display_name`
- `tags`
- `notes`

#### `delete_voice`

Behavior:

- Set `deleted_at`.
- Do not physically remove the audio file in the first implementation.

### Generation History

#### `create_generation`

Input:

```json
{
  "input_text": "string",
  "control_instruction": "string",
  "voice_id": "uuid or null",
  "reference_audio_path": "string or null",
  "prompt_text": "string",
  "cfg_value": 2.0,
  "inference_timesteps": 10,
  "normalize": false,
  "denoise": false
}
```

Output:

```json
{
  "id": "uuid",
  "status": "pending"
}
```

#### `mark_generation_running`

Input:

```json
{
  "id": "uuid"
}
```

Output:

```json
{
  "id": "uuid",
  "status": "running"
}
```

#### `mark_generation_succeeded`

Input:

```json
{
  "id": "uuid",
  "output_audio_path": "data/app/generations/{id}.wav",
  "sample_rate": 48000
}
```

Output:

```json
{
  "id": "uuid",
  "status": "succeeded"
}
```

#### `mark_generation_failed`

Input:

```json
{
  "id": "uuid",
  "error_summary": "string"
}
```

Output:

```json
{
  "id": "uuid",
  "status": "failed"
}
```

## AppShell Integration Contract

The AppShell should:

- Load saved voices with `list_voices`.
- Start the AppShell backend service in default app mode.
- Pass either an uploaded reference audio path or saved voice id to `generate-audio`.
- Let the generation service create, run, succeed, or fail generation records.
- Play stored audio through project-relative media URLs.

The AppShell must not embed the legacy Gradio WebUI as its primary UI.

### `generate-audio`

Input:

```json
{
  "input_text": "string",
  "control_instruction": "string",
  "prompt_text": "string",
  "cfg_value": 2.0,
  "inference_timesteps": 10,
  "normalize": false,
  "denoise": false,
  "reference": {
    "kind": "none"
  }
}
```

Reference variants:

```json
{ "kind": "none" }
{ "kind": "upload", "path": "absolute or process-readable audio path" }
{ "kind": "saved_voice", "voice_id": "uuid" }
```

Behavior:

- Uploaded references are copied to `data/app/tmp/` before generation.
- Saved voices resolve through the `voices` table and update `last_used_at` after success.
- Successful output audio is copied to `data/app/generations/{id}.wav`.
- Model execution is serialized by the AppShell backend process.

Output:

```json
{
  "id": "uuid",
  "status": "succeeded",
  "output_audio_path": "data/app/generations/{id}.wav",
  "sample_rate": 48000
}
```

Invalid requests return a JSON error with HTTP 400 from the AppShell backend. Synthesis failures return a generation record with `status: "failed"` and `error_summary`.

### Future `create-generation-job`

队列化 job contract 应成为长时间模型工作的首选入口。现有 `generate-audio` route 可以作为兼容 wrapper 保留。

Input:

```json
{
  "backend_id": "voxcpm2",
  "model_id": "openbmb/VoxCPM2",
  "mode": "voice_design",
  "input_text": "string",
  "voice_id": "uuid or null",
  "params": {}
}
```

Output:

```json
{
  "id": "uuid",
  "backend_id": "voxcpm2",
  "status": "queued"
}
```

`backend_id` 取值：

- `voxcpm2`: 声音资产和通用生产。
- `indextts2`: 台词级情绪和表演精修。

Job status 取值：

```text
queued
running
succeeded
failed
cancelled
deleted
```

后端必须在 dispatch work 之前拒绝 disabled 或 unavailable 的 backend。

### Future `list-runtime-backends`

renderer 使用这个 contract 展示模型状态。renderer 不应自行推断 GPU safety。

Output:

```json
{
  "items": [
    {
      "backend_id": "voxcpm2",
      "display_name": "VoxCPM2",
      "enabled": true,
      "loaded": false,
      "busy": false,
      "device": "cuda",
      "last_error": "",
      "capabilities": [
        "voice_design",
        "voice_clone",
        "ultimate_clone",
        "multilingual_generation"
      ]
    },
    {
      "backend_id": "indextts2",
      "display_name": "IndexTTS2",
      "enabled": false,
      "loaded": false,
      "busy": false,
      "device": "cuda",
      "last_error": "runtime not configured",
      "capabilities": [
        "line_performance",
        "emotion_audio",
        "emotion_text",
        "emotion_vector",
        "multi_take"
      ]
    }
  ]
}
```

Runtime state 以 Python 后端为准。前端只展示状态并提交请求。

### Runtime Coordinator Contract

所有 model adapter 在加载或运行 GPU 模型前，都必须使用共享的 `RuntimeCoordinator`。

行为：

- 默认 GPU slot count 是 `1`。
- disabled backend 不能被调度。
- busy backend 或已占用 GPU lease 应根据 job policy 排队或拒绝。
- 从一个 backend 切换到另一个 backend 前，必须先卸载当前 backend。
- unload 应执行 adapter cleanup、Python garbage collection，并在可用时清理 CUDA cache。
- 失败必须释放 lease 并更新 `last_error`。

## Legacy Gradio Compatibility Contract

The legacy Gradio route may later call the same app services so development and regression workflows stay useful. If integrated, it should:

- Load saved voices with `list_voices`.
- Pass the selected voice `audio_path` as `reference_wav_path_input`.
- Create a generation record before calling the generation backend.
- Mark the generation as succeeded or failed after the backend returns.
- Copy successful output audio into `data/app/generations/`.

## Electron Contract

Electron should:

- Start the React AppShell renderer.
- Send AppShell status to the renderer through IPC.
- Start and stop `voxcpm_app.backend_server` in default AppShell mode.
- Keep the original Gradio route separate from AppShell mode.

Electron should not directly mutate SQLite app data in the first implementation.

Renderer IPC additions:

- `selectAudioFile()`
- `generateAudio(payload)`
- `mediaUrl(projectRelativePath)`

## Local App Service CLI

Electron calls the Python app layer through a JSON CLI boundary:

```text
python -m voxcpm_app.service_cli <action> --project-root <project-root>
```

Input is a JSON object on stdin. Output is a JSON object on stdout.

Initial actions:

- `list-voices`
- `create-voice`
- `update-voice`
- `delete-voice`
- `list-generations`
- `create-generation`
- `mark-generation-running`
- `mark-generation-succeeded`
- `mark-generation-failed`
- `delete-generation`
