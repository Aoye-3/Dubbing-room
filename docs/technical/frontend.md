# 前端架构

## 当前技术栈

- Electron。
- React。
- TypeScript。
- Vite。
- `lucide-react` icons。
- Vitest、jsdom、React Testing Library。

入口：

```text
electron/renderer/src/main.tsx
electron/renderer/src/styles.css
electron/renderer/src/vite-env.d.ts
```

## 当前页面

当前 `PageKey` 包括：

- `design`
- `clone`
- `ultimate`
- `indexTTS2`
- `loraTraining`
- `loraInference`
- `library`
- `history`
- `jobs`
- `updates`
- `settings`

## IndexTTS-2.5 Performance Desk 当前能力

当前页面定义在 `electron/renderer/src/indextts2/IndexTTS2Page.tsx`，`main.tsx` 只负责挂载 `App`。

`IndexTTS2Page` 负责表单状态和提交，`formMapper.ts` 是快速试听与多 Take 共用的唯一 payload 映射边界，`PerformanceDesk.tsx` 负责当前 job/take 状态和操作。

能力：

- 加载 runtime status。
- 文本输入。
- `ZH / EN / JA / ES / AR` 必选语言。
- `duration_factor` 0.5-2.0。
- speaker reference：
  - saved voice
  - uploaded audio
- emotion mode：
  - same voice
  - audio prompt
  - vector
  - text prompt
- `emo_alpha`。
- vector 模式条件显示 `use_random`。
- `interval_silence`。
- `max_text_tokens_per_segment`。
- text normalization、分句和受控 sampling 专家区；不显示无效的 `do_sample`。
- ZH Pinyin、EN CMU、JA Kana 的 `<source|pronunciation>` 标注插入；ES/AR 不显示未支持助手。
- 文本情感实验/显存敏感提示，以及 runtime capability 禁用。
- 参考音频最多使用前 15 秒的上游限制提示。
- 根据 runtime `configured` / `busy` 状态禁用生成。
- “快速试听”和“生成多 Take”都调用 job API；前者提交一个 take。
- 当前 job 的 bounded polling；terminal 状态后停止轮询，离页清理 timer。
- take 状态、播放、参数、warnings/errors、选择、导出、保存为 Voice Library 和取消。
- 选择成功 take 后可在 History 查看其 2.5 模型身份、语言、时长和 warnings。

仍保留全局 Jobs 页用于跨任务查看；Performance Desk 是当前创作任务的就地比较面。尚缺 structured logs 查询、原生 Electron IPC 集成测试和桌面 E2E。

## 当前目录结构

```text
electron/renderer/src/
  app/
    App.tsx
    AppShell.tsx
    navigation.tsx
    routes.tsx
  shared/
    api/
      client.ts
      errors.ts
    audio.ts
    components.tsx
    GenerationResultPanel.tsx
    useGenerationAudioExport.ts
    types.ts
  storage/
    VoiceLibraryPage.tsx
    HistoryPage.tsx
    EmptyState.tsx
  voxcpm/
    VoxCPMPage.tsx
  indextts2/
    IndexTTS2Page.tsx
    formMapper.ts
    PerformanceDesk.tsx
  jobs/
    JobListPage.tsx
  updates/
    UpdatePage.tsx
```

表单映射和 job desk 已按业务边界拆分；不要在同步兼容入口和 job 入口重新各自拼装 payload。

## 当前交互边界

### 通用状态

前端展示：

- backend enabled。
- backend configured。
- loaded。
- busy。
- device。
- last_error。
- queue depth。
- active job。

前端不做：

- 不判断 GPU 是否可并发。
- 不直接加载/卸载模型。
- 不绕过后端创建文件。

### IndexTTS2 表演台

当前布局：

- 左侧：台词和 speaker。
- 中间：情绪和参数。
- 右侧：job status、take comparison、output playback。

生成按钮状态：

- App backend not ready：disabled。
- runtime missing：disabled。
- backend busy：disabled or queue mode。
- speaker missing：disabled。
- text missing：disabled。
- emotion source invalid：disabled。

### 多 take UI

已支持：

- 每个 take 播放。
- 显示 take 参数摘要。
- 显示 status / error。
- 标记 selected take。
- 保存 selected take 为 voice。
- 导出任意成功 take。
- terminal job 停止轮询，action failure 显示结构化错误类别与消息。

## API 类型

当前共享类型在：

```text
electron/renderer/src/shared/types.ts
```

`vite-env.d.ts` 只声明 `window.voxcpmShell` bridge，并引用共享类型。

当前类型包括：

- `RuntimeBackendStatus`。
- `GenerationJob`。
- `GenerationTake`，内嵌可播放的 `output_asset` 摘要。
- `AppVoice` / `AppGeneration`。
- `GenerateAudioPayload` / `IndexTTS25Payload`（`IndexTTS2Payload` 仅作为 deprecated alias）。
- `IndexTTS2RuntimeProfile`。
- model identity 与 structured warning 类型。
- 安全更新相关类型。

job/take status 当前仍使用 `string`，尚未收紧为枚举联合类型；独立通用 `AudioAsset` 类型也尚未暴露。

## 验收

- `npm.cmd run typecheck` 通过。
- `npm.cmd run build` 通过。
- IndexTTS2 页面行为不回退。
- `main.tsx` 不再承载新增复杂面板。
- runtime missing / busy / failed 均有可读 UI。
- Jobs 页可轮询任务、取消 queued/running IndexTTS job、重试、播放/选择 take，并保存成功 take 为音色。
- `npm.cmd test` 的 renderer mapper、字段显隐、Settings 保存、bounded polling、take action、History metadata 与 error 分类测试通过。


## Phase 4 production result and History UI status (2026-07-06)

AppShell branding:

- The desktop shell product name is `Dubbing-room`.
- Window titles, renderer document titles, loading shell text, npm package name, and user-facing AppShell status text use `Dubbing-room`.
- `VoxCPM`, `VoxCPM2`, `voxcpm_app`, `voxcpmShell`, `VOXCPM_*` environment variables, log filenames, and model IDs remain model/backend integration names and should not be renamed as part of product branding.

Production result panels now share `electron/renderer/src/shared/GenerationResultPanel.tsx`.

`GenerationResultPanel` is intentionally a presentation component. It renders result metadata, playback, export and save controls, then calls callbacks supplied by the owning page. It must not import `apiClient`, call `exportAudioFile`, call `promoteGenerationToVoice`, or branch on module-specific `source_mode` values.

Export side effects are owned by `electron/renderer/src/shared/useGenerationAudioExport.ts`. `VoxCPMPage` and `IndexTTS2Page` each instantiate this hook with their own local generated record, so export messages and errors remain scoped to the current module page instance.

The panel displays:

- Source
- Description
- Audio playback
- File location
- Export action
- Save generated audio as a Voice Library entry

Module result isolation:

- `design`, `clone`, and `ultimate` still reuse `VoxCPMPage`, but routes pass distinct React `key` values so their local result state does not bleed across modes.
- `IndexTTS2Page` no longer keeps a separate synchronous-result panel as its primary flow. `PerformanceDesk` owns current job/take playback, selection, export, and save-as-voice actions; `/indextts2/generate` remains a backend compatibility route.
- `GenerateAudioPayload.source_mode` is written by the renderer as one of `voice-design`, `voice-cloning`, or `ultimate-cloning`.
- IndexTTS2 writes `source_mode: "indextts2-performance"` from the backend.

History page behavior:

- `HistoryPage` has internal `History` and `Trash` subviews.
- Normal History receives `generations` from `App.tsx`, which calls `listGenerations()` with default filtering.
- Trash loads its own data with `listGenerations({ deleted_only: true })`.
- Filters are local UI state: source, favorite/star state, and status.
- Star/unstar calls `updateGenerationFavorite`.
- Move to Trash calls `trashGeneration`, which maps to the soft-delete app-service action.
- Trash supports selecting the current filtered rows and permanently deleting only selected visible trashed records.

Voice promotion behavior:

- Save-generated-voice calls `promoteGenerationToVoice`, not raw `createVoice`.
- After successful promotion, the returned generation is hidden from normal History by the backend.
- The voice library owns its copied audio file, so History purge does not affect promoted voices.

Export behavior:

- `GenerationResultPanel` triggers the `onExportAudio` callback supplied by its page/container.
- `VoxCPMPage` and `IndexTTS2Page` use `useGenerationAudioExport` to call `exportAudioFile`.
- History rows call `exportAudioFile` directly from `HistoryPage`.
- Export is implemented in Electron main because it requires a native save dialog and filesystem copy.
- The renderer passes only project-relative audio paths.

Result panel boundary rules:

- Shared UI is allowed: source, description, playback, file path, export button, and save-as-voice controls.
- Shared business logic is not allowed in the panel: generation, promotion-to-voice, export implementation, reference selection, and module-specific validation stay in the owning page.
- Future modules that need different result actions should pass different callbacks or action slots before adding conditional module branches to `GenerationResultPanel`.
