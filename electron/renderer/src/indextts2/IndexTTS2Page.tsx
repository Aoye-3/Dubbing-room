import { Library, RefreshCw, SlidersHorizontal, Sparkles, Upload } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { MessageKey } from "../app/i18n";
import { apiClient } from "../shared/api/client";
import { classifyBackendError } from "../shared/api/errors";
import { LoadingPanel } from "../shared/components";
import type { AppVoice, IndexTTS2EmotionMode, IndexTTS25Language, RuntimeBackendStatus, SelectedAudioFile, ShellStatus } from "../shared/types";
import { PerformanceDesk } from "./PerformanceDesk";
import { buildIndexTTS25JobRequest, clampTakeCount, type IndexTTS25Form } from "./formMapper";

const emotionFields = ["happy", "angry", "sad", "afraid", "disgusted", "melancholic", "surprised", "calm"] as const;
const annotationNames: Partial<Record<IndexTTS25Language, string>> = { ZH: "Pinyin", EN: "CMU", JA: "Kana" };
const annotationExamples: Partial<Record<IndexTTS25Language, string>> = { ZH: "<行|XING2>", EN: "<minute|M IH1 . N AH0 T>", JA: "<上手|じょうず>" };

export function IndexTTS2Page({ appReady, status, voices, reload, t }: {
  appReady: boolean; status: ShellStatus; voices: AppVoice[]; reload: () => Promise<void>; t: (key: MessageKey) => string;
}) {
  const [runtime, setRuntime] = useState<RuntimeBackendStatus | null>(null);
  const [text, setText] = useState("快躲起来！是他要来了！");
  const [language, setLanguage] = useState<IndexTTS25Language>("ZH");
  const [speakerKind, setSpeakerKind] = useState<"upload" | "saved_voice">("saved_voice");
  const [voiceId, setVoiceId] = useState("");
  const [speakerFile, setSpeakerFile] = useState<SelectedAudioFile | null>(null);
  const [emotionMode, setEmotionMode] = useState<IndexTTS2EmotionMode>("same_voice");
  const [emotionFile, setEmotionFile] = useState<SelectedAudioFile | null>(null);
  const [emotionText, setEmotionText] = useState("");
  const [emotionVector, setEmotionVector] = useState<Record<(typeof emotionFields)[number], number>>(Object.fromEntries(emotionFields.map((field) => [field, 0])) as never);
  const [emoAlpha, setEmoAlpha] = useState(1);
  const [durationFactor, setDurationFactor] = useState(1);
  const [takeCount, setTakeCount] = useState(3);
  const [textNormalization, setTextNormalization] = useState(true);
  const [useRandom, setUseRandom] = useState(false);
  const [intervalSilence, setIntervalSilence] = useState(200);
  const [maxTextTokens, setMaxTextTokens] = useState(120);
  const [topP, setTopP] = useState(0.8);
  const [topK, setTopK] = useState(30);
  const [temperature, setTemperature] = useState(0.8);
  const [lengthPenalty, setLengthPenalty] = useState(0);
  const [numBeams, setNumBeams] = useState(3);
  const [repetitionPenalty, setRepetitionPenalty] = useState(10);
  const [maxMelTokens, setMaxMelTokens] = useState(1500);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [annotationOpen, setAnnotationOpen] = useState(false);
  const [annotationSource, setAnnotationSource] = useState("");
  const [annotationPronunciation, setAnnotationPronunciation] = useState("");
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");

  const loadRuntime = useCallback(async () => {
    try {
      const result = await apiClient.getRuntimeBackends();
      setRuntime(result.items.find((item) => item.backend_id === "indextts2") ?? null);
    } catch (value) {
      const issue = classifyBackendError(value);
      setError(`${issue.category}: ${issue.message}`);
    }
  }, []);

  useEffect(() => { if (appReady) void loadRuntime(); }, [appReady, loadRuntime]);
  useEffect(() => {
    if (!voiceId && voices[0]) setVoiceId(voices[0].id);
    if (voices.length === 0) setSpeakerKind("upload");
  }, [voiceId, voices]);
  useEffect(() => { setAnnotationOpen(false); }, [language]);
  useEffect(() => {
    if (runtime?.text_emotion_enabled === false && emotionMode === "text_prompt") setEmotionMode("same_voice");
  }, [emotionMode, runtime?.text_emotion_enabled]);

  const vectorTotal = useMemo(() => emotionFields.reduce((sum, field) => sum + emotionVector[field], 0), [emotionVector]);
  const speaker = speakerKind === "upload" ? (speakerFile ? { kind: "upload" as const, path: speakerFile.path } : null) : (voiceId ? { kind: "saved_voice" as const, voice_id: voiceId } : null);
  const textEmotionEnabled = runtime?.text_emotion_enabled === true;
  const invalid = !text.trim()
    || !speaker
    || durationFactor < 0.5
    || durationFactor > 2
    || (emotionMode === "audio_prompt" && !emotionFile)
    || (emotionMode === "vector" && vectorTotal > 0.8)
    || (emotionMode === "text_prompt" && (!textEmotionEnabled || !emotionText.trim()));
  const unavailable = !runtime || !runtime.configured || runtime.busy;
  const annotationName = annotationNames[language];

  const selectAudio = async (kind: "speaker" | "emotion") => {
    const file = await apiClient.selectAudioFile();
    if (!file) return;
    if (kind === "speaker") { setSpeakerFile(file); setSpeakerKind("upload"); }
    else { setEmotionFile(file); setEmotionMode("audio_prompt"); }
  };

  const buildForm = (): IndexTTS25Form | null => {
    if (!speaker) return null;
    const common = {
      text, language, speaker, emotion_mode: emotionMode, emo_alpha: emoAlpha,
      duration_factor: durationFactor, text_normalization: textNormalization,
      interval_silence: intervalSilence,
      max_text_tokens_per_segment: maxTextTokens, top_p: topP, top_k: topK,
      temperature, length_penalty: lengthPenalty, num_beams: numBeams,
      repetition_penalty: repetitionPenalty, max_mel_tokens: maxMelTokens,
    };
    if (emotionMode === "audio_prompt" && emotionFile) return { ...common, emotion_mode: "audio_prompt", use_random: false, emotion_audio: { kind: "upload", path: emotionFile.path } };
    if (emotionMode === "vector") return { ...common, emotion_mode: "vector", use_random: useRandom, emo_vector: emotionVector };
    if (emotionMode === "text_prompt") return { ...common, emotion_mode: "text_prompt", use_random: false, emo_text: emotionText };
    return { ...common, emotion_mode: "same_voice", use_random: false };
  };

  const submit = async (count: number) => {
    const form = buildForm();
    if (!form) return;
    setError(""); setIsGenerating(true);
    try {
      const job = await apiClient.createGenerationJob(buildIndexTTS25JobRequest(form, count, { textEmotionEnabled }));
      if (job) setCurrentJobId(job.id);
      await reload();
      await loadRuntime();
    } catch (value) {
      const issue = classifyBackendError(value);
      setError(`${issue.category}: ${issue.message}`);
    } finally { setIsGenerating(false); }
  };

  return (
    <section className="indextts2-grid">
      <div className="mode-panel">
        <div className="mode-header"><Sparkles size={20} /><span>IndexTTS-2.5</span></div>
        <p className="mode-description">Multilingual performance generation. Long text is experimental and memory-sensitive.</p>
        <div className={`runtime-card ${runtime?.configured ? "ready" : "failed"}`}><strong>{t("runtimeStatus")}</strong><span>{runtime ? `${runtime.display_name} / ${runtime.device}` : status.message}</span><p>{runtime?.last_error || runtime?.effective_precision || "checking"}</p></div>
        <button className="primary-action" disabled={!appReady || isGenerating || unavailable || invalid} type="button" onClick={() => void submit(takeCount)}><Sparkles size={18} />Generate multiple Takes</button>
        <button className="ghost-action" disabled={!appReady || isGenerating || unavailable || invalid} type="button" onClick={() => void submit(1)}><RefreshCw size={18} />Quick preview</button>
        <button className="ghost-action" disabled={!appReady} type="button" onClick={() => void loadRuntime()}><RefreshCw size={18} />{t("retry")}</button>
        {error && <p className="status-line error">{error}</p>}
      </div>
      <div className="native-workbench indextts2-workbench">
        {!appReady ? <LoadingPanel status={status} /> : <>
          <div className="indextts2-column">
            <label><span>{t("targetText")}</span><textarea aria-label="targetText" value={text} onChange={(event) => setText(event.target.value)} /></label>
            <p className="mode-description">Experimental with long text; longer scripts and dense segmentation are VRAM-sensitive.</p>
            <label><span>Language</span><select aria-label="Language" value={language} onChange={(event) => setLanguage(event.target.value as IndexTTS25Language)}>{["ZH", "EN", "JA", "ES", "AR"].map((value) => <option key={value}>{value}</option>)}</select></label>
            {annotationName && <div className="annotation-helper"><button className="ghost-action" type="button" onClick={() => setAnnotationOpen(true)}>{annotationName} annotation helper</button>{annotationOpen && <div><p className="mode-description">Insert {annotationExamples[language]} using &lt;source|pronunciation&gt; syntax.</p><label><span>Source phrase</span><input aria-label="Source phrase" value={annotationSource} onChange={(event) => setAnnotationSource(event.target.value)} /></label><label><span>Pronunciation</span><input aria-label="Pronunciation" value={annotationPronunciation} onChange={(event) => setAnnotationPronunciation(event.target.value)} /></label><button className="ghost-action" disabled={!annotationSource.trim() || !annotationPronunciation.trim()} type="button" onClick={() => { const annotation = `<${annotationSource.trim()}|${annotationPronunciation.trim()}>`; setText((current) => `${current}${current && !/\s$/.test(current) ? " " : ""}${annotation}`); setAnnotationOpen(false); setAnnotationSource(""); setAnnotationPronunciation(""); }}>Insert annotation</button></div>}</div>}
            <div className="reference-panel"><span className="field-title">{t("speakerReference")}</span><p className="mode-description">Use a clean reference of about 15 seconds; longer audio may be truncated.</p><div className="segmented-control"><button className={speakerKind === "saved_voice" ? "active" : ""} type="button" onClick={() => setSpeakerKind("saved_voice")}><Library size={15} />{t("savedVoice")}</button><button className={speakerKind === "upload" ? "active" : ""} type="button" onClick={() => setSpeakerKind("upload")}><Upload size={15} />{t("uploadedAudio")}</button></div>{speakerKind === "saved_voice" ? <label><span>Speaker</span><select aria-label="Speaker" value={voiceId} onChange={(event) => setVoiceId(event.target.value)}>{voices.map((voice) => <option key={voice.id} value={voice.id}>{voice.display_name}</option>)}</select></label> : <button className="ghost-action" type="button" onClick={() => void selectAudio("speaker")}><Upload size={17} />{speakerFile?.name || t("selectAudio")}</button>}</div>
            <NumberField label="Duration factor" value={durationFactor} setValue={setDurationFactor} min={0.5} max={2} step={0.05} />
            <NumberField label="Take count" value={takeCount} setValue={(value) => setTakeCount(clampTakeCount(value))} min={1} max={5} step={1} />
          </div>
          <div className="indextts2-column">
            <label><span>{t("emotionMode")}</span><select aria-label={t("emotionMode")} value={emotionMode} onChange={(event) => setEmotionMode(event.target.value as IndexTTS2EmotionMode)}><option value="same_voice">{t("sameVoice")}</option><option value="audio_prompt">{t("emotionAudio")}</option><option value="vector">{t("emotionVector")}</option>{textEmotionEnabled && <option value="text_prompt">{t("emotionText")}</option>}</select></label>
            {emotionMode === "audio_prompt" && <button className="ghost-action" type="button" onClick={() => void selectAudio("emotion")}><Upload size={17} />{emotionFile?.name || t("emotionReference")}</button>}
            {emotionMode === "text_prompt" && <><label><span>{t("emotionText")}</span><textarea aria-label={t("emotionText")} value={emotionText} onChange={(event) => setEmotionText(event.target.value)} /></label><p className="status-line warning">Experimental and VRAM-sensitive: an 8 GB GPU may run out of memory, and this mode has no fallback.</p></>}
            {emotionMode === "vector" && <div className="emotion-vector-grid"><p className={vectorTotal > 0.8 ? "status-line error" : "status-line"}>{vectorTotal.toFixed(2)} / 0.80</p>{emotionFields.map((field) => <label key={field}><span>{field}</span><input type="range" min={0} max={1} step={0.05} value={emotionVector[field]} onChange={(event) => setEmotionVector({ ...emotionVector, [field]: Number(event.target.value) })} /></label>)}<label className="checkbox-row"><input aria-label="use_random" checked={useRandom} type="checkbox" onChange={(event) => setUseRandom(event.target.checked)} /><span>use_random</span></label></div>}
            <label><span>{`${t("emoAlpha")}: ${emoAlpha.toFixed(2)}`}</span><input type="range" min={0} max={1} step={0.05} value={emoAlpha} onChange={(event) => setEmoAlpha(Number(event.target.value))} /></label>
            <button className="ghost-action" type="button" onClick={() => setAdvancedOpen(!advancedOpen)}><SlidersHorizontal size={17} />{t("advanced")}</button>
            {advancedOpen && <div className="advanced-grid"><label className="checkbox-row"><input aria-label="text_normalization" checked={textNormalization} type="checkbox" onChange={(event) => setTextNormalization(event.target.checked)} /><span>text_normalization</span></label><NumberField label="interval_silence" value={intervalSilence} setValue={setIntervalSilence} min={0} max={5000} step={50} /><NumberField label="max_text_tokens_per_segment" value={maxTextTokens} setValue={setMaxTextTokens} min={20} max={1000} step={10} /><NumberField label="top_p" value={topP} setValue={setTopP} min={0} max={1} step={0.05} /><NumberField label="top_k" value={topK} setValue={setTopK} min={0} max={200} step={1} /><NumberField label="temperature" value={temperature} setValue={setTemperature} min={0.1} max={2} step={0.05} /><NumberField label="length_penalty" value={lengthPenalty} setValue={setLengthPenalty} min={-5} max={5} step={0.1} /><NumberField label="num_beams" value={numBeams} setValue={setNumBeams} min={1} max={20} step={1} /><NumberField label="repetition_penalty" value={repetitionPenalty} setValue={setRepetitionPenalty} min={0.1} max={50} step={0.1} /><NumberField label="max_mel_tokens" value={maxMelTokens} setValue={setMaxMelTokens} min={100} max={5000} step={100} /></div>}
          </div>
          <PerformanceDesk jobId={currentJobId} onHistoryChanged={reload} />
        </>}
      </div>
    </section>
  );
}

function NumberField({ label, value, setValue, min, max, step }: { label: string; value: number; setValue: (value: number) => void; min: number; max: number; step: number }) {
  return <label><span>{label}</span><input aria-label={label} type="number" value={value} min={min} max={max} step={step} onChange={(event) => setValue(Number(event.target.value))} /></label>;
}
