/// <reference types="vite/client" />

type ShellStatus = {
  state: "starting" | "ready" | "failed" | "exited" | string;
  message: string;
  detail: string;
};

type ShellState = {
  appMode: "app-shell" | "legacy-webui-dev" | string;
  backendUrl: string;
  mainPort: number;
  legacyBackendUrl: string;
  appBackendUrl: string;
  projectDir: string;
  outLogPath: string;
  errLogPath: string;
  appBackendOutLogPath: string;
  appBackendErrLogPath: string;
  status: ShellStatus;
};

type AppVoice = {
  id: string;
  display_name: string;
  tags: string[];
  notes: string;
  source: string;
  audio_path: string;
  audio_sha256: string;
  duration_seconds: number | null;
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
  deleted_at: string | null;
};

type AppGeneration = {
  id: string;
  input_text: string;
  control_instruction: string;
  voice_id: string | null;
  reference_audio_path: string | null;
  prompt_text: string;
  cfg_value: number;
  inference_timesteps: number;
  normalize: boolean;
  denoise: boolean;
  output_audio_path: string | null;
  sample_rate: number | null;
  status: string;
  error_summary: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
};

type AppListResponse<T> = {
  items: T[];
};

type SelectedAudioFile = {
  path: string;
  name: string;
};

type GenerateAudioPayload = {
  input_text: string;
  control_instruction: string;
  prompt_text: string;
  cfg_value: number;
  inference_timesteps: number;
  normalize: boolean;
  denoise: boolean;
  reference:
    | { kind: "none" }
    | { kind: "upload"; path: string }
    | { kind: "saved_voice"; voice_id: string };
};

type RuntimeBackendStatus = {
  backend_id: string;
  display_name: string;
  enabled: boolean;
  configured: boolean;
  loaded: boolean;
  busy: boolean;
  device: string;
  last_error: string;
  capabilities: string[];
  active_job_id?: string | null;
  started_at?: string | null;
};

type GenerationJob = {
  id: string;
  backend_id: string;
  model_id: string;
  mode: string;
  status: string;
  input_text: string;
  voice_id: string | null;
  params_json: string;
  params?: Record<string, unknown>;
  output_asset_id: string | null;
  error_summary: string;
  legacy_generation_id: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
};

type GenerationTake = {
  id: string;
  job_id: string;
  backend_id: string;
  take_index: number;
  label: string;
  status: string;
  params_json: string;
  output_asset_id: string | null;
  is_selected: boolean;
  error_summary: string;
  created_at: string;
  updated_at: string;
};

type IndexTTS2EmotionMode = "same_voice" | "audio_prompt" | "vector" | "text_prompt";

type IndexTTS2Payload = {
  text: string;
  speaker: { kind: "upload"; path: string } | { kind: "saved_voice"; voice_id: string };
  emotion_mode: IndexTTS2EmotionMode;
  emotion_audio?: { kind: "upload"; path: string };
  emo_alpha: number;
  emo_vector?: {
    happy: number;
    angry: number;
    sad: number;
    afraid: number;
    disgusted: number;
    melancholic: number;
    surprised: number;
    calm: number;
  };
  use_emo_text?: boolean;
  emo_text?: string;
  use_random: boolean;
  interval_silence: number;
  max_text_tokens_per_segment: number;
  do_sample: boolean;
  top_p: number;
  top_k: number;
  temperature: number;
  length_penalty: number;
  num_beams: number;
  repetition_penalty: number;
  max_mel_tokens: number;
};

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
