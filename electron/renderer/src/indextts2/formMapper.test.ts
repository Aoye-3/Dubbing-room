import { describe, expect, it } from "vitest";
import { buildIndexTTS25JobRequest, type IndexTTS25Form } from "./formMapper";

const common = {
  text: "Hello",
  language: "EN" as const,
  speaker: { kind: "saved_voice" as const, voice_id: "voice-1" },
  emo_alpha: 0.7,
  duration_factor: 1.25,
  text_normalization: true,
  interval_silence: 200,
  max_text_tokens_per_segment: 120,
  top_p: 0.8,
  top_k: 30,
  temperature: 0.8,
  length_penalty: 0,
  num_beams: 3,
  repetition_penalty: 10,
  max_mel_tokens: 1500,
};

const sameVoiceForm: IndexTTS25Form = {
  ...common,
  emotion_mode: "same_voice",
  use_random: false,
};

const capability = { textEmotionEnabled: true };

describe("buildIndexTTS25JobRequest", () => {
  it.each(["ZH", "EN", "JA", "ES", "AR"] as const)("accepts the official %s language", (language) => {
    const request = buildIndexTTS25JobRequest({ ...sameVoiceForm, language }, 3, capability);
    expect(request.params.language).toBe(language);
    expect(request.params.take_count).toBe(3);
  });

  it("uses the same validated contract for a one-Take quick preview", () => {
    const request = buildIndexTTS25JobRequest(sameVoiceForm, 1, capability);
    expect(request).toEqual({
      backend_id: "indextts2",
      model_id: "IndexTTS-2.5",
      mode: "line_performance",
      input_text: "Hello",
      voice_id: "voice-1",
      params: { ...sameVoiceForm, take_count: 1 },
    });
    expect(request.params).not.toHaveProperty("do_sample");
    expect(request.params).not.toHaveProperty("precision");
    expect(request.params).not.toHaveProperty("use_qwen_emo");
    expect(request.params).not.toHaveProperty("use_cuda_kernel");
  });

  it.each([
    [{ ...sameVoiceForm, duration_factor: 0.49 }, "duration_factor must be between 0.5 and 2.0"],
    [{ ...sameVoiceForm, duration_factor: 2.01 }, "duration_factor must be between 0.5 and 2.0"],
    [{ ...sameVoiceForm, language: "FR" }, "language must be one of ZH, EN, JA, ES, AR"],
  ])("rejects an invalid line-performance value", (form, message) => {
    expect(() => buildIndexTTS25JobRequest(form as IndexTTS25Form, 1, capability)).toThrow(message);
  });

  it("requires audio only for audio-prompt emotion", () => {
    const form = { ...common, emotion_mode: "audio_prompt", use_random: false } as unknown as IndexTTS25Form;
    expect(() => buildIndexTTS25JobRequest(form, 1, capability)).toThrow("emotion audio is required");
  });

  it("rejects vector totals above 0.8", () => {
    const form: IndexTTS25Form = {
      ...common,
      emotion_mode: "vector",
      use_random: true,
      emo_vector: { happy: 0.5, angry: 0.4, sad: 0, afraid: 0, disgusted: 0, melancholic: 0, surprised: 0, calm: 0 },
    };
    expect(() => buildIndexTTS25JobRequest(form, 1, capability)).toThrow("emotion vector total must not exceed 0.8");
  });

  it("requires non-empty text emotion and an enabled capability", () => {
    const form: IndexTTS25Form = { ...common, emotion_mode: "text_prompt", use_random: false, emo_text: "tense" };
    expect(() => buildIndexTTS25JobRequest({ ...form, emo_text: "   " }, 1, capability)).toThrow("emotion text is required");
    expect(() => buildIndexTTS25JobRequest(form, 1, { textEmotionEnabled: false })).toThrow("text emotion is unavailable");
  });

  it("rejects emotion fields that belong to another mode", () => {
    const mixed = { ...sameVoiceForm, emo_text: "tense" } as unknown as IndexTTS25Form;
    expect(() => buildIndexTTS25JobRequest(mixed, 1, capability)).toThrow("same_voice does not accept emotion prompt fields");
  });
});
