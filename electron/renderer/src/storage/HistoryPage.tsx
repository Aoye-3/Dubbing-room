import { AudioWaveform, MoreHorizontal, Star } from "lucide-react";
import { mediaUrl } from "../shared/audio";
import type { AppDataState, AppGeneration } from "../shared/types";
import type { MessageKey } from "../app/i18n";
import { EmptyState } from "./EmptyState";
export function HistoryPage({
  generations,
  appDataState,
  appDataError,
  reload,
  t,
}: {
  generations: AppGeneration[];
  appDataState: AppDataState;
  appDataError: string;
  reload: () => void;
  t: (key: MessageKey) => string;
}) {
  const isLoading = appDataState === "loading" || appDataState === "idle";
  return (
    <section className="history-list">
      {isLoading && <EmptyState title={t("loadingData")} />}
      {appDataState === "failed" && <EmptyState title={t("loadFailed")} detail={appDataError} actionLabel={t("retry")} onAction={reload} />}
      {appDataState === "ready" && generations.length === 0 && <EmptyState title={t("noHistoryItems")} />}
      {generations.map((row) => (
        <article className="history-row" key={row.id}>
          <AudioWaveform size={22} className="wave-icon" />
          <div className="history-main">
            <h2>{row.status}</h2>
            <p>{row.sample_rate ? `${row.sample_rate} Hz` : t("noOutput")}</p>
            <span>{row.created_at}</span>
          </div>
          <div className="history-text">
            <strong>{row.voice_id || row.reference_audio_path || t("noReference")}</strong>
            <p>{row.input_text}</p>
            {row.error_summary && <p className="status-line error">{row.error_summary}</p>}
          </div>
          <div className="history-actions">
            {row.output_audio_path && <audio controls src={mediaUrl(row.output_audio_path)} />}
            <button title={t("favorite")} aria-label={t("favorite")}>
              <Star size={19} />
            </button>
            <button title={t("more")} aria-label={t("more")}>
              <MoreHorizontal size={19} />
            </button>
          </div>
        </article>
      ))}
      <div className="end-note">{t("endReached")}</div>
    </section>
  );
}
