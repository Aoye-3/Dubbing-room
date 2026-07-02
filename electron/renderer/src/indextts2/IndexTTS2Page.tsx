import { FileAudio, Library, Play, RefreshCw, SlidersHorizontal, Sparkles, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../shared/api/client";
import { mediaUrl } from "../shared/audio";
import { LoadingPanel } from "../shared/components";
import type { AppGeneration, AppVoice, IndexTTS2EmotionMode, IndexTTS2Payload, RuntimeBackendStatus, SelectedAudioFile, ShellStatus } from "../shared/types";
import type { MessageKey } from "../app/i18n";
const emotionVectorFields = ["happy", "angry", "sad", "afraid", "disgusted", "melancholic", "surprised", "calm"] as const;

export function IndexTTS2Page({
  appReady,
  status,
  voices,
  reload,
  t,
}: {
  appReady: boolean;
  status: ShellStatus;
  voices: AppVoice[];
  reload: () => Promise<void>;
  t: (key: MessageKey) => string;
}) {
  const [runtime, setRuntime] = useState<RuntimeBackendStatus | null>(null);
  const [text, setText] = useState("快躲起来！是他要来了！");
  const [speakerKind, setSpeakerKind] = useState<"upload" | "saved_voice">("saved_voice");
  const [selectedVoiceId, setSelectedVoiceId] = useState("");
  const [speakerFile, setSpeakerFile] = useState<SelectedAudioFile | null>(null);
  const [emotionMode, setEmotionMode] = useState<IndexTTS2EmotionMode>("same_voice");
  const [emotionFile, setEmotionFile] = useState<SelectedAudioFile | null>(null);
  const [emoText, setEmoText] = useState("");
  const [emoAlpha, setEmoAlpha] = useState(1);
  const [useRandom, setUseRandom] = useState(false);
  const [takeCount, setTakeCount] = useState(3);
  const [intervalSilence, setIntervalSilence] = useState(200);
  const [maxTextTokens, setMaxTextTokens] = useState(120);
  const [emotionVector, setEmotionVector] = useState<Record<(typeof emotionVectorFields)[number], number>>({
    happy: 0,
    angry: 0,
    sad: 0,
    afraid: 0,
    disgusted: 0,
    melancholic: 0,
    surprised: 0,
    calm: 0,
  });
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [doSample, setDoSample] = useState(true);
  const [topP, setTopP] = useState(0.8);
  const [topK, setTopK] = useState(30);
  const [temperature, setTemperature] = useState(0.8);
  const [lengthPenalty, setLengthPenalty] = useState(0);
  const [numBeams, setNumBeams] = useState(3);
  const [repetitionPenalty, setRepetitionPenalty] = useState(10);
  const [maxMelTokens, setMaxMelTokens] = useState(1500);
  const [useFp16, setUseFp16] = useState(false);
  const [useCudaKernel, setUseCudaKernel] = useState(false);
  const [useDeepspeed, setUseDeepspeed] = useState(false);
  const [useAccel, setUseAccel] = useState(false);
  const [useTorchCompile, setUseTorchCompile] = useState(false);
  const [generatedRecord, setGeneratedRecord] = useState<AppGeneration | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");
  const runtimeUnavailable = runtime ? !runtime.configured || runtime.busy : false;
  const emotionVectorTotal = emotionVectorFields.reduce((sum, field) => sum + emotionVector[field], 0);
  const vectorTooHigh = emotionMode === "vector" && emotionVectorTotal > 0.8;
  const missingEmotionAudio = emotionMode === "audio_prompt" && !emotionFile;

  const loadRuntime = useCallback(async () => {
    try {
      const result = await apiClient.getRuntimeBackends();
      setRuntime(result?.items.find((item) => item.backend_id === "indextts2") ?? null);
    } catch (runtimeError) {
      setRuntime({
        backend_id: "indextts2",
        display_name: "IndexTTS2",
        enabled: false,
        configured: false,
        loaded: false,
        busy: false,
        device: "unknown",
        last_error: runtimeError instanceof Error ? runtimeError.message : String(runtimeError),
        capabilities: [],
      });
    }
  }, []);

  useEffect(() => {
    loadRuntime();
  }, [loadRuntime]);

  useEffect(() => {
    if (!selectedVoiceId && voices.length > 0) {
      setSelectedVoiceId(voices[0].id);
    }
    if (voices.length === 0 && speakerKind === "saved_voice") {
      setSpeakerKind("upload");
    }
  }, [selectedVoiceId, speakerKind, voices]);

  useEffect(() => {
    if (emotionMode === "text_prompt" && emoAlpha === 1) {
      setEmoAlpha(0.6);
    }
  }, [emotionMode, emoAlpha]);

  const selectSpeaker = async () => {
    const selected = await apiClient.selectAudioFile();
    if (selected) {
      setSpeakerFile(selected);
      setSpeakerKind("upload");
    }
  };

  const selectEmotion = async () => {
    const selected = await apiClient.selectAudioFile();
    if (selected) {
      setEmotionFile(selected);
      setEmotionMode("audio_prompt");
    }
  };

  const generate = async () => {
    setError("");
    const speaker = buildIndexSpeakerPayload(speakerKind, selectedVoiceId, speakerFile);
    if (!speaker) {
      setError(t("missingReference"));
      return;
    }
    if (missingEmotionAudio) {
      setError(t("emotionReference"));
      return;
    }
    if (vectorTooHigh) {
      setError("emo_vector total must be 0.8 or less.");
      return;
    }
    const payload: IndexTTS2Payload = {
      text,
      speaker,
      emotion_mode: emotionMode,
      emo_alpha: emoAlpha,
      use_random: useRandom,
      interval_silence: intervalSilence,
      max_text_tokens_per_segment: maxTextTokens,
      do_sample: doSample,
      top_p: topP,
      top_k: topK,
      temperature,
      length_penalty: lengthPenalty,
      num_beams: numBeams,
      repetition_penalty: repetitionPenalty,
      max_mel_tokens: maxMelTokens,
      use_fp16: useFp16,
      use_cuda_kernel: useCudaKernel,
      use_deepspeed: useDeepspeed,
      use_accel: useAccel,
      use_torch_compile: useTorchCompile,
    };
    if (emotionMode === "audio_prompt" && emotionFile) {
      payload.emotion_audio = { kind: "upload", path: emotionFile.path };
    }
    if (emotionMode === "vector") {
      payload.emo_vector = emotionVector;
    }
    if (emotionMode === "text_prompt") {
      payload.use_emo_text = true;
      payload.emo_text = emoText;
    }

    setIsGenerating(true);
    try {
      const record = await apiClient.generateIndexTTS2(payload);
      if (record) {
        setGeneratedRecord(record);
      }
      await reload();
      await loadRuntime();
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : String(generateError));
    } finally {
      setIsGenerating(false);
    }
  };

  const submitJob = async () => {
    setError("");
    const speaker = buildIndexSpeakerPayload(speakerKind, selectedVoiceId, speakerFile);
    if (!speaker) {
      setError(t("missingReference"));
      return;
    }
    if (missingEmotionAudio) {
      setError(t("emotionReference"));
      return;
    }
    if (vectorTooHigh) {
      setError("emo_vector total must be 0.8 or less.");
      return;
    }
    const payload: IndexTTS2Payload = {
      text,
      speaker,
      emotion_mode: emotionMode,
      emo_alpha: emoAlpha,
      use_random: useRandom,
      interval_silence: intervalSilence,
      max_text_tokens_per_segment: maxTextTokens,
      do_sample: doSample,
      top_p: topP,
      top_k: topK,
      temperature,
      length_penalty: lengthPenalty,
      num_beams: numBeams,
      repetition_penalty: repetitionPenalty,
      max_mel_tokens: maxMelTokens,
      use_fp16: useFp16,
      use_cuda_kernel: useCudaKernel,
      use_deepspeed: useDeepspeed,
      use_accel: useAccel,
      use_torch_compile: useTorchCompile,
      take_count: clampTakeCount(takeCount),
    };
    if (emotionMode === "audio_prompt" && emotionFile) {
      payload.emotion_audio = { kind: "upload", path: emotionFile.path };
    }
    if (emotionMode === "vector") {
      payload.emo_vector = emotionVector;
    }
    if (emotionMode === "text_prompt") {
      payload.use_emo_text = true;
      payload.emo_text = emoText;
    }

    setIsGenerating(true);
    try {
      await apiClient.createGenerationJob({
        backend_id: "indextts2",
        model_id: "IndexTTS2",
        mode: "line_performance",
        input_text: text,
        voice_id: speaker.kind === "saved_voice" ? speaker.voice_id : null,
        params: payload as unknown as Record<string, unknown>,
      });
      await reload();
      await loadRuntime();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : String(submitError));
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <section className="indextts2-grid">
      <div className="mode-panel">
        <div className="mode-header">
          <Sparkles size={20} />
          <span>{t("navIndexTTS2")}</span>
        </div>
        <p className="mode-description">{t("indexTTS2Description")}</p>
        <div className={`runtime-card ${runtime?.configured ? "ready" : "failed"}`}>
          <strong>{t("runtimeStatus")}</strong>
          <span>{runtime ? `${runtime.display_name} / ${runtime.device}` : status.message}</span>
          <p>{runtime?.configured ? runtime.last_error || "configured" : runtime?.last_error || t("missingRuntime")}</p>
        </div>
        <button className="primary-action" disabled={!appReady || isGenerating || runtimeUnavailable || vectorTooHigh || missingEmotionAudio} onClick={generate} type="button">
          <Sparkles size={18} />
          {isGenerating ? status.message : t("generate")}
        </button>
        <button className="ghost-action" disabled={!appReady || isGenerating || runtimeUnavailable || vectorTooHigh || missingEmotionAudio} onClick={submitJob} type="button">
          <RefreshCw size={18} />
          {t("queueJob")}
        </button>
        <button className="ghost-action" disabled={!appReady} onClick={loadRuntime} type="button">
          <RefreshCw size={18} />
          {t("retry")}
        </button>
      </div>

      <div className="native-workbench indextts2-workbench">
        {!appReady && <LoadingPanel status={status} />}
        {appReady && (
          <>
            <div className="indextts2-column">
              <label>
                <span>{t("targetText")}</span>
                <textarea value={text} onChange={(event) => setText(event.target.value)} />
              </label>
              <div className="reference-panel">
                <span className="field-title">{t("speakerReference")}</span>
                <div className="segmented-control">
                  <button className={speakerKind === "saved_voice" ? "active" : ""} type="button" onClick={() => setSpeakerKind("saved_voice")}>
                    <Library size={15} />
                    {t("savedVoice")}
                  </button>
                  <button className={speakerKind === "upload" ? "active" : ""} type="button" onClick={() => setSpeakerKind("upload")}>
                    <Upload size={15} />
                    {t("uploadedAudio")}
                  </button>
                </div>
                {speakerKind === "saved_voice" && (
                  <select value={selectedVoiceId} onChange={(event) => setSelectedVoiceId(event.target.value)}>
                    {voices.length === 0 && <option value="">{t("noSavedVoices")}</option>}
                    {voices.map((voice) => (
                      <option key={voice.id} value={voice.id}>
                        {voice.display_name}
                      </option>
                    ))}
                  </select>
                )}
                {speakerKind === "upload" && (
                  <button className="ghost-action" type="button" onClick={selectSpeaker}>
                    <Upload size={17} />
                    {speakerFile ? speakerFile.name : t("selectAudio")}
                  </button>
                )}
              </div>
            </div>

            <div className="indextts2-column">
              <label>
                <span>{t("emotionMode")}</span>
                <select value={emotionMode} onChange={(event) => setEmotionMode(event.target.value as IndexTTS2EmotionMode)}>
                  <option value="same_voice">{t("sameVoice")}</option>
                  <option value="audio_prompt">{t("emotionAudio")}</option>
                  <option value="vector">{t("emotionVector")}</option>
                  <option value="text_prompt">{t("emotionText")}</option>
                </select>
              </label>
              {emotionMode === "audio_prompt" && (
                <button className="ghost-action" type="button" onClick={selectEmotion}>
                  <Upload size={17} />
                  {emotionFile ? emotionFile.name : t("emotionReference")}
                </button>
              )}
              {emotionMode === "text_prompt" && (
                <label>
                  <span>{t("emotionText")}</span>
                  <textarea value={emoText} onChange={(event) => setEmoText(event.target.value)} />
                </label>
              )}
              {emotionMode === "vector" && (
                <div className="emotion-vector-grid">
                  <p className={emotionVectorTotal > 0.8 ? "status-line error" : "status-line"}>
                    {`emo_vector total: ${emotionVectorTotal.toFixed(2)} / 0.80`}
                  </p>
                  {emotionVectorFields.map((field) => (
                    <label key={field}>
                      <span>{field}</span>
                      <input
                        max={1}
                        min={0}
                        step={0.05}
                        type="range"
                        value={emotionVector[field]}
                        onChange={(event) => setEmotionVector({ ...emotionVector, [field]: Number(event.target.value) })}
                      />
                      <strong>{emotionVector[field].toFixed(2)}</strong>
                    </label>
                  ))}
                </div>
              )}
              <label>
                <span>{`${t("emoAlpha")}: ${emoAlpha.toFixed(2)}`}</span>
                <input max={1} min={0} step={0.05} type="range" value={emoAlpha} onChange={(event) => setEmoAlpha(Number(event.target.value))} />
              </label>
              <label className="checkbox-row">
                <input checked={useRandom} type="checkbox" onChange={(event) => setUseRandom(event.target.checked)} />
                <span>{t("useRandom")}</span>
              </label>
              <p className="mode-description">{t("randomHint")}</p>
              <label>
                <span>{t("takes")}</span>
                <input min={1} max={5} step={1} type="number" value={takeCount} onChange={(event) => setTakeCount(clampTakeCount(Number(event.target.value)))} />
              </label>
              <label>
                <span>{t("intervalSilence")}</span>
                <input min={0} max={5000} step={50} type="number" value={intervalSilence} onChange={(event) => setIntervalSilence(Number(event.target.value))} />
              </label>
              <label>
                <span>{t("maxTextTokens")}</span>
                <input min={20} max={1000} step={10} type="number" value={maxTextTokens} onChange={(event) => setMaxTextTokens(Number(event.target.value))} />
              </label>
              <button className="ghost-action" type="button" onClick={() => setAdvancedOpen(!advancedOpen)}>
                <SlidersHorizontal size={17} />
                {t("advanced")}
              </button>
              {advancedOpen && (
                <div className="advanced-grid">
                  <label className="checkbox-row"><input checked={doSample} type="checkbox" onChange={(event) => setDoSample(event.target.checked)} /><span>do_sample</span></label>
                  <NumberField label="top_p" value={topP} setValue={setTopP} min={0} max={1} step={0.05} />
                  <NumberField label="top_k" value={topK} setValue={setTopK} min={0} max={200} step={1} />
                  <NumberField label="temperature" value={temperature} setValue={setTemperature} min={0.1} max={2} step={0.05} />
                  <NumberField label="length_penalty" value={lengthPenalty} setValue={setLengthPenalty} min={-5} max={5} step={0.1} />
                  <NumberField label="num_beams" value={numBeams} setValue={setNumBeams} min={1} max={20} step={1} />
                  <NumberField label="repetition_penalty" value={repetitionPenalty} setValue={setRepetitionPenalty} min={0.1} max={50} step={0.1} />
                  <NumberField label="max_mel_tokens" value={maxMelTokens} setValue={setMaxMelTokens} min={100} max={5000} step={100} />
                  <label className="checkbox-row"><input checked={useFp16} type="checkbox" onChange={(event) => setUseFp16(event.target.checked)} /><span>use_fp16</span></label>
                  <label className="checkbox-row"><input checked={useCudaKernel} type="checkbox" onChange={(event) => setUseCudaKernel(event.target.checked)} /><span>use_cuda_kernel</span></label>
                  <label className="checkbox-row"><input checked={useDeepspeed} type="checkbox" onChange={(event) => setUseDeepspeed(event.target.checked)} /><span>use_deepspeed</span></label>
                  <label className="checkbox-row"><input checked={useAccel} type="checkbox" onChange={(event) => setUseAccel(event.target.checked)} /><span>use_accel</span></label>
                  <label className="checkbox-row"><input checked={useTorchCompile} type="checkbox" onChange={(event) => setUseTorchCompile(event.target.checked)} /><span>use_torch_compile</span></label>
                </div>
              )}
            </div>

            <aside className="result-panel">
              <div className="result-header">
                <FileAudio size={20} />
                <h2>{t("generationOutput")}</h2>
              </div>
              {generatedRecord?.output_audio_path ? (
                <div className="audio-result">
                  <audio controls src={mediaUrl(generatedRecord.output_audio_path)} />
                  <dl className="adapter-summary">
                    <dt>{t("status")}</dt>
                    <dd>{generatedRecord.status}</dd>
                    <dt>{t("sampleRate")}</dt>
                    <dd>{generatedRecord.sample_rate ? `${generatedRecord.sample_rate} Hz` : "--"}</dd>
                  </dl>
                </div>
              ) : (
                <div className="audio-placeholder">
                  <Play size={22} />
                  <span>{generatedRecord?.status === "failed" ? generatedRecord.error_summary : t("noGeneration")}</span>
                </div>
              )}
              {error && <p className="status-line error">{error}</p>}
            </aside>
          </>
        )}
      </div>
    </section>
  );
}

function NumberField({
  label,
  value,
  setValue,
  min,
  max,
  step,
}: {
  label: string;
  value: number;
  setValue: (value: number) => void;
  min: number;
  max: number;
  step: number;
}) {
  return (
    <label>
      <span>{label}</span>
      <input min={min} max={max} step={step} type="number" value={value} onChange={(event) => setValue(Number(event.target.value))} />
    </label>
  );
}

function buildIndexSpeakerPayload(
  speakerKind: "upload" | "saved_voice",
  selectedVoiceId: string,
  speakerFile: SelectedAudioFile | null,
): IndexTTS2Payload["speaker"] | null {
  if (speakerKind === "upload" && speakerFile) {
    return { kind: "upload", path: speakerFile.path };
  }
  if (speakerKind === "saved_voice" && selectedVoiceId) {
    return { kind: "saved_voice", voice_id: selectedVoiceId };
  }
  return null;
}

function clampTakeCount(value: number): number {
  if (!Number.isFinite(value)) {
    return 3;
  }
  return Math.max(1, Math.min(5, Math.round(value)));
}
