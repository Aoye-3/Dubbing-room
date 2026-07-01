# Agent 协作与开发规则

## 最高优先级规则

- 只在当前仓库 `F:\.VoxCPM\VoxCPM` 内工作。
- 禁止使用 worktree。
- 禁止复制或 clone 项目到其他目录。
- 禁止把依赖、缓存、虚拟环境、模型权重、构建产物写到 C 盘。
- 不回退用户已有修改。
- 修改前确认当前分支和工作树状态。
- 对已有脏文件要区分是否与当前任务相关。

## 当前分支注意事项

最近一次双模型 AppShell 提交：

```text
e2421a8 feat: add dual-model indextts2 app shell
```

后续调研时曾看到工作树存在非本任务修改：

```text
.gitignore
package.json
package-lock.json
```

如果后续仍存在这些修改，除非用户明确要求，不要覆盖或格式化它们。

## 调研优先级

1. 使用 Codegraph 查询当前代码事实。
2. 对不在 Codegraph 输出中的文件再用 shell 只读查看。
3. 外部资料必须优先官方 README、官方 docs、论文或上游源码。
4. 对技术事实要给出文件路径和行号。

## 实现优先级

下一轮实现不应先直接安装模型，而应先保证显存互斥：

1. RuntimeCoordinator 接管 VoxCPM2 和 IndexTTS2。
2. 再接真实 IndexTTS2 runtime。
3. 再迁移 storage v2。
4. 再做 job queue 和多 take UI。

## 编码边界

### Runtime 相关

可改：

- `src/voxcpm_app/runtime.py`
- `src/voxcpm_app/generation_service.py`
- `src/voxcpm_app/indextts2_service.py`
- `src/voxcpm_app/backend_server.py`
- 相关测试

不要做：

- 不要在同一轮重写整个后端。
- 不要引入外部队列服务。
- 不要把真实模型权重提交进 Git。

### 前端相关

可改：

- `electron/renderer/src/main.tsx`
- `electron/renderer/src/vite-env.d.ts`
- `electron/main.js`
- `electron/preload.js`

目标：

- 后续拆分到 `electron/renderer/src/indextts2/`、`voxcpm/`、`jobs/`。

不要做：

- 不要继续无限扩写 `main.tsx`。
- 不要让前端决定 GPU safety。

### 存储相关

可改：

- `src/voxcpm_app/db.py`
- `src/voxcpm_app/repositories.py`
- `src/voxcpm_app/schemas.py`
- `src/voxcpm_app/generation_history.py`
- `src/voxcpm_app/audio_assets.py`

原则：

- additive migration。
- 旧 API shape 兼容。
- 不给 `generations.backend_id` 设置误导性默认值。

## 子代理使用建议

适合派子代理：

- 外部项目架构调研。
- 本地代码事实复核。
- 存储迁移影响分析。
- IndexTTS2 runtime/checkpoints 方案复核。

不适合派子代理：

- 当前需要立即执行的关键路径改动。
- 会产生重叠写集的实现任务。
- 需要凭本地用户环境做审批的安装任务。

## 验证要求

文档和代码修改后至少运行：

```bat
npm.cmd run typecheck
npm.cmd run build
node --check electron\main.js
node --check electron\preload.js
.venv\Scripts\python.exe -m pytest tests\test_voxcpm_app_storage.py tests\test_voxcpm_app_service_cli.py tests\test_voxcpm_app_generation_service.py tests\test_voxcpm_app_indextts2_service.py -q --basetemp data\pytest-tmp
```

如果只改文档，可以不运行完整测试，但需要说明未运行原因。

