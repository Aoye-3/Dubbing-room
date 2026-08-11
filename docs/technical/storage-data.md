# 存储与数据模型

## 当前存储版本

当前 SQLite 表：

```text
schema_version
voices
generations
assets
generation_jobs
generation_takes
```

当前 schema version 为 v4。迁移采用 additive 方式：保留 `voices` / `generations` 兼容表，新增 job/take/asset 表和 History/Voice linkage 字段。

当前本地文件目录：

```text
data/app/voices/
data/app/generations/
data/app/tmp/
```

## 当前能力

- Voice Library。
- Generation History 收藏、回收站、恢复、永久清理和隐藏已提升记录。
- VoxCPM2 单输出同步生成。
- VoxCPM2 / IndexTTS2 queued job。
- IndexTTS2 多 take、每个 take 的独立状态/错误和 selected take History 投影。
- job cancel/retry 基础语义。
- 生成结果或成功 take 保存为 voice。
- soft-delete voices / generations。
- `params_json` 保存 job/take 参数快照。

当前限制：

- 还没有独立 Assets CRUD/import API；asset 由 job/take 服务间接创建和读取。
- queue 进程重启恢复、running job 硬取消和跨进程协调尚未实现。
- History 的 legacy projection 仍是用户界面兼容面，不是完全 asset-native 的查询模型。
- 没有通用音频去重和引用计数；永久删除仍依赖“voice 拥有独立复制文件”的安全边界。

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

## 当前 assets 表

```text
assets
  id TEXT PRIMARY KEY
  kind TEXT NOT NULL
  path TEXT NOT NULL
  sha256 TEXT NOT NULL
  mime_type TEXT NOT NULL
  duration_seconds REAL
  sample_rate INTEGER
  created_at TEXT NOT NULL
  deleted_at TEXT
```

建议 kind：

- `voice`
- `reference`
- `generation_output`
- `take_output`
- `uploaded`

## 当前 generation_jobs 表

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

## 当前 generation_takes 表

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
  legacy_generation_id TEXT
  is_selected INTEGER NOT NULL DEFAULT 0
  error_summary TEXT NOT NULL DEFAULT ''
  created_at TEXT NOT NULL
  updated_at TEXT NOT NULL
```

## 旧表兼容策略

- `VoiceRecord` 和 `GenerationRecord` 的既有字段保持可读。
- `generation_takes.legacy_generation_id` 连接 selected take 与兼容 History 投影。
- `voices.source_generation_id`、`generations.saved_voice_id`、`promoted_to_voice_at` 和 `hidden_from_history_at` 记录生成结果提升为音色的双向关联。
- `generations.source_backend` / `source_mode` 保存用户可理解的来源；旧记录使用安全默认值并按 legacy 数据处理。
- 当前没有把 `asset_id` 直接加入 `voices`，也没有把 job/take 外键直接加入 `generations`；不要在文档中把这些延期字段当作已实现 schema。

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

## Job/take storage status (2026-08-07)

Storage v2 引入的 `assets`、`generation_jobs` 和 `generation_takes` 继续在 v4 中使用。`generation_takes.legacy_generation_id` 连接当前 selected take 与兼容 History 投影。Failed take 留在 Jobs 详情中，不会投影到 History。成功 take 可通过既有 create-voice 流程以 `source: "take"` 保存到 Voice Library。

## Phase 4 history and voice-linkage storage status (2026-07-06)

Storage v4 keeps the legacy `voices` and `generations` tables as the user-facing compatibility surface, while adding explicit fields for source-aware history, trash, stars, and promotion into the voice library.

New `generations` columns:

```text
source_backend TEXT NOT NULL DEFAULT 'voxcpm2'
source_mode TEXT NOT NULL DEFAULT 'legacy'
description TEXT NOT NULL DEFAULT ''
is_favorite INTEGER NOT NULL DEFAULT 0
saved_voice_id TEXT
promoted_to_voice_at TEXT
hidden_from_history_at TEXT
```

New `voices` column:

```text
source_generation_id TEXT
```

History visibility rules:

- Normal History lists only records where `deleted_at is null` and `hidden_from_history_at is null`.
- Trash lists records where `deleted_at is not null`; it does not include records hidden because they were promoted to a voice.
- Promoting a generation to a voice sets `saved_voice_id`, `promoted_to_voice_at`, and `hidden_from_history_at` on the generation.
- Promoted generations are not deleted; they remain traceable through `voices.source_generation_id` and `generations.saved_voice_id`.
- Permanent purge is only valid for trashed generations. It deletes the generation row and its file under `data/app/generations/`, but does not delete any copied voice file under `data/app/voices/`.

Source mode values currently written by production modules:

```text
voice-design
voice-cloning
ultimate-cloning
indextts2-performance
```

Migration rule:

- Additive migrations continue to live in `initialize_database()` with `_add_column_if_missing`.
- New history columns must remain nullable or have safe defaults so old SQLite files continue to open.
- Any future asset-level deduplication must preserve the current safety invariant: deleting a history generation must never remove an audio file still owned by a voice.
