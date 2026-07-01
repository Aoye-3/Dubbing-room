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
POST /app-service
POST /generate-audio
POST /indextts2/generate
```

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

## 当前问题

- 生成接口同步等待模型完成。
- 没有 queue API。
- 没有 job status API。
- 没有 cancel/retry。
- 没有 structured logs。
- VoxCPM2 runtime status 是静态对象，不是 adapter 状态。
- IndexTTS2 失败写入 generation，但前端不一定能很好区分配置失败、参数失败、runtime busy。

## 目标 API

### Runtime

```text
GET  /runtime-backends
POST /runtime-backends/:backend_id/unload
POST /runtime-backends/:backend_id/load
POST /runtime/free
```

### Jobs

```text
POST /generation-jobs
GET  /generation-jobs
GET  /generation-jobs/:job_id
POST /generation-jobs/:job_id/cancel
POST /generation-jobs/:job_id/retry
```

### Takes

```text
GET  /generation-jobs/:job_id/takes
POST /generation-takes/:take_id/select
POST /generation-jobs/:job_id/takes
```

### Assets

```text
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

建议统一错误：

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

