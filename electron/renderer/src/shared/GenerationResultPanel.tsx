import { Download, FileAudio, Play, Save } from "lucide-react";
import type { ReactNode } from "react";
import type { MessageKey } from "../app/i18n";
import { mediaUrl } from "./audio";
import type { AppGeneration } from "./types";

type GenerationResultPanelProps = {
  record: AppGeneration | null;
  sourceLabel: string;
  description: string;
  voiceName: string;
  isSaving: boolean;
  message: string;
  error: string;
  onVoiceNameChange: (value: string) => void;
  onSaveVoice: () => void;
  onExportAudio: () => void;
  exportMessage: string;
  exportError: string;
  canExport: boolean;
  canSaveVoice: boolean;
  t: (key: MessageKey) => string;
  children?: ReactNode;
};

export function GenerationResultPanel({
  record,
  sourceLabel,
  description,
  voiceName,
  isSaving,
  message,
  error,
  onVoiceNameChange,
  onSaveVoice,
  onExportAudio,
  exportMessage,
  exportError,
  canExport,
  canSaveVoice,
  t,
  children,
}: GenerationResultPanelProps) {
  const audioPath = record?.output_audio_path ?? "";

  return (
    <aside className="result-panel">
      {children}
      <div className="result-header">
        <FileAudio size={20} />
        <h2>{t("generationOutput")}</h2>
      </div>
      {audioPath ? (
        <div className="audio-result">
          <audio controls src={mediaUrl(audioPath)} />
          <dl className="adapter-summary">
            <dt>{t("source")}</dt>
            <dd>{sourceLabel}</dd>
            <dt>{t("description")}</dt>
            <dd>{description || record?.description || "--"}</dd>
            <dt>{t("status")}</dt>
            <dd>{record?.status ?? "--"}</dd>
            <dt>{t("sampleRate")}</dt>
            <dd>{record?.sample_rate ? `${record.sample_rate} Hz` : "--"}</dd>
            <dt>{t("fileLocation")}</dt>
            <dd>{audioPath}</dd>
          </dl>
          <div className="result-actions">
            <button className="ghost-action" disabled={!canExport} type="button" onClick={onExportAudio}>
              <Download size={17} />
              {t("exportAudio")}
            </button>
          </div>
          <div className="inline-save">
            <label>
              <span>{t("voiceName")}</span>
              <input value={voiceName} onChange={(event) => onVoiceNameChange(event.target.value)} />
            </label>
            <button className="ghost-action" disabled={!canSaveVoice || isSaving || !voiceName.trim()} onClick={onSaveVoice} type="button">
              <Save size={17} />
              {t("saveGeneratedVoice")}
            </button>
          </div>
        </div>
      ) : (
        <div className="audio-placeholder">
          <Play size={22} />
          <span>{record?.status === "failed" ? record.error_summary : t("noGeneration")}</span>
        </div>
      )}
      {message && <p className="status-line success">{message}</p>}
      {error && <p className="status-line error">{error}</p>}
      {exportMessage && <p className="status-line success">{exportMessage}</p>}
      {exportError && <p className="status-line error">{exportError}</p>}
    </aside>
  );
}
