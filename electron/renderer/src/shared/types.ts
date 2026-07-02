export type PageKey =
  | "design"
  | "clone"
  | "ultimate"
  | "indexTTS2"
  | "loraTraining"
  | "loraInference"
  | "library"
  | "history"
  | "jobs"
  | "settings";

export type LanguageCode = "en" | "zh";
export type AppDataState = "idle" | "loading" | "ready" | "failed";
export type FeatureMode = "voice-design" | "voice-cloning" | "ultimate-cloning" | "lora-training" | "lora-inference";
export type ReferenceKind = "none" | "upload" | "saved_voice";

export type ShellStatus = {
  state: "starting" | "ready" | "failed" | "exited" | string;
  message: string;
  detail: string;
};

export type ShellState = {
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

export type AppVoice = {
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

export type AppGeneration = {
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

export type AppListResponse<T> = {
  items: T[];
};

export type SelectedAudioFile = {
  path: string;
  name: string;
};

export type GenerateAudioPayload = {
  input_text: string;
  control_instruction: string;
  prompt_text: string;
  cfg_value: number;
  inference_timesteps: number;
  min_len: number;
  max_len: number;
  normalize: boolean;
  denoise: boolean;
  retry_badcase: boolean;
  retry_badcase_max_times: number;
  retry_badcase_ratio_threshold: number;
  reference:
    | { kind: "none" }
    | { kind: "upload"; path: string }
    | { kind: "saved_voice"; voice_id: string };
};

export type RuntimeBackendStatus = {
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
  state?: string;
  details?: Record<string, unknown> | null;
};

export type GenerationJob = {
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

export type GenerationTake = {
  id: string;
  job_id: string;
  backend_id: string;
  take_index: number;
  label: string;
  status: string;
  params_json: string;
  params?: Record<string, unknown>;
  output_asset_id: string | null;
  output_asset: {
    id: string;
    path: string;
    mime_type: string;
    duration_seconds: number | null;
    sample_rate: number | null;
  } | null;
  legacy_generation_id: string | null;
  is_selected: boolean;
  error_summary: string;
  created_at: string;
  updated_at: string;
};

export type IndexTTS2EmotionMode = "same_voice" | "audio_prompt" | "vector" | "text_prompt";

export type IndexTTS2Payload = {
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
  use_fp16: boolean;
  use_cuda_kernel: boolean;
  use_deepspeed: boolean;
  use_accel: boolean;
  use_torch_compile: boolean;
  take_count?: number;
};
