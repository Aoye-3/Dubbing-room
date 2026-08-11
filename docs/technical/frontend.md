# 前端架构

## 当前技术栈

- Electron。
- React。
- TypeScript。
- Vite。
- `lucide-react` icons。

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

## IndexTTS2Page 当前能力

当前页面定义在 `electron/renderer/src/indextts2/IndexTTS2Page.tsx`，`main.tsx` 只负责挂载 `App`。

能力：

- 加载 runtime status。
- 文本输入。
- speaker reference：
  - saved voice
  - uploaded audio
- emotion mode：
  - same voice
  - audio prompt
  - vector
  - text prompt
- `emo_alpha`。
- `use_random`。
- `interval_silence`。
- `max_text_tokens_per_segment`。
- advanced sampling。
- 根据 runtime `configured` / `busy` 状态禁用生成。
- 同步生成后播放、导出和保存为 Voice Library 音色。
- 提交 1-5 个 take 的 queued job。

当前缺口：

- 多 take 比较目前位于独立 Jobs 页，还不是表演台内的并排对比面板。
- structured backend `code` / `details` 没有保留为 typed UI error。
- 没有 structured logs 或 warning 详情展示。
- 没有前端测试。

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
  jobs/
    JobListPage.tsx
  updates/
    UpdatePage.tsx
```

IndexTTS2 的细分表演控件和 take comparison 仍可在交互复杂度继续增长时拆分；当前不为单次使用提前增加组件层级。

## 目标交互

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

目标布局：

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

应支持：

- 每个 take 播放。
- 显示 take 参数摘要。
- 显示 status / error。
- 标记 selected take。
- 保存 selected take 为 voice。

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
- `GenerateAudioPayload` / `IndexTTS2Payload`。
- 安全更新相关类型。

job/take status 当前仍使用 `string`，尚未收紧为枚举联合类型；独立通用 `AudioAsset` 类型也尚未暴露。

## 验收

- `npm.cmd run typecheck` 通过。
- `npm.cmd run build` 通过。
- IndexTTS2 页面行为不回退。
- `main.tsx` 不再承载新增复杂面板。
- runtime missing / busy / failed 均有可读 UI。
- Jobs 页可轮询任务、取消 queued job、重试、播放/选择 take，并保存成功 take 为音色。


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
- `IndexTTS2Page` uses the same shared result panel and supports saving the latest generated output as a voice.
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
