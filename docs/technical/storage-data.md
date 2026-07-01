# 存储与数据模型

## 当前存储 v1

当前 SQLite 表：

```text
schema_version
voices
generations
```

当前本地文件目录：

```text
data/app/voices/
data/app/generations/
data/app/tmp/
```

## 当前能力

v1 可支持：

- Voice Library。
- Generation History。
- VoxCPM2 单输出生成。
- IndexTTS2 单 take 生成。
- 保存生成结果为 voice。
- 软删除 voices / generations。

v1 不适合：

- 通用资产管理。
- 多 take。
- 异步 job。
- job retry。
- selected take。
- 每个 take 的独立错误。
- 结构化模型参数查询。

## 兼容约束

不要破坏：

- `VoiceRecord` shape。
- `GenerationRecord` shape。
- `list-voices`。
- `list-generations`。
- Voice Library 页面。
- History 页面。

短期策略：

- 新增表。
- 旧表新增 nullable 兼容列。
- 旧 API 继续返回旧字段。
- 新数据镜像到旧 History 投影。

## 目标 assets 表

```text
assets
  id TEXT PRIMARY KEY
  kind TEXT NOT NULL
  path TEXT NOT NULL
  sha256 TEXT NOT NULL
  mime_type TEXT NOT NULL
  duration_seconds REAL
  sample_rate INTEGER
  source TEXT
  created_at TEXT NOT NULL
  deleted_at TEXT
```

建议 kind：

- `voice`
- `reference`
- `generation_output`
- `take_output`
- `uploaded`

## 目标 generation_jobs 表

```text
generation_jobs
  id TEXT PRIMARY KEY
  backend_id TEXT NOT NULL
  model_id TEXT NOT NULL
  mode TEXT NOT NULL
  status TEXT NOT NULL
  input_text TEXT NOT NULL
  voice_id TEXT
  params_json TEXT NOT NULL
  output_asset_id TEXT
  error_summary TEXT NOT NULL DEFAULT ''
  legacy_generation_id TEXT
  created_at TEXT NOT NULL
  updated_at TEXT NOT NULL
  deleted_at TEXT
```

状态：

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`
- `deleted`

## 目标 generation_takes 表

```text
generation_takes
  id TEXT PRIMARY KEY
  job_id TEXT NOT NULL
  backend_id TEXT NOT NULL
  take_index INTEGER NOT NULL
  label TEXT
  status TEXT NOT NULL
  params_json TEXT NOT NULL
  output_asset_id TEXT
  is_selected INTEGER NOT NULL DEFAULT 0
  error_summary TEXT NOT NULL DEFAULT ''
  created_at TEXT NOT NULL
  updated_at TEXT NOT NULL
```

## 旧表兼容列

建议给 `voices` 增加：

```text
asset_id TEXT
```

建议给 `generations` 增加：

```text
backend_id TEXT
model_id TEXT
mode TEXT
params_json TEXT
output_asset_id TEXT
job_id TEXT
selected_take_id TEXT
```

注意：

- 不要给 `generations.backend_id` 设置默认 `voxcpm2`。
- 旧记录读取时可以在应用层解释为 legacy VoxCPM2。
- IndexTTS2 当前也会写旧 `generations`，默认值会误标。

## 数据流

### VoxCPM2 生成

```text
create generation_job
run VoxCPM2
write tmp wav
create asset(kind=generation_output)
mark job succeeded
create/update legacy generation projection
```

### VoxCPM 输出保存为 voice

```text
generation output asset
  -> create asset(kind=voice)
  -> create voice row
  -> keep voices.audio_path for compatibility
```

### IndexTTS2 多 take

```text
create generation_job for one line
for each take:
  run IndexTTS2
  create asset(kind=take_output)
  create generation_take
user selects take:
  mark selected
  mirror selected take to legacy generations
```

## Migration 验收

- 空库初始化成功。
- 旧库迁移成功。
- 旧 Voice Library 不崩。
- 旧 History 不崩。
- 旧 `createVoice` 可继续工作。
- 新 asset/job/take repository 可读写。
- selected take 能投影到 legacy generation。

