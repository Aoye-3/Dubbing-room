import { AudioWaveform, Download, MoreHorizontal, SlidersHorizontal, Sparkles } from "lucide-react";
import { useState } from "react";
import { apiClient } from "../shared/api/client";
import { mediaUrl } from "../shared/audio";
import type { AppDataState, AppVoice, SelectedAudioFile } from "../shared/types";
import type { MessageKey } from "../app/i18n";
import { EmptyState } from "./EmptyState";
export function VoiceLibraryPage({
  voices,
  appDataState,
  appDataError,
  reload,
  t,
}: {
  voices: AppVoice[];
  appDataState: AppDataState;
  appDataError: string;
  reload: () => Promise<void>;
  t: (key: MessageKey) => string;
}) {
  const [selectedFile, setSelectedFile] = useState<SelectedAudioFile | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [tags, setTags] = useState("");
  const [notes, setNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const isLoading = appDataState === "loading" || appDataState === "idle";

  const selectFile = async () => {
    const file = await apiClient.selectAudioFile();
    if (file) {
      setSelectedFile(file);
      setDisplayName(file.name.replace(/\.[^.]+$/, ""));
      setError("");
    }
  };

  const createVoice = async () => {
    if (!selectedFile || !displayName.trim()) {
      return;
    }
    setIsSaving(true);
    setError("");
    try {
      await apiClient.createVoice({
        source_audio_path: selectedFile.path,
        display_name: displayName.trim(),
        tags: parseTags(tags),
        notes,
        source: "upload",
      });
      setSelectedFile(null);
      setDisplayName("");
      setTags("");
      setNotes("");
      await reload();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : String(saveError));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section className="library-layout">
      <div className="import-panel">
        <div className="section-actions">
          <button className="ghost-action" type="button" onClick={selectFile}>
            <Download size={18} />
            {t("importVoice")}
          </button>
          <button className="primary-action" disabled={!selectedFile || !displayName.trim() || isSaving} type="button" onClick={createVoice}>
            <Sparkles size={18} />
            {t("createVoice")}
          </button>
        </div>
        <div className="import-fields">
          <label>
            <span>{t("voiceName")}</span>
            <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
          </label>
          <label>
            <span>{t("tags")}</span>
            <input value={tags} onChange={(event) => setTags(event.target.value)} />
          </label>
          <label>
            <span>{t("notes")}</span>
            <input value={notes} onChange={(event) => setNotes(event.target.value)} />
          </label>
        </div>
        {selectedFile && <p>{`${t("selectedAudio")}: ${selectedFile.name}`}</p>}
        {error && <p className="status-line error">{error}</p>}
      </div>
      {isLoading && <EmptyState title={t("loadingData")} />}
      {appDataState === "failed" && <EmptyState title={t("loadFailed")} detail={appDataError} actionLabel={t("retry")} onAction={reload} />}
      {appDataState === "ready" && voices.length === 0 && <EmptyState title={t("noSavedVoices")} />}
      <div className="voice-card-grid">
        {voices.map((voice) => (
          <article className="voice-card" key={voice.id}>
            <div className="voice-card-title">
              <AudioWaveform size={20} />
              <h2>{voice.display_name}</h2>
            </div>
            <p>{voice.notes || voice.audio_path}</p>
            <audio controls src={mediaUrl(voice.audio_path)} />
            <div className="tag-row">
              {voice.tags.map((tag) => (
                <span key={tag}>{tag}</span>
              ))}
            </div>
            <div className="card-actions">
              <button title={t("download")} aria-label={t("download")}>
                <Download size={17} />
              </button>
              <button title={t("edit")} aria-label={t("edit")}>
                <SlidersHorizontal size={17} />
              </button>
              <button title={t("more")} aria-label={t("more")}>
                <MoreHorizontal size={17} />
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function parseTags(raw: string): string[] {
  return raw
    .split(/[,\s，]+/)
    .map((tag) => tag.trim())
    .filter(Boolean);
}
