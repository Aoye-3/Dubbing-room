import type { IndexTTS25Payload } from "../shared/types";

type WithoutTakeCount<T> = T extends unknown ? Omit<T, "take_count"> : never;

export type IndexTTS25Form = WithoutTakeCount<IndexTTS25Payload>;
export type IndexTTS25ValidationContext = { textEmotionEnabled: boolean };

export type IndexTTS25JobRequest = {
  backend_id: "indextts2";
  model_id: "IndexTTS-2.5";
  mode: "line_performance";
  input_text: string;
  voice_id: string | null;
  params: IndexTTS25Payload & Record<string, unknown>;
};

const supportedLanguages = ["ZH", "EN", "JA", "ES", "AR"] as const;
const emotionVectorFields = ["happy", "angry", "sad", "afraid", "disgusted", "melancholic", "surprised", "calm"] as const;

export function buildIndexTTS25JobRequest(form: IndexTTS25Form, takeCount: number, context: IndexTTS25ValidationContext): IndexTTS25JobRequest {
  validateForm(form, context);
  return {
    backend_id: "indextts2",
    model_id: "IndexTTS-2.5",
    mode: "line_performance",
    input_text: form.text,
    voice_id: form.speaker.kind === "saved_voice" ? form.speaker.voice_id : null,
    params: { ...form, take_count: clampTakeCount(takeCount) } as IndexTTS25Payload & Record<string, unknown>,
  };
}

function validateForm(form: IndexTTS25Form, context: IndexTTS25ValidationContext): void {
  const candidate = form as IndexTTS25Form & Record<string, unknown>;
  if (!supportedLanguages.includes(candidate.language as (typeof supportedLanguages)[number])) {
    throw new Error("language must be one of ZH, EN, JA, ES, AR");
  }
  if (!Number.isFinite(candidate.duration_factor) || candidate.duration_factor < 0.5 || candidate.duration_factor > 2) {
    throw new Error("duration_factor must be between 0.5 and 2.0");
  }

  const hasAudio = candidate.emotion_audio !== undefined;
  const hasVector = candidate.emo_vector !== undefined;
  const hasText = candidate.emo_text !== undefined;
  if (candidate.emotion_mode === "same_voice") {
    if (hasAudio || hasVector || hasText) throw new Error("same_voice does not accept emotion prompt fields");
    return;
  }
  if (candidate.emotion_mode === "audio_prompt") {
    const audio = candidate.emotion_audio;
    if (!audio || typeof audio !== "object" || (audio as { kind?: unknown }).kind !== "upload" || !(audio as { path?: unknown }).path) {
      throw new Error("emotion audio is required");
    }
    if (hasVector || hasText) throw new Error("audio_prompt does not accept vector or text emotion fields");
    return;
  }
  if (candidate.emotion_mode === "vector") {
    const vector = candidate.emo_vector as Record<string, unknown> | undefined;
    if (!vector) throw new Error("emotion vector is required");
    if (hasAudio || hasText) throw new Error("vector does not accept audio or text emotion fields");
    const total = emotionVectorFields.reduce((sum, field) => {
      const value = vector[field];
      if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) {
        throw new Error(`emotion vector ${field} must be between 0 and 1`);
      }
      return sum + value;
    }, 0);
    if (total > 0.8000001) throw new Error("emotion vector total must not exceed 0.8");
    return;
  }
  if (candidate.emotion_mode === "text_prompt") {
    if (!context.textEmotionEnabled) throw new Error("text emotion is unavailable");
    if (typeof candidate.emo_text !== "string" || !candidate.emo_text.trim()) throw new Error("emotion text is required");
    if (hasAudio || hasVector) throw new Error("text_prompt does not accept audio or vector emotion fields");
    return;
  }
  throw new Error("unsupported emotion mode");
}

export function clampTakeCount(value: number): number {
  return Number.isFinite(value) ? Math.max(1, Math.min(5, Math.round(value))) : 3;
}
