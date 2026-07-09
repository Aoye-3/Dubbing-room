import { HelpCircle, Library, RefreshCw, Save, SlidersHorizontal, Sparkles, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../shared/api/client";
import { GenerationResultPanel } from "../shared/GenerationResultPanel";
import { LoadingPanel } from "../shared/components";
import { useGenerationAudioExport } from "../shared/useGenerationAudioExport";
import type { AppGeneration, AppVoice, FeatureMode, GenerateAudioPayload, ReferenceKind, RuntimeBackendStatus, SelectedAudioFile, ShellStatus } from "../shared/types";
import type { MessageKey } from "../app/i18n";

const controlHints = {
  generate: "按当前文本、控制提示和参数生成一段新的语音。",
  retry: "重新加载应用数据和 VoxCPM2 运行状态。",
  model: "当前使用的本地生成模型，只读展示。",
  cfgValue: "控制提示对生成结果的影响强度；数值越高越贴近控制提示，但过高可能降低自然度。",
  steps: "扩散/推理迭代步数；步数越多通常更稳定，但生成耗时会增加。",
  minLen: "限制生成内容的最短 token 长度，用于避免输出过短。",
  maxLen: "限制生成内容的最长 token 长度，用于控制生成上限和显存占用。",
  normalize: "生成前清理和规范化输入文本，如数字、符号、Markdown 和换行。",
  denoise: "对参考音频做降噪处理，降低背景噪声对音色参考的影响；声音设计模式通常没有参考音频。",
  retryBadcase: "检测到异常或低质量片段时自动重试生成。",
  retryBadcaseMaxTimes: "badcase 自动重试的最大次数。",
  retryBadcaseRatioThreshold: "badcase 判定阈值；数值越低越容易触发重试。",
  targetText: "最终要朗读成语音的文本内容。",
  controlInstruction: "描述声音风格、语速、情绪和节奏等控制目标。",
  promptTranscript: "极致克隆模式下，填写参考音频对应的转写文本。",
  referenceSource: "选择生成时使用上传音频，还是使用声音库里保存的音色。",
  uploadedAudio: "使用本地音频文件作为参考音色。",
  savedVoice: "使用声音库中已经保存的音色作为参考。",
  selectAudio: "从本机选择一段参考音频。",
  uploadVoiceName: "保存上传参考音频时使用的声音名称。",
  saveUploadedVoice: "把当前上传的参考音频保存到声音库。",
  generatedVoiceName: "保存生成结果时使用的声音名称。",
  saveGeneratedVoice: "把当前生成的音频保存到声音库。",
};

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
  const [minLen, setMinLen] = useState(2);
  const [maxLen, setMaxLen] = useState(4096);
  const [normalize, setNormalize] = useState(false);
  const [denoise, setDenoise] = useState(false);
  const [retryBadcase, setRetryBadcase] = useState(true);
  const [retryBadcaseMaxTimes, setRetryBadcaseMaxTimes] = useState(3);
  const [retryBadcaseRatioThreshold, setRetryBadcaseRatioThreshold] = useState(6);
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
  const generationAudioExport = useGenerationAudioExport(generatedRecord, t);

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
    if (appReady) {
      loadRuntime();
    }
  }, [appReady, loadRuntime]);

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
    if (modeKey === "ultimate-cloning" && !promptText.trim()) {
      setError("prompt_text is required for ultimate cloning.");
      return;
    }

    setIsGenerating(true);
    try {
      const record = await apiClient.generateAudio({
        input_text: inputText,
        control_instruction: modeKey === "ultimate-cloning" ? "" : controlInstruction,
        prompt_text: modeKey === "ultimate-cloning" ? promptText : "",
        cfg_value: cfgValue,
        inference_timesteps: inferenceTimesteps,
        min_len: minLen,
        max_len: maxLen,
        normalize,
        denoise,
        retry_badcase: retryBadcase,
        retry_badcase_max_times: retryBadcaseMaxTimes,
        retry_badcase_ratio_threshold: retryBadcaseRatioThreshold,
        source_mode: modeKey as GenerateAudioPayload["source_mode"],
        description: modeKey === "ultimate-cloning" ? promptText : controlInstruction,
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
      const result = await apiClient.promoteGenerationToVoice({
        generation_id: generatedRecord.id,
        display_name: generatedVoiceName.trim(),
        tags: ["generated"],
      });
      if (result?.generation) {
        setGeneratedRecord(result.generation);
      }
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
            <HelpBadge text={controlHints.generate} focusable={false} />
          </button>
          <button className="ghost-action" disabled={!appReady} onClick={() => Promise.all([reload(), loadRuntime()])} type="button">
            <RefreshCw size={18} />
            {t("retry")}
            <HelpBadge text={controlHints.retry} focusable={false} />
          </button>
        </div>
        {runtimeUnavailable && (
          <p className="status-line error">{runtime?.last_error || (runtime?.busy ? "VoxCPM2 runtime is busy." : t("missingRuntime"))}</p>
        )}
        <div className="field-stack">
          <label>
            <FieldCaption hint={controlHints.model}>{t("model")}</FieldCaption>
            <input value="openbmb/VoxCPM2" readOnly />
          </label>
          <label>
            <FieldCaption hint={controlHints.cfgValue}>{t("cfgValue")}</FieldCaption>
            <input min={0.1} max={10} step={0.1} type="number" value={cfgValue} onChange={(event) => setCfgValue(Number(event.target.value))} />
          </label>
          <label>
            <FieldCaption hint={controlHints.steps}>{t("steps")}</FieldCaption>
            <input min={1} max={100} step={1} type="number" value={inferenceTimesteps} onChange={(event) => setInferenceTimesteps(Number(event.target.value))} />
          </label>
          <label>
            <FieldCaption hint={controlHints.minLen}>min_len</FieldCaption>
            <input min={0} max={4096} step={1} type="number" value={minLen} onChange={(event) => setMinLen(Number(event.target.value))} />
          </label>
          <label>
            <FieldCaption hint={controlHints.maxLen}>max_len</FieldCaption>
            <input min={1} max={8192} step={1} type="number" value={maxLen} onChange={(event) => setMaxLen(Number(event.target.value))} />
          </label>
          <label className="checkbox-row">
            <input checked={normalize} type="checkbox" onChange={(event) => setNormalize(event.target.checked)} />
            <span className="checkbox-label-text">{t("normalize")}</span>
            <HelpBadge text={controlHints.normalize} />
          </label>
          <label className="checkbox-row">
            <input checked={denoise} type="checkbox" onChange={(event) => setDenoise(event.target.checked)} />
            <span className="checkbox-label-text">{t("denoise")}</span>
            <HelpBadge text={controlHints.denoise} />
          </label>
          <label className="checkbox-row">
            <input checked={retryBadcase} type="checkbox" onChange={(event) => setRetryBadcase(event.target.checked)} />
            <span className="checkbox-label-text">retry_badcase</span>
            <HelpBadge text={controlHints.retryBadcase} />
          </label>
          <label>
            <FieldCaption hint={controlHints.retryBadcaseMaxTimes}>retry_badcase_max_times</FieldCaption>
            <input min={0} max={10} step={1} type="number" value={retryBadcaseMaxTimes} onChange={(event) => setRetryBadcaseMaxTimes(Number(event.target.value))} />
          </label>
          <label>
            <FieldCaption hint={controlHints.retryBadcaseRatioThreshold}>retry_badcase_ratio_threshold</FieldCaption>
            <input min={0} max={20} step={0.5} type="number" value={retryBadcaseRatioThreshold} onChange={(event) => setRetryBadcaseRatioThreshold(Number(event.target.value))} />
          </label>
        </div>
      </div>

      <div className="native-workbench generation-workbench">
        {!appReady && <LoadingPanel status={status} />}
        {appReady && (
          <>
            <div className="prompt-workspace">
              <label>
                <FieldCaption hint={controlHints.targetText}>{t("targetText")}</FieldCaption>
                <textarea value={inputText} onChange={(event) => setInputText(event.target.value)} />
              </label>
              <label>
                <FieldCaption hint={controlHints.controlInstruction}>{t("controlInstruction")}</FieldCaption>
                <textarea value={controlInstruction} onChange={(event) => setControlInstruction(event.target.value)} />
              </label>
              {modeKey === "ultimate-cloning" && (
                <label>
                  <FieldCaption hint={controlHints.promptTranscript}>{t("promptTranscript")}</FieldCaption>
                  <textarea value={promptText} onChange={(event) => setPromptText(event.target.value)} />
                </label>
              )}
            </div>
            <GenerationResultPanel
              record={generatedRecord}
              sourceLabel={mode}
              description={generatedRecord?.description || (modeKey === "ultimate-cloning" ? promptText : controlInstruction)}
              voiceName={generatedVoiceName}
              isSaving={isSaving}
              message={message}
              error={error}
              onVoiceNameChange={setGeneratedVoiceName}
              onSaveVoice={saveGeneratedVoice}
              onExportAudio={generationAudioExport.exportAudio}
              exportMessage={generationAudioExport.exportMessage}
              exportError={generationAudioExport.exportError}
              canExport={generationAudioExport.canExport}
              canSaveVoice={Boolean(generatedRecord?.output_audio_path)}
              t={t}
            >
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
            </GenerationResultPanel>
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
      <FieldCaption className="field-title" hint={controlHints.referenceSource}>{t("referenceSource")}</FieldCaption>
      <div className="segmented-control">
        <button className={referenceKind === "upload" ? "active" : ""} type="button" onClick={() => setReferenceKind("upload")}>
          <Upload size={15} />
          {t("uploadedAudio")}
          <HelpBadge text={controlHints.uploadedAudio} focusable={false} />
        </button>
        <button className={referenceKind === "saved_voice" ? "active" : ""} type="button" onClick={() => setReferenceKind("saved_voice")}>
          <Library size={15} />
          {t("savedVoice")}
          <HelpBadge text={controlHints.savedVoice} focusable={false} />
        </button>
      </div>
      {referenceKind === "upload" && (
        <div className="reference-stack">
          <button className="ghost-action" type="button" onClick={selectAudio}>
            <Upload size={17} />
            {t("selectAudio")}
            <HelpBadge text={controlHints.selectAudio} focusable={false} />
          </button>
          {uploadedFile && <p>{`${t("selectedAudio")}: ${uploadedFile.name}`}</p>}
          {uploadedFile && (
            <div className="inline-save">
              <label>
                <FieldCaption hint={controlHints.uploadVoiceName}>{t("voiceName")}</FieldCaption>
                <input value={uploadVoiceName} onChange={(event) => setUploadVoiceName(event.target.value)} />
              </label>
              <button className="ghost-action" disabled={isSaving} type="button" onClick={saveUploadedVoice}>
                <Save size={17} />
                {t("saveUploadedVoice")}
                <HelpBadge text={controlHints.saveUploadedVoice} focusable={false} />
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

function FieldCaption({
  children,
  hint,
  className,
}: {
  children: string;
  hint: string;
  className?: string;
}) {
  return (
    <span className={className ? `field-caption ${className}` : "field-caption"}>
      <span>{children}</span>
      <HelpBadge text={hint} />
    </span>
  );
}

function HelpBadge({ text, focusable = true }: { text: string; focusable?: boolean }) {
  return (
    <span className="help-badge" aria-label={focusable ? text : undefined} tabIndex={focusable ? 0 : undefined} title={text}>
      <HelpCircle size={13} strokeWidth={2.4} />
      <span className="help-bubble" role="tooltip">{text}</span>
    </span>
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
