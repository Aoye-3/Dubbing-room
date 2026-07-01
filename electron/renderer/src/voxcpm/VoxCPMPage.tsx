import { FileAudio, Library, Play, RefreshCw, Save, SlidersHorizontal, Sparkles, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../shared/api/client";
import { mediaUrl } from "../shared/audio";
import { LoadingPanel } from "../shared/components";
import type { AppGeneration, AppVoice, FeatureMode, GenerateAudioPayload, ReferenceKind, RuntimeBackendStatus, SelectedAudioFile, ShellStatus } from "../shared/types";
import type { MessageKey } from "../app/i18n";
export function VoxCPMPage({
  mode,
  status,
  appReady,
  accent,
  modeKey,
  description,
  voices,
  reload,
  t,
}: {
  mode: string;
  status: ShellStatus;
  appReady: boolean;
  accent: string;
  modeKey: FeatureMode;
  description: string;
  voices: AppVoice[];
  reload: () => Promise<void>;
  t: (key: MessageKey) => string;
}) {
  const [inputText, setInputText] = useState("VoxCPM brings local voice generation into a reusable desktop workflow.");
  const [controlInstruction, setControlInstruction] = useState("A calm, natural voice with clear pacing.");
  const [promptText, setPromptText] = useState("");
  const [cfgValue, setCfgValue] = useState(2);
  const [inferenceTimesteps, setInferenceTimesteps] = useState(10);
  const [normalize, setNormalize] = useState(false);
  const [denoise, setDenoise] = useState(false);
  const [referenceKind, setReferenceKind] = useState<ReferenceKind>(modeKey === "voice-design" ? "none" : "saved_voice");
  const [selectedVoiceId, setSelectedVoiceId] = useState("");
  const [uploadedFile, setUploadedFile] = useState<SelectedAudioFile | null>(null);
  const [generatedRecord, setGeneratedRecord] = useState<AppGeneration | null>(null);
  const [generatedVoiceName, setGeneratedVoiceName] = useState(t("generatedVoiceName"));
  const [uploadVoiceName, setUploadVoiceName] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [runtime, setRuntime] = useState<RuntimeBackendStatus | null>(null);

  const supportsReference = modeKey !== "voice-design";
  const requiresReference = modeKey === "ultimate-cloning";
  const runtimeUnavailable = runtime ? !runtime.configured || runtime.busy : false;

  const loadRuntime = useCallback(async () => {
    try {
      const result = await apiClient.getRuntimeBackends();
      setRuntime(result?.items.find((item) => item.backend_id === "voxcpm2") ?? null);
    } catch (runtimeError) {
      setRuntime({
        backend_id: "voxcpm2",
        display_name: "VoxCPM2",
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
    if (modeKey === "voice-design") {
      setReferenceKind("none");
      return;
    }
    if (!selectedVoiceId && voices.length > 0) {
      setSelectedVoiceId(voices[0].id);
      setReferenceKind("saved_voice");
    }
    if (voices.length === 0 && referenceKind === "saved_voice") {
      setReferenceKind("upload");
    }
  }, [modeKey, referenceKind, selectedVoiceId, voices]);

  const selectAudio = async () => {
    const selected = await apiClient.selectAudioFile();
    if (selected) {
      setUploadedFile(selected);
      setReferenceKind("upload");
      setUploadVoiceName(selected.name.replace(/\.[^.]+$/, ""));
    }
  };

  const saveUploadedVoice = async () => {
    if (!uploadedFile || !uploadVoiceName.trim()) {
      return;
    }
    setIsSaving(true);
    setError("");
    try {
      await apiClient.createVoice({
        source_audio_path: uploadedFile.path,
        display_name: uploadVoiceName.trim(),
        source: "upload",
      });
      setMessage(t("saveSuccess"));
      await reload();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : String(saveError));
    } finally {
      setIsSaving(false);
    }
  };

  const generate = async () => {
    setMessage("");
    setError("");
    const reference = buildReferencePayload(referenceKind, selectedVoiceId, uploadedFile);
    if (supportsReference && requiresReference && reference.kind === "none") {
      setError(t("missingReference"));
      return;
    }
    if (supportsReference && modeKey === "voice-cloning" && reference.kind === "none") {
      setError(t("missingReference"));
      return;
    }

    setIsGenerating(true);
    try {
      const record = await apiClient.generateAudio({
        input_text: inputText,
        control_instruction: modeKey === "ultimate-cloning" && promptText.trim() ? "" : controlInstruction,
        prompt_text: modeKey === "ultimate-cloning" ? promptText : "",
        cfg_value: cfgValue,
        inference_timesteps: inferenceTimesteps,
        normalize,
        denoise,
        reference,
      });
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

  const saveGeneratedVoice = async () => {
    if (!generatedRecord?.output_audio_path || !generatedVoiceName.trim()) {
      return;
    }
    setIsSaving(true);
    setError("");
    try {
      await apiClient.createVoice({
        source_audio_path: generatedRecord.output_audio_path,
        display_name: generatedVoiceName.trim(),
        tags: ["generated"],
        source: "generated",
      });
      setMessage(t("saveSuccess"));
      await reload();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : String(saveError));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section className={`generation-grid ${accent}`}>
      <div className="mode-panel">
        <div className="mode-header">
          <SlidersHorizontal size={20} />
          <span>{mode}</span>
        </div>
        <p className="mode-description">{description}</p>
        <div className="quick-controls">
          <button className="primary-action" disabled={!appReady || isGenerating || runtimeUnavailable} onClick={generate} type="button">
            <Sparkles size={18} />
            {isGenerating ? status.message : t("generate")}
          </button>
          <button className="ghost-action" disabled={!appReady} onClick={() => Promise.all([reload(), loadRuntime()])} type="button">
            <RefreshCw size={18} />
            {t("retry")}
          </button>
        </div>
        {runtimeUnavailable && (
          <p className="status-line error">{runtime?.last_error || (runtime?.busy ? "VoxCPM2 runtime is busy." : t("missingRuntime"))}</p>
        )}
        <div className="field-stack">
          <label>
            <span>{t("model")}</span>
            <input value="openbmb/VoxCPM2" readOnly />
          </label>
          <label>
            <span>{t("cfgValue")}</span>
            <input min={0.1} max={10} step={0.1} type="number" value={cfgValue} onChange={(event) => setCfgValue(Number(event.target.value))} />
          </label>
          <label>
            <span>{t("steps")}</span>
            <input min={1} max={100} step={1} type="number" value={inferenceTimesteps} onChange={(event) => setInferenceTimesteps(Number(event.target.value))} />
          </label>
          <label className="checkbox-row">
            <input checked={normalize} type="checkbox" onChange={(event) => setNormalize(event.target.checked)} />
            <span>{t("normalize")}</span>
          </label>
          <label className="checkbox-row">
            <input checked={denoise} type="checkbox" onChange={(event) => setDenoise(event.target.checked)} />
            <span>{t("denoise")}</span>
          </label>
        </div>
      </div>

      <div className="native-workbench generation-workbench">
        {!appReady && <LoadingPanel status={status} />}
        {appReady && (
          <>
            <div className="prompt-workspace">
              <label>
                <span>{t("targetText")}</span>
                <textarea value={inputText} onChange={(event) => setInputText(event.target.value)} />
              </label>
              <label>
                <span>{t("controlInstruction")}</span>
                <textarea value={controlInstruction} onChange={(event) => setControlInstruction(event.target.value)} />
              </label>
              {modeKey === "ultimate-cloning" && (
                <label>
                  <span>{t("promptTranscript")}</span>
                  <textarea value={promptText} onChange={(event) => setPromptText(event.target.value)} />
                </label>
              )}
            </div>
            <aside className="result-panel">
              {supportsReference && (
                <ReferencePicker
                  voices={voices}
                  referenceKind={referenceKind}
                  selectedVoiceId={selectedVoiceId}
                  uploadedFile={uploadedFile}
                  uploadVoiceName={uploadVoiceName}
                  isSaving={isSaving}
                  setReferenceKind={setReferenceKind}
                  setSelectedVoiceId={setSelectedVoiceId}
                  setUploadVoiceName={setUploadVoiceName}
                  selectAudio={selectAudio}
                  saveUploadedVoice={saveUploadedVoice}
                  t={t}
                />
              )}
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
                  <div className="inline-save">
                    <input value={generatedVoiceName} onChange={(event) => setGeneratedVoiceName(event.target.value)} />
                    <button className="ghost-action" disabled={isSaving} onClick={saveGeneratedVoice} type="button">
                      <Save size={17} />
                      {t("saveGeneratedVoice")}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="audio-placeholder">
                  <Play size={22} />
                  <span>{generatedRecord?.status === "failed" ? generatedRecord.error_summary : t("noGeneration")}</span>
                </div>
              )}
              {message && <p className="status-line success">{message}</p>}
              {error && <p className="status-line error">{error}</p>}
            </aside>
          </>
        )}
      </div>
    </section>
  );
}

function ReferencePicker({
  voices,
  referenceKind,
  selectedVoiceId,
  uploadedFile,
  uploadVoiceName,
  isSaving,
  setReferenceKind,
  setSelectedVoiceId,
  setUploadVoiceName,
  selectAudio,
  saveUploadedVoice,
  t,
}: {
  voices: AppVoice[];
  referenceKind: ReferenceKind;
  selectedVoiceId: string;
  uploadedFile: SelectedAudioFile | null;
  uploadVoiceName: string;
  isSaving: boolean;
  setReferenceKind: (kind: ReferenceKind) => void;
  setSelectedVoiceId: (id: string) => void;
  setUploadVoiceName: (name: string) => void;
  selectAudio: () => void;
  saveUploadedVoice: () => void;
  t: (key: MessageKey) => string;
}) {
  return (
    <div className="reference-panel">
      <span className="field-title">{t("referenceSource")}</span>
      <div className="segmented-control">
        <button className={referenceKind === "upload" ? "active" : ""} type="button" onClick={() => setReferenceKind("upload")}>
          <Upload size={15} />
          {t("uploadedAudio")}
        </button>
        <button className={referenceKind === "saved_voice" ? "active" : ""} type="button" onClick={() => setReferenceKind("saved_voice")}>
          <Library size={15} />
          {t("savedVoice")}
        </button>
      </div>
      {referenceKind === "upload" && (
        <div className="reference-stack">
          <button className="ghost-action" type="button" onClick={selectAudio}>
            <Upload size={17} />
            {t("selectAudio")}
          </button>
          {uploadedFile && <p>{`${t("selectedAudio")}: ${uploadedFile.name}`}</p>}
          {uploadedFile && (
            <div className="inline-save">
              <input value={uploadVoiceName} onChange={(event) => setUploadVoiceName(event.target.value)} />
              <button className="ghost-action" disabled={isSaving} type="button" onClick={saveUploadedVoice}>
                <Save size={17} />
                {t("saveUploadedVoice")}
              </button>
            </div>
          )}
        </div>
      )}
      {referenceKind === "saved_voice" && (
        <select value={selectedVoiceId} onChange={(event) => setSelectedVoiceId(event.target.value)}>
          {voices.length === 0 && <option value="">{t("noSavedVoices")}</option>}
          {voices.map((voice) => (
            <option key={voice.id} value={voice.id}>
              {voice.display_name}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}

function buildReferencePayload(
  referenceKind: ReferenceKind,
  selectedVoiceId: string,
  uploadedFile: SelectedAudioFile | null,
): GenerateAudioPayload["reference"] {
  if (referenceKind === "upload" && uploadedFile) {
    return { kind: "upload", path: uploadedFile.path };
  }
  if (referenceKind === "saved_voice" && selectedVoiceId) {
    return { kind: "saved_voice", voice_id: selectedVoiceId };
  }
  return { kind: "none" };
}
