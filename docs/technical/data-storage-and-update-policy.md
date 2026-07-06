# 数据存储体系与 Git 更新机制规划

## 目标

本文记录 VoxCPM-Box 当前的数据存储边界，并为后续通过 GitHub 拉取公开仓库更新提供设计约束。

核心原则：

- 用户数据不上传到公开项目仓库。
- Git 更新只更新仓库追踪的项目文件，不覆盖本地用户库、运行时缓存、模型权重和个人配置。
- 开发示例数据可以随仓库发布，但必须保持小、可公开、可替换。
- 当前项目在仓库目录内运行，但用户数据通过 `.gitignore` 与 Git 更新隔离。

## 当前开发进度快照

当前仓库已经进入 AppShell 产品层开发阶段：

- Electron React AppShell 已存在，入口为 `electron/main.js` 和 `electron/renderer/src/app/App.tsx`。
- 本地 Python App 后端已存在，Electron 通过 IPC 调用 `voxcpm_app.backend_server` 和 `voxcpm_app.service_cli`。
- Voice Library、Generation History、VoxCPM2 生成、IndexTTS2 运行时状态、job/take 基础结构已经落地。
- 现有路线文档记录：Phase 1/2 runtime/UI 已完成；Phase 3 job/take loop 已有基础实现，但真实模型 smoke 仍依赖项目本地 runtime/checkpoints。

本次只读检查 `data/app/app.sqlite3` 的实际状态：

```text
tables = assets, generation_jobs, generation_takes, generations, schema_version, voices
assets = 0
generation_jobs = 0
generation_takes = 0
generations = 9
voices = 0
schema_version = 1, 2, 3
```

## 当前存储体系

### 总体路径

App 数据路径由 `src/voxcpm_app/paths.py` 定义：

```text
data/app/app.sqlite3
data/app/voices/
data/app/generations/
data/app/tmp/
```

模型和运行时缓存主要在：

```text
data/runtimes/voxcpm2/hf-cache/
data/runtimes/indextts2/
third_party/index-tts/checkpoints/
```

### 提示词存储

当前没有单独的 Prompt Library。

提示词相关内容随生成记录存入 SQLite：

- `generations.input_text`：目标文本。
- `generations.control_instruction`：声音风格、语速、情绪等控制提示。
- `generations.prompt_text`：极致克隆模式下的参考音频转写。
- `generation_jobs.params_json`：异步任务参数，包含模型相关参数。
- `generation_takes.params_json`：单个 take 的参数。

结论：现在的提示词存储属于生成历史的一部分，不是独立可复用资产。后续如果要做“提示词模板/角色提示词/项目提示词”，应新增 app-layer 表或项目表，不应写入 `conf/`、`examples/` 或公开仓库文件。

建议后续目标：

```text
prompt_presets
  id
  scope                 app | project | role
  name
  prompt_text
  tags_json
  created_at
  updated_at
  deleted_at
```

### 媒体存储

当前媒体采用“SQLite 元数据 + 本地文件”的模式。

主要目录：

- `data/app/voices/`：保存可复用音色音频。
- `data/app/generations/`：保存生成输出音频。
- `data/app/tmp/`：保存上传引用、临时生成文件、worker 中间文件。

SQLite 中相关字段：

- `voices.audio_path`、`voices.audio_sha256`
- `generations.reference_audio_path`
- `generations.output_audio_path`
- `assets.path`、`assets.sha256`
- `generation_jobs.output_asset_id`
- `generation_takes.output_asset_id`

Electron 前端不直接读文件，使用 `mediaUrl(projectRelativePath)` 生成后端 `/media?path=...` URL。后端只应允许项目内相对路径，避免任意文件读取。

结论：`data/app/**` 是用户数据，不能上传公开仓库，Git 更新机制必须保留。

### 配置存储

当前配置分为三类。

仓库配置模板：

- `conf/voxcpm_v*/voxcpm_finetune_*.yaml`
- `package.json`
- `pyproject.toml`
- `vite.config.ts`
- `tsconfig.json`
- `third_party/index-tts/checkpoints/config.yaml`

本地运行时配置/缓存：

- `data/runtimes/voxcpm2/hf-cache/`
- `data/runtimes/indextts2/`
- `.local-ffmpeg/`
- `.venv/`
- `.npm-cache/`

前端轻量偏好：

- `window.localStorage["voxcpm-app-language"]` 只保存界面语言。

结论：`conf/` 当前应视为公开开发模板，不适合作为用户个人配置写入位置。后续若需要用户设置，应进入 SQLite 或 `data/app/config/`，并继续忽略。

建议后续目标：

```text
app_settings
  key
  value_json
  updated_at
```

或：

```text
data/app/config/settings.json
```

二选一即可，优先 SQLite，避免配置散落。

### 项目存储

当前“project”主要指当前仓库根目录：

- Electron 启动 Python 后端时传入 `--project-root`。
- 媒体路径以项目根为基准保存相对路径。
- Settings UI 目前展示 project/local paths，而不是用户项目实体。

当前没有独立的用户项目表，也没有 `projects/` 目录作为创作项目库。

结论：如果要做真正的“创作项目”，它应该是用户数据，不应上传公开仓库。建议放在 SQLite 和 `data/app/projects/` 下。

建议后续目标：

```text
projects
  id
  name
  description
  default_voice_id
  metadata_json
  created_at
  updated_at
  deleted_at

project_items
  id
  project_id
  kind                 script | scene | role | generation | asset
  ref_id
  order_index
  metadata_json
```

## 数据分类

### 可以上传公开仓库的数据

这些是产品源码、文档、模板或公开示例：

- `src/`
- `electron/`
- `scripts/`
- `conf/` 作为默认训练配置模板
- `examples/` 中小型、可公开、无个人信息的示例
- `assets/` 中品牌、截图、文档图片
- `docs/`
- `tests/`
- 根入口与工程配置：`app.py`、`lora_ft_webui.py`、`package*.json`、`pyproject.toml`、`uv.lock`、`README*.md`

### 不上传公开仓库的用户数据

这些必须保持本地：

- `data/app/`
- `data/app/app.sqlite3`
- `data/app/voices/`
- `data/app/generations/`
- `data/app/tmp/`
- 未来的 `data/app/projects/`
- 未来的 `data/app/config/`
- 用户自定义 prompt、角色、项目、历史、生成输出、上传参考音频

### 不上传公开仓库的运行时与缓存

这些不是用户创作数据，但也不应上传：

- `data/runtimes/`
- `data/model-cache/`
- `data/pytest-tmp/`
- `.pytest-tmp/`
- `.venv/`
- `node_modules/`
- `dist/`
- `.npm-cache/`
- `.local-ffmpeg/`
- `*.log`
- `third_party/index-tts/checkpoints/` 中的模型权重

### 需要补强忽略规则的产物

当前 `.gitignore` 已覆盖主要 App 数据和 runtime，但训练相关产物还应明确加入：

```text
lora/
checkpoints/
logs/
runs/
tensorboard/
*.ckpt
*.pth
*.pt
*.safetensors
```

补强时要注意：`third_party/index-tts/checkpoints/config.yaml` 和 `pinyin.vocab` 当前有保留规则，不应误删。

## GitHub 更新机制设计

### 更新目标

从公开 GitHub 仓库拉取源码、文档、模板、测试和产品 UI 更新，同时保持本地：

- 用户 SQLite 数据库不变。
- 用户媒体文件不变。
- 本地模型权重、运行时、虚拟环境、缓存不变。
- 用户个人配置不变。
- 当前未提交的用户代码改动不被自动覆盖。

### 机制边界

更新机制不应做这些事：

- 不把用户数据索引或同步到公开仓库。
- 不上传 `data/app/**`。
- 不用 `git reset --hard` 自动覆盖本地改动。
- 不删除 ignored 文件。
- 不在其它目录 clone/copy/worktree。
- 不把依赖、缓存、模型放到 C: 或系统临时目录。

### 推荐流程

1. Preflight 检查

```text
git status --porcelain
git remote -v
git branch --show-current
git check-ignore data/app/app.sqlite3 data/app/generations/example.wav data/runtimes/example
```

如果存在 tracked 文件的本地改动，默认停止并提示用户先提交、stash 或放弃。不要自动覆盖。

2. 数据保护检查

检查这些路径必须被忽略或不存在：

```text
data/app/
data/runtimes/
.venv/
node_modules/
.npm-cache/
.local-ffmpeg/
*.log
```

可选：在当前工作区内创建本地备份，例如：

```text
data/backups/app-YYYYMMDD-HHMMSS/
```

备份目录也必须忽略。

3. 拉取更新

推荐使用普通 Git 机制：

```text
git fetch origin
git merge --ff-only origin/<release-branch>
```

如果无法 fast-forward，则停止并让用户选择合并策略。更新器不应静默处理冲突。

4. 迁移与验证

更新完成后运行：

```text
.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_storage.py tests\test_voxcpm_app_service_cli.py --basetemp data\pytest-tmp
npm.cmd run typecheck
```

如果 schema 有变化，必须通过 additive migration 处理，不允许重建用户数据库。

5. 更新结果报告

报告内容应包含：

- 更新前后 commit。
- 被更新的 tracked 文件摘要。
- 用户数据路径保护检查结果。
- 数据库 migration 版本。
- 验证命令结果。

### Allowlist / Denylist

Git 更新天然只作用于 tracked 文件，但更新器仍应显式声明边界。

允许更新的典型路径：

```text
src/
electron/
scripts/
conf/
examples/
assets/
docs/
tests/
third_party/index-tts source files, excluding ignored checkpoints
*.py
*.md
package.json
package-lock.json
pyproject.toml
uv.lock
vite.config.ts
tsconfig.json
```

必须保留的本地路径：

```text
data/app/
data/runtimes/
data/model-cache/
data/pytest-tmp/
.venv/
node_modules/
.npm-cache/
.local-ffmpeg/
*.log
lora/
checkpoints/
logs/
runs/
tensorboard/
```

## 后续文档与实现任务

建议后续按这个顺序推进：

1. 补强 `.gitignore`：加入训练产物、用户项目数据、备份目录。
2. 设计 `app_settings` 或 `data/app/config/settings.json`，把用户配置从仓库模板中分离。
3. 设计 `projects` / `project_items`，把真正的创作项目纳入用户数据体系。
4. 设计 `prompt_presets`，把可复用提示词从 generation history 中提升为用户资产。
5. 实现更新器 preflight，只做检查和报告，先不自动 merge。
6. 实现 GitHub 更新按钮或 CLI，使用 fetch + ff-only merge，遇到本地 tracked 改动立即停止。
7. 为 migration 和 update preflight 增加测试。

## 结论

当前存储设计的方向是正确的：用户数据集中在 `data/app`，开发模板和公开示例留在仓库，运行时缓存和模型资产留在 ignored 路径。

下一步的重点不是改模型或 UI，而是把边界制度化：

- 明确用户数据表。
- 补齐 ignored 路径。
- 把用户配置和项目数据迁入 `data/app`。
- 让 GitHub 更新机制只更新 tracked 项目文件，并在任何可能覆盖用户改动时停止。
