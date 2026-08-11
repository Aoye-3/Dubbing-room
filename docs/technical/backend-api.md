# 后端与 API

## 当前后端入口

```text
src/voxcpm_app/backend_server.py
```

当前后端是 Python `ThreadingHTTPServer`，由 Electron main 进程转发请求。

## 当前路由

```text
GET  /health
GET  /runtime-backends
GET  /media?path=...
GET  /generation-jobs
GET  /generation-jobs/:job_id
GET  /generation-jobs/:job_id/takes
POST /app-service
POST /generate-audio
POST /indextts2/generate
POST /generation-jobs
POST /generation-jobs/:job_id/cancel
POST /generation-jobs/:job_id/retry
POST /generation-takes/:take_id/select
POST /runtime-backends/:backend_id/unload
```

`POST /runtime-backends/:backend_id/unload` 当前只返回兼容响应 `unloaded: false`，尚未执行真实模型卸载。

## 当前 app-service actions

通过 `src/voxcpm_app/service_cli.py` 的 `ACTIONS` 复用：

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
- `restore-generation`
- `update-generation-favorite`
- `purge-generations`
- `promote-generation-to-voice`

## 当前生成接口

### VoxCPM2

```text
POST /generate-audio
```

调用：

```text
GenerationService.generate_audio(payload)
```

返回：

```text
GenerationRecord
```

### IndexTTS2

```text
POST /indextts2/generate
```

调用：

```text
IndexTTS2Service.generate(payload)
```

返回：

```text
GenerationRecord
```

## 当前限制与延期接口

- `/generate-audio` 和 `/indextts2/generate` 仍同步等待模型完成；job API 是并行保留的产品入口。
- queue 只存在于当前 Python backend 进程，重启后不会恢复旧 queued/running 工作。
- queued job 可以取消；running job 只写入 `cancel requested`，不会强制中断模型或子进程。
- retry 会创建一个新 job，不会原地复用原 job id。
- 尚无 structured logs 查询接口。
- Electron 当前把非 2xx 响应压缩成普通 `Error(message)`；`code` 和 `details` 尚未保留为前端类型。
- runtime load/free 和真实 unload 尚未实现。
- 独立 Assets CRUD/import API、追加 take API 尚未实现；当前 assets 通过 job/take 和 Voice Library 服务间接管理。

延期接口：

```text
POST /runtime-backends/:backend_id/load
POST /runtime/free
POST /generation-jobs/:job_id/takes
GET  /assets
GET  /assets/:asset_id
POST /assets/import
POST /assets/:asset_id/save-as-voice
```

## Backend service boundary

目标服务划分：

```text
RuntimeService
JobService
AssetService
VoiceService
GenerationHistoryProjectionService
VoxCPM2BackendAdapter
IndexTTS2BackendAdapter
```

## 错误格式

当前统一错误：

```json
{
  "error": "human readable message",
  "type": "RuntimeMissingError",
  "code": "runtime_missing",
  "details": {}
}
```

常见 code：

- `validation_error`
- `runtime_missing`
- `checkpoints_missing`
- `runtime_busy`
- `worker_failed`
- `timeout`
- `output_missing`
- `media_not_found`

## 兼容策略

短期保留：

- `/generate-audio`
- `/indextts2/generate`
- `/app-service`

内部可逐步改为：

```text
sync route -> create job -> run immediately -> return legacy GenerationRecord
```

这样前端旧流程不变，新 job/take 能逐步上线。

## 验收

- 旧 API 不回退。
- 新 job API 可创建、查询、失败、成功。
- `/runtime-backends` 返回 VoxCPM2 和 IndexTTS2 的真实状态。
- 后端所有错误返回 JSON。
- Electron main 对超时和非 2xx 有清晰错误。

## Job/take API status (2026-08-07)

`generation-jobs` create/list/get/cancel/retry、`generation-jobs/:job_id/takes` 和 `generation-takes/:take_id/select` 已实现。Take 列表响应包含用于播放的 `output_asset`。IndexTTS2 queued job 支持 `params.take_count`，范围限制为 1-5，默认值为 3。

当前语义：

- queued cancel 将 job 标记为 `cancelled`，worker 取出后会跳过。
- running cancel 仅写入 `cancel requested`，不会中断正在执行的模型。
- retry 从旧 job 的 backend、mode、voice 和 params 创建新 job。
- 选择 failed take 会被拒绝；选择 succeeded take 会更新唯一 selected take 并投影到兼容 History。
- job/take 自动化覆盖使用 fake synthesizer/runner；真实模型验收仍未记录。

## Phase 4 history and voice-linkage API status (2026-07-06)

The AppShell still uses the compatibility `/app-service` route for local storage actions. Electron preload exposes these actions to the renderer through `window.voxcpmShell`, and `electron/renderer/src/shared/api/client.ts` wraps them.

New or expanded app-service actions:

```text
list-generations
delete-generation
restore-generation
update-generation-favorite
purge-generations
promote-generation-to-voice
```

`list-generations` payload:

```json
{
  "include_deleted": false,
  "deleted_only": false,
  "include_hidden": false
}
```

Default behavior returns normal History records only: not deleted and not promoted/hidden.

`delete-generation` is a soft delete used by "Move to Trash". It sets `status: "deleted"` and `deleted_at`.

`restore-generation` clears `deleted_at` and restores a best-effort status based on the existing output/error fields.

`update-generation-favorite` payload:

```json
{
  "id": "generation-id",
  "is_favorite": true
}
```

`purge-generations` payload:

```json
{
  "ids": ["generation-id"]
}
```

Permanent purge rejects records that are not already in Trash. Successful purge removes the SQLite row and the generation output file, but it must not remove copied voice files.

`promote-generation-to-voice` payload:

```json
{
  "generation_id": "generation-id",
  "display_name": "Generated Voice",
  "tags": ["generated"],
  "notes": ""
}
```

Response:

```json
{
  "voice": {},
  "generation": {}
}
```

The operation copies the generation output into `data/app/voices/`, creates a voice with `source_generation_id`, and updates the generation with `saved_voice_id`, `promoted_to_voice_at`, and `hidden_from_history_at`.

Electron-only export API:

```text
exportAudioFile({ project_relative_path, suggested_name })
```

This uses `dialog.showSaveDialog` and validates that `project_relative_path` resolves inside the current project before copying the file.
