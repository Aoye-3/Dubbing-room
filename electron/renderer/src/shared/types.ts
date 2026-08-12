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
  | "updates"
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
  source_generation_id: string | null;
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
  source_backend: string;
  source_mode: string;
  description: string;
  is_favorite: boolean;
  output_audio_path: string | null;
  sample_rate: number | null;
  status: string;
  error_summary: string;
  saved_voice_id: string | null;
  promoted_to_voice_at: string | null;
  hidden_from_history_at: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  model_id?: string | null;
  model_version?: string | null;
  upstream_commit?: string | null;
  warnings?: BackendWarning[];
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
  source_mode: "voice-design" | "voice-cloning" | "ultimate-cloning";
  description?: string;
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
  model_id?: string | null;
  model_version?: string | null;
  upstream_commit?: string | null;
  supported_languages?: IndexTTS25Language[] | null;
  effective_precision?: "bf16" | "fp32" | string | null;
  text_emotion_enabled?: boolean | null;
  warnings?: BackendWarning[] | null;
  paths?: Record<string, string> | null;
};

export type IndexTTS2RuntimeProfile = {
  precision: "auto" | "bf16" | "fp32";
  allow_text_emotion: boolean;
  use_cuda_kernel: boolean;
  use_deepspeed: boolean;
  use_accel: boolean;
  use_torch_compile: boolean;
};

export type IndexTTS2RuntimeProfileResponse = {
  profile: IndexTTS2RuntimeProfile;
  effective_precision: "bf16" | "fp32";
  warnings: string[];
  capability: Record<string, unknown>;
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
  model_version?: string | null;
  upstream_commit?: string | null;
  warnings?: BackendWarning[];
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
  model_id?: string | null;
  model_version?: string | null;
  upstream_commit?: string | null;
  warnings?: BackendWarning[];
};

export type IndexTTS2EmotionMode = "same_voice" | "audio_prompt" | "vector" | "text_prompt";
export type IndexTTS25Language = "ZH" | "EN" | "JA" | "ES" | "AR";
export type BackendWarning = { code: string; message: string };

type IndexTTS25CommonPayload = {
  text: string;
  language: IndexTTS25Language;
  speaker: { kind: "upload"; path: string } | { kind: "saved_voice"; voice_id: string };
  emo_alpha: number;
  duration_factor: number;
  text_normalization: boolean;
  interval_silence: number;
  max_text_tokens_per_segment: number;
  top_p: number;
  top_k: number;
  temperature: number;
  length_penalty: number;
  num_beams: number;
  repetition_penalty: number;
  max_mel_tokens: number;
  take_count?: number;
};

export type IndexTTS25EmotionVector = {
    happy: number;
    angry: number;
    sad: number;
    afraid: number;
    disgusted: number;
    melancholic: number;
    surprised: number;
    calm: number;
};

export type IndexTTS25EmotionPayload =
  | { emotion_mode: "same_voice"; use_random: false; emotion_audio?: never; emo_vector?: never; emo_text?: never }
  | { emotion_mode: "audio_prompt"; use_random: false; emotion_audio: { kind: "upload"; path: string }; emo_vector?: never; emo_text?: never }
  | { emotion_mode: "vector"; use_random: boolean; emo_vector: IndexTTS25EmotionVector; emotion_audio?: never; emo_text?: never }
  | { emotion_mode: "text_prompt"; use_random: false; emo_text: string; emotion_audio?: never; emo_vector?: never };

export type IndexTTS25Payload = IndexTTS25CommonPayload & IndexTTS25EmotionPayload;

/** @deprecated Use IndexTTS25Payload. */
export type IndexTTS2Payload = IndexTTS25Payload;

export type ProtectedPathCheck = {
  path: string;
  ignored: boolean;
  exists: boolean;
  classification: "user-data" | "local-runtime" | string;
};

export type UpdateStatus = {
  state: "blocked" | "updateAvailable" | "upToDate" | "succeeded" | "failed" | string;
  repositoryUrl: string;
  remoteUrl: string;
  currentBranch: string;
  targetBranch: string;
  currentCommit: string;
  upstreamCommit: string;
  ahead: number;
  behind: number;
  dirtyTrackedFiles: string[];
  protectedPaths: ProtectedPathCheck[];
  blockers: string[];
  log: string[];
};

export type UpdateActionResult = {
  ok: boolean;
  state: string;
  summary: string;
  status: UpdateStatus;
  log: string[];
  error: string;
};

export type UpdateRequest = {
  repositoryUrl: string;
  branch: string;
};
