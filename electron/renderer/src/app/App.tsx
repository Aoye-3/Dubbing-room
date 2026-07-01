import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AudioWaveform,
  Download,
  FileAudio,
  History,
  Languages,
  Library,
  Mic2,
  MoreHorizontal,
  Play,
  RefreshCw,
  Save,
  Settings,
  SlidersHorizontal,
  Sparkles,
  Star,
  Upload,
  WandSparkles,
} from "lucide-react";
import { JobListPage } from "../jobs/JobListPage";
import { apiClient } from "../shared/api/client";
import { messages, type MessageKey } from "./i18n";
import { navItems } from "./navigation";
import { mediaUrl } from "../shared/audio";
import { LoadingPanel } from "../shared/components";
import { VoxCPMPage } from "../voxcpm/VoxCPMPage";
import { HistoryPage } from "../storage/HistoryPage";
import { VoiceLibraryPage } from "../storage/VoiceLibraryPage";
import type {
  AppDataState,
  AppGeneration,
  AppVoice,
  FeatureMode,
  GenerateAudioPayload,
  IndexTTS2EmotionMode,
  IndexTTS2Payload,
  LanguageCode,
  PageKey,
  ReferenceKind,
  RuntimeBackendStatus,
  SelectedAudioFile,
  ShellState,
  ShellStatus,
} from "../shared/types";

export function App() {
  const [activePage, setActivePage] = useState<PageKey>("design");
  const [language, setLanguage] = useState<LanguageCode>(() => {
    const saved = window.localStorage.getItem("voxcpm-app-language");
    return saved === "zh" || saved === "en" ? saved : "zh";
  });
  const [shellState, setShellState] = useState<ShellState | null>(null);
  const [status, setStatus] = useState<ShellStatus>({
    state: "starting",
    message: messages.zh.starting,
    detail: "",
  });
  const [voices, setVoices] = useState<AppVoice[]>([]);
  const [generations, setGenerations] = useState<AppGeneration[]>([]);
  const [appDataState, setAppDataState] = useState<AppDataState>("idle");
  const [appDataError, setAppDataError] = useState("");

  const t = useMemo(() => {
    return (key: MessageKey) => messages[language][key] ?? messages.en[key];
  }, [language]);

  useEffect(() => {
    window.localStorage.setItem("voxcpm-app-language", language);
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  }, [language]);

  useEffect(() => {
    apiClient.getShellState().then((state) => {
      if (!state) {
        return;
      }
      setShellState(state);
      setStatus(state.status);
    });
    apiClient.onStatus((payload) => setStatus(payload));
  }, []);

  const loadAppData = useCallback(async () => {

    setAppDataState("loading");
    setAppDataError("");
    try {
      const [voiceResult, generationResult] = await Promise.all([
        apiClient.listVoices(),
        apiClient.listGenerations(),
      ]);
      setVoices(voiceResult.items);
      setGenerations(generationResult.items);
      setAppDataState("ready");
    } catch (error) {
      setAppDataState("failed");
      setAppDataError(error instanceof Error ? error.message : String(error));
    }
  }, []);

  useEffect(() => {
    loadAppData();
  }, [loadAppData]);

  const activeNav = useMemo(() => navItems.find((item) => item.key === activePage), [activePage]);
  const appReady = status.state === "ready";

  return (
    <div className="app-shell">
      <aside className="rail" aria-label="Primary">
        <div className="brand-mark">
          <Sparkles size={24} strokeWidth={2.1} />
        </div>
        <nav className="rail-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            const label = t(item.labelKey);
            return (
              <button
                key={item.key}
                className={`rail-button ${activePage === item.key ? "active" : ""}`}
                title={label}
                aria-label={label}
                onClick={() => setActivePage(item.key)}
              >
                <Icon size={23} strokeWidth={2.05} />
              </button>
            );
          })}
        </nav>
        <div className="version">dev</div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">{t("appTitle")}</p>
            <h1>{activeNav ? t(activeNav.labelKey) : ""}</h1>
          </div>
          <div className="topbar-actions">
            <LanguageSwitch language={language} setLanguage={setLanguage} />
            <BackendPill status={status} t={t} />
          </div>
        </header>

        {activePage === "design" && (
          <VoxCPMPage
            mode={t("navDesign")}
            status={status}
            appReady={appReady}
            accent="design"
            modeKey="voice-design"
            description={t("designDescription")}
            voices={voices}
            reload={loadAppData}
            t={t}
          />
        )}
        {activePage === "clone" && (
          <VoxCPMPage
            mode={t("navClone")}
            status={status}
            appReady={appReady}
            accent="clone"
            modeKey="voice-cloning"
            description={t("cloneDescription")}
            voices={voices}
            reload={loadAppData}
            t={t}
          />
        )}
        {activePage === "ultimate" && (
          <VoxCPMPage
            mode={t("navUltimate")}
            status={status}
            appReady={appReady}
            accent="ultimate"
            modeKey="ultimate-cloning"
            description={t("ultimateDescription")}
            voices={voices}
            reload={loadAppData}
            t={t}
          />
        )}
        {activePage === "indexTTS2" && (
          <IndexTTS2Page
            appReady={appReady}
            status={status}
            voices={voices}
            reload={loadAppData}
            t={t}
          />
        )}
        {activePage === "loraTraining" && (
          <ReservedFeaturePage
            mode={t("navLoraTraining")}
            modeKey="lora-training"
            description={t("loraTrainingDescription")}
            t={t}
          />
        )}
        {activePage === "loraInference" && (
          <ReservedFeaturePage
            mode={t("navLoraInference")}
            modeKey="lora-inference"
            description={t("loraInferenceDescription")}
            t={t}
          />
        )}
        {activePage === "library" && (
          <VoiceLibraryPage
            voices={voices}
            appDataState={appDataState}
            appDataError={appDataError}
            reload={loadAppData}
            t={t}
          />
        )}
        {activePage === "history" && (
          <HistoryPage
            generations={generations}
            appDataState={appDataState}
            appDataError={appDataError}
            reload={loadAppData}
            t={t}
          />
        )}
        {activePage === "jobs" && (
          <JobListPage
            labels={{
              jobs: t("navJobs"),
              retry: t("retry"),
              cancel: t("cancel"),
              noJobs: t("noJobs"),
              takes: t("takes"),
            }}
          />
        )}
        {activePage === "settings" && (
          <SettingsPage
            status={status}
            shellState={shellState}
            language={language}
            setLanguage={setLanguage}
            t={t}
          />
        )}
      </main>
    </div>
  );
}

function LanguageSwitch({
  language,
  setLanguage,
}: {
  language: LanguageCode;
  setLanguage: (language: LanguageCode) => void;
}) {
  return (
    <div className="language-switch" aria-label="Interface language">
      <Languages size={17} />
      <button className={language === "en" ? "active" : ""} type="button" onClick={() => setLanguage("en")}>
        EN
      </button>
      <button className={language === "zh" ? "active" : ""} type="button" onClick={() => setLanguage("zh")}>
        中
      </button>
    </div>
  );
}

function BackendPill({ status, t }: { status: ShellStatus; t: (key: MessageKey) => string }) {
  return (
    <div className={`backend-pill ${status.state}`}>
      <span />
      <strong>{status.state === "ready" ? t("appReady") : status.message}</strong>
    </div>
  );
}

const emotionVectorFields = ["happy", "angry", "sad", "afraid", "disgusted", "melancholic", "surprised", "calm"] as const;

function IndexTTS2Page({
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
  const [generatedRecord, setGeneratedRecord] = useState<AppGeneration | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");
  const runtimeUnavailable = runtime ? !runtime.configured || runtime.busy : false;

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
        <button className="primary-action" disabled={!appReady || isGenerating || runtimeUnavailable} onClick={generate} type="button">
          <Sparkles size={18} />
          {isGenerating ? status.message : t("generate")}
        </button>
        <button className="ghost-action" disabled={!appReady || isGenerating || runtimeUnavailable} onClick={submitJob} type="button">
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

function ReservedFeaturePage({
  mode,
  modeKey,
  description,
  t,
}: {
  mode: string;
  modeKey: FeatureMode;
  description: string;
  t: (key: MessageKey) => string;
}) {
  return (
    <section className="generation-grid reserved">
      <div className="mode-panel">
        <div className="mode-header">
          <SlidersHorizontal size={20} />
          <span>{mode}</span>
        </div>
        <p className="mode-description">{description}</p>
        <div className="field-stack">
          <label>
            <span>{t("pretrainedModel")}</span>
            <input value="openbmb/VoxCPM2" readOnly />
          </label>
          <label>
            <span>{modeKey === "lora-training" ? t("trainingManifest") : t("loraCheckpoint")}</span>
            <input value={modeKey === "lora-training" ? "examples/train_data_example.jsonl" : "None"} readOnly />
          </label>
          <label>
            <span>{t("outputDirectory")}</span>
            <input value={modeKey === "lora-training" ? "lora/" : "data/app/generations/"} readOnly />
          </label>
        </div>
      </div>
      <div className="native-workbench reserved-workbench">
        <div className="adapter-card">
          <h2>{mode}</h2>
          <p>{description}</p>
        </div>
      </div>
    </section>
  );
}

function SettingsPage({
  status,
  shellState,
  language,
  setLanguage,
  t,
}: {
  status: ShellStatus;
  shellState: ShellState | null;
  language: LanguageCode;
  setLanguage: (language: LanguageCode) => void;
  t: (key: MessageKey) => string;
}) {
  return (
    <section className="settings-grid">
      <div className="settings-panel">
        <h2>{t("runtime")}</h2>
        <dl>
          <dt>{t("backend")}</dt>
          <dd>{status.state}</dd>
          <dt>{t("appMode")}</dt>
          <dd>{shellState?.appMode ?? "app-shell"}</dd>
          <dt>{t("port")}</dt>
          <dd>{shellState?.mainPort ?? 8818}</dd>
          <dt>{t("appBackend")}</dt>
          <dd>{shellState?.appBackendUrl ?? "http://127.0.0.1:8818"}</dd>
          <dt>{t("legacyBackend")}</dt>
          <dd>{shellState?.legacyBackendUrl ?? "http://127.0.0.1:8808"}</dd>
        </dl>
      </div>
      <div className="settings-panel">
        <h2>{t("interface")}</h2>
        <dl>
          <dt>{t("interfaceLanguage")}</dt>
          <dd>
            <LanguageSwitch language={language} setLanguage={setLanguage} />
          </dd>
          <dt>{t("language")}</dt>
          <dd>{language === "zh" ? t("chinese") : t("english")}</dd>
          <dt>{t("appMode")}</dt>
          <dd>{t("languageHint")}</dd>
        </dl>
      </div>
      <div className="settings-panel">
        <h2>{t("localPaths")}</h2>
        <dl>
          <dt>{t("project")}</dt>
          <dd>{shellState?.projectDir ?? "F:\\.VoxCPM\\VoxCPM"}</dd>
          <dt>{t("outputLog")}</dt>
          <dd>{shellState?.appBackendOutLogPath ?? "voxcpm_app_backend.out.log"}</dd>
          <dt>{t("errorLog")}</dt>
          <dd>{shellState?.appBackendErrLogPath ?? "voxcpm_app_backend.err.log"}</dd>
          <dt>{t("gradioRoute")}</dt>
          <dd>{t("gradioRouteValue")}</dd>
        </dl>
      </div>
    </section>
  );
}
