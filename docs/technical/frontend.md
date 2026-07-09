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
- `settings`

## IndexTTS2Page 当前能力

当前页面直接定义在 `main.tsx`。

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
- 生成后播放输出。

当前缺口：

- 未根据 `runtime.configured` 禁用生成。
- 没有 job status。
- 没有 take comparison。
- 没有日志或 warning 展示。
- 没有前端测试。
- 页面和 helper 都在 `main.tsx`。

## 目标目录结构

```text
electron/renderer/src/
  app/
    App.tsx
    navigation.ts
    shell-state.ts
  shared/
    api/
    components/
    media.ts
    types.ts
  storage/
    VoiceLibraryPage.tsx
    HistoryPage.tsx
    AssetsPage.tsx
  voxcpm/
    VoxCPMStudioPage.tsx
    GenerationPanel.tsx
  indextts2/
    IndexTTS2Page.tsx
    LineEditorPanel.tsx
    SpeakerReferencePanel.tsx
    EmotionControlPanel.tsx
    AdvancedSamplingPanel.tsx
    TakeComparisonPanel.tsx
    RuntimeStatusCard.tsx
  jobs/
    JobQueuePage.tsx
    JobStatusBadge.tsx
    TakeCard.tsx
```

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

当前类型在：

```text
electron/renderer/src/vite-env.d.ts
```

下一步建议拆到：

```text
electron/renderer/src/shared/types.ts
electron/renderer/src/shared/api/types.ts
```

新增类型：

- `RuntimeBackendStatus`
- `GenerationJob`
- `GenerationTake`
- `AudioAsset`
- `BackendId`
- `JobStatus`
- `TakeStatus`

## 验收

- `npm.cmd run typecheck` 通过。
- `npm.cmd run build` 通过。
- IndexTTS2 页面行为不回退。
- `main.tsx` 不再承载新增复杂面板。
- runtime missing / busy / failed 均有可读 UI。


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
