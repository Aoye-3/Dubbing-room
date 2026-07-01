/// <reference types="vite/client" />

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
} from "./shared/types";

declare global {
  interface Window {
    voxcpmShell?: {
      onStatus(callback: (payload: ShellStatus) => void): void;
      getShellState(): Promise<ShellState>;
      selectAudioFile(): Promise<SelectedAudioFile | null>;
      generateAudio(payload: GenerateAudioPayload): Promise<AppGeneration>;
      generateIndexTTS2(payload: IndexTTS2Payload): Promise<AppGeneration>;
      getRuntimeBackends(): Promise<AppListResponse<RuntimeBackendStatus>>;
      createGenerationJob(payload: {
        backend_id: string;
        model_id: string;
        mode: string;
        input_text: string;
        voice_id?: string | null;
        params?: Record<string, unknown>;
      }): Promise<GenerationJob>;
      listGenerationJobs(): Promise<AppListResponse<GenerationJob>>;
      getGenerationJob(payload: { id: string }): Promise<GenerationJob>;
      cancelGenerationJob(payload: { id: string }): Promise<GenerationJob>;
      retryGenerationJob(payload: { id: string }): Promise<GenerationJob>;
      listGenerationTakes(payload: { job_id: string }): Promise<AppListResponse<GenerationTake>>;
      selectGenerationTake(payload: { id: string }): Promise<GenerationTake>;
      mediaUrl(projectRelativePath: string): string;
      listVoices(payload?: { include_deleted?: boolean }): Promise<AppListResponse<AppVoice>>;
      createVoice(payload: {
        source_audio_path: string;
        display_name: string;
        tags?: string[];
        notes?: string;
        source?: string;
        duration_seconds?: number | null;
      }): Promise<AppVoice>;
      updateVoice(payload: { id: string; display_name: string; tags: string[]; notes: string }): Promise<AppVoice>;
      deleteVoice(payload: { id: string }): Promise<AppVoice>;
      listGenerations(payload?: { include_deleted?: boolean }): Promise<AppListResponse<AppGeneration>>;
      createGeneration(payload: {
        input_text: string;
        control_instruction?: string;
        voice_id?: string | null;
        reference_audio_path?: string | null;
        prompt_text?: string;
        cfg_value?: number;
        inference_timesteps?: number;
        normalize?: boolean;
        denoise?: boolean;
      }): Promise<AppGeneration>;
      markGenerationRunning(payload: { id: string }): Promise<AppGeneration>;
      markGenerationSucceeded(payload: {
        id: string;
        source_output_audio_path: string;
        sample_rate: number;
      }): Promise<AppGeneration>;
      markGenerationFailed(payload: { id: string; error_summary?: string }): Promise<AppGeneration>;
      deleteGeneration(payload: { id: string }): Promise<AppGeneration>;
    };
  }
}
