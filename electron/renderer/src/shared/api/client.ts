import type {
  AppGeneration,
  AppListResponse,
  AppVoice,
  GenerateAudioPayload,
  GenerationJob,
  GenerationTake,
  IndexTTS2Payload,
  RuntimeBackendStatus,
  SelectedAudioFile,
  ShellState,
  ShellStatus,
} from "../types";

const emptyList = <T>(): AppListResponse<T> => ({ items: [] });

function shell() {
  return window.voxcpmShell;
}

export const apiClient = {
  onStatus(callback: (payload: ShellStatus) => void): void {
    shell()?.onStatus(callback);
  },

  getShellState(): Promise<ShellState | undefined> {
    return shell()?.getShellState() ?? Promise.resolve(undefined);
  },

  selectAudioFile(): Promise<SelectedAudioFile | null> {
    return shell()?.selectAudioFile() ?? Promise.resolve(null);
  },

  generateAudio(payload: GenerateAudioPayload): Promise<AppGeneration | undefined> {
    return shell()?.generateAudio(payload) ?? Promise.resolve(undefined);
  },

  generateIndexTTS2(payload: IndexTTS2Payload): Promise<AppGeneration | undefined> {
    return shell()?.generateIndexTTS2(payload) ?? Promise.resolve(undefined);
  },

  getRuntimeBackends(): Promise<AppListResponse<RuntimeBackendStatus>> {
    return shell()?.getRuntimeBackends() ?? Promise.resolve(emptyList<RuntimeBackendStatus>());
  },

  createGenerationJob(payload: {
    backend_id: string;
    model_id: string;
    mode: string;
    input_text: string;
    voice_id?: string | null;
    params?: Record<string, unknown>;
  }): Promise<GenerationJob | undefined> {
    return shell()?.createGenerationJob(payload) ?? Promise.resolve(undefined);
  },

  listGenerationJobs(): Promise<AppListResponse<GenerationJob>> {
    return shell()?.listGenerationJobs() ?? Promise.resolve(emptyList<GenerationJob>());
  },

  cancelGenerationJob(payload: { id: string }): Promise<GenerationJob | undefined> {
    return shell()?.cancelGenerationJob(payload) ?? Promise.resolve(undefined);
  },

  retryGenerationJob(payload: { id: string }): Promise<GenerationJob | undefined> {
    return shell()?.retryGenerationJob(payload) ?? Promise.resolve(undefined);
  },

  listGenerationTakes(payload: { job_id: string }): Promise<AppListResponse<GenerationTake>> {
    return shell()?.listGenerationTakes(payload) ?? Promise.resolve(emptyList<GenerationTake>());
  },

  mediaUrl(projectRelativePath: string): string {
    return shell()?.mediaUrl(projectRelativePath) ?? "";
  },

  listVoices(payload?: { include_deleted?: boolean }): Promise<AppListResponse<AppVoice>> {
    return shell()?.listVoices(payload) ?? Promise.resolve(emptyList<AppVoice>());
  },

  createVoice(payload: {
    source_audio_path: string;
    display_name: string;
    tags?: string[];
    notes?: string;
    source?: string;
    duration_seconds?: number | null;
  }): Promise<AppVoice | undefined> {
    return shell()?.createVoice(payload) ?? Promise.resolve(undefined);
  },

  listGenerations(payload?: { include_deleted?: boolean }): Promise<AppListResponse<AppGeneration>> {
    return shell()?.listGenerations(payload) ?? Promise.resolve(emptyList<AppGeneration>());
  },
};
