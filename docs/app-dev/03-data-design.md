# Data Design

## Storage Strategy

Use SQLite for structured metadata and local files for audio assets.

Default development paths:

```text
data/app/app.sqlite3
data/app/voices/
data/app/generations/
data/app/tmp/
```

Paths stored in SQLite should be relative to the project root where practical.

双模型方向保持一套通用存储后端，同时服务 VoxCPM2 和 IndexTTS2。两个模型可以有不同控制参数，但输入、输出、任务和可复用资产必须出现在同一个 app data system 中。

## Tables

### `voices`

Stores reusable reference voices.

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | UUID string |
| `display_name` | TEXT NOT NULL | User-facing name |
| `tags` | TEXT NOT NULL DEFAULT `[]` | JSON array of strings |
| `notes` | TEXT NOT NULL DEFAULT `` | User notes |
| `source` | TEXT NOT NULL DEFAULT `upload` | `upload`, `microphone`, `imported`, `unknown` |
| `audio_path` | TEXT NOT NULL | Relative path to stored audio |
| `audio_sha256` | TEXT NOT NULL | File checksum |
| `duration_seconds` | REAL | Nullable when unknown |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC |
| `updated_at` | TEXT NOT NULL | ISO 8601 UTC |
| `last_used_at` | TEXT | ISO 8601 UTC |
| `deleted_at` | TEXT | Soft delete timestamp |

### `generations`

Stores generation attempts and outputs.

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | UUID string |
| `input_text` | TEXT NOT NULL | Target text |
| `control_instruction` | TEXT NOT NULL DEFAULT `` | Control prompt |
| `voice_id` | TEXT | Nullable FK-like reference to `voices.id` |
| `reference_audio_path` | TEXT | Stored or uploaded reference path |
| `prompt_text` | TEXT NOT NULL DEFAULT `` | Ultimate cloning transcript |
| `cfg_value` | REAL NOT NULL | Generation parameter |
| `inference_timesteps` | INTEGER NOT NULL | Generation parameter |
| `normalize` | INTEGER NOT NULL | Boolean 0/1 |
| `denoise` | INTEGER NOT NULL | Boolean 0/1 |
| `output_audio_path` | TEXT | Relative path after success |
| `sample_rate` | INTEGER | Output sample rate |
| `status` | TEXT NOT NULL | See status enum |
| `error_summary` | TEXT NOT NULL DEFAULT `` | Short failure message |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC |
| `updated_at` | TEXT NOT NULL | ISO 8601 UTC |
| `deleted_at` | TEXT | Soft delete timestamp |

Generation status enum:

```text
pending
running
succeeded
failed
cancelled
deleted
```

## Dual-Model Storage Direction

当前 `voices` 和 `generations` 表仍是第一版实现。下一版 schema 应在不破坏旧记录的前提下增加通用存储概念。

### `assets`

保存应用拥有的媒体文件，不让媒体文件依附于某个模型专属历史。

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | UUID string |
| `kind` | TEXT NOT NULL | `voice`, `reference`, `generation_output`, `take_output`, `tmp` |
| `path` | TEXT NOT NULL | Project-relative media path |
| `sha256` | TEXT NOT NULL | File checksum |
| `mime_type` | TEXT | Optional detected media type |
| `duration_seconds` | REAL | Nullable when unknown |
| `sample_rate` | INTEGER | Nullable when unknown |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC |
| `deleted_at` | TEXT | Soft delete timestamp |

### `generation_jobs`

跟踪提交给模型后端的生成工作。

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | UUID string |
| `backend_id` | TEXT NOT NULL | `voxcpm2` or `indextts2` |
| `model_id` | TEXT NOT NULL | Concrete upstream model identifier |
| `mode` | TEXT NOT NULL | `voice_design`, `voice_clone`, `ultimate_clone`, `line_performance` |
| `status` | TEXT NOT NULL | `queued`, `running`, `succeeded`, `failed`, `cancelled`, `deleted` |
| `input_text` | TEXT NOT NULL | Target text or script line |
| `voice_id` | TEXT | Reusable speaker voice when applicable |
| `params_json` | TEXT NOT NULL | Model-specific request parameters as JSON |
| `output_asset_id` | TEXT | Primary output asset when succeeded |
| `error_summary` | TEXT NOT NULL DEFAULT `` | Short failure message |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC |
| `updated_at` | TEXT NOT NULL | ISO 8601 UTC |
| `deleted_at` | TEXT | Soft delete timestamp |

### `generation_takes`

保存同一台词或同一任务的多个表演版本。

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | UUID string |
| `job_id` | TEXT NOT NULL | Parent job |
| `backend_id` | TEXT NOT NULL | Model backend that produced the take |
| `take_index` | INTEGER NOT NULL | Stable display order |
| `label` | TEXT NOT NULL DEFAULT `` | Optional user-facing label |
| `params_json` | TEXT NOT NULL | Per-take performance parameters |
| `output_asset_id` | TEXT | Output audio asset |
| `is_selected` | INTEGER NOT NULL DEFAULT 0 | Chosen take flag |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC |

兼容阶段可以先在 `generations` 上添加字段：

- `backend_id`
- `model_id`
- `mode`
- `params_json`
- `output_asset_id`

没有这些字段的旧记录应解释为 VoxCPM2 generation rows。

## File Naming

Recommended voice file path:

```text
data/app/voices/{voice_id}{original_extension}
```

Recommended generation output path:

```text
data/app/generations/{generation_id}.wav
```

Temporary app files:

```text
data/app/tmp/{uuid}-{safe_filename}
```

## Deletion Policy

First implementation uses soft delete:

- Set `deleted_at`.
- Hide records with `deleted_at IS NOT NULL` from default lists.
- Do not immediately remove files.

Physical cleanup can be implemented later as a separate maintenance action.

## Migration Policy

Use numbered migrations or an explicit `schema_version` table.

Minimum required table:

```text
schema_version
  version INTEGER NOT NULL
  applied_at TEXT NOT NULL
```

