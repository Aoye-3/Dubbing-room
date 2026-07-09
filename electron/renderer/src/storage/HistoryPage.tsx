import { AudioWaveform, Download, RotateCcw, Star, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../shared/api/client";
import { mediaUrl } from "../shared/audio";
import type { AppDataState, AppGeneration } from "../shared/types";
import type { MessageKey } from "../app/i18n";
import { EmptyState } from "./EmptyState";

type HistoryView = "history" | "trash";
type SourceFilter = "all" | "voice-design" | "voice-cloning" | "ultimate-cloning" | "indextts2-performance";
type FavoriteFilter = "all" | "favorite" | "plain";
type StatusFilter = "all" | "succeeded" | "failed" | "running";

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
  reload: () => Promise<void>;
  t: (key: MessageKey) => string;
}) {
  const [view, setView] = useState<HistoryView>("history");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [favoriteFilter, setFavoriteFilter] = useState<FavoriteFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [trashedGenerations, setTrashedGenerations] = useState<AppGeneration[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [trashError, setTrashError] = useState("");

  const loadTrash = async () => {
    setTrashError("");
    try {
      const result = await apiClient.listGenerations({ deleted_only: true });
      setTrashedGenerations(result.items);
    } catch (error) {
      setTrashError(error instanceof Error ? error.message : String(error));
    }
  };

  useEffect(() => {
    if (view === "trash") {
      loadTrash();
    }
  }, [view]);

  const sourceOptions = useMemo(
    () => [
      ["all", t("allSources")],
      ["voice-design", t("navDesign")],
      ["voice-cloning", t("navClone")],
      ["ultimate-cloning", t("navUltimate")],
      ["indextts2-performance", t("navIndexTTS2")],
    ] as const,
    [t],
  );
  const visibleRows = filterGenerations(view === "trash" ? trashedGenerations : generations, sourceFilter, favoriteFilter, statusFilter);
  const selectedVisibleIds = selectedIds.filter((id) => visibleRows.some((row) => row.id === id));
  const allVisibleSelected = visibleRows.length > 0 && visibleRows.every((row) => selectedIds.includes(row.id));
  const isLoading = appDataState === "loading" || appDataState === "idle";

  const refresh = async () => {
    await reload();
    if (view === "trash") {
      await loadTrash();
    }
  };

  const toggleFavorite = async (row: AppGeneration) => {
    await apiClient.updateGenerationFavorite({ id: row.id, is_favorite: !row.is_favorite });
    await refresh();
  };

  const moveToTrash = async (row: AppGeneration) => {
    await apiClient.trashGeneration({ id: row.id });
    await refresh();
  };

  const restore = async (row: AppGeneration) => {
    await apiClient.restoreGeneration({ id: row.id });
    setSelectedIds((ids) => ids.filter((id) => id !== row.id));
    await refresh();
  };

  const purgeSelected = async () => {
    if (selectedVisibleIds.length === 0) {
      return;
    }
    await apiClient.purgeGenerations({ ids: selectedVisibleIds });
    setSelectedIds([]);
    await refresh();
  };

  const exportAudio = async (row: AppGeneration) => {
    if (!row.output_audio_path) {
      return;
    }
    await apiClient.exportAudioFile({
      project_relative_path: row.output_audio_path,
      suggested_name: `${row.id}.wav`,
    });
  };

  const toggleVisibleSelection = () => {
    if (allVisibleSelected) {
      setSelectedIds((ids) => ids.filter((id) => !visibleRows.some((row) => row.id === id)));
      return;
    }
    setSelectedIds(Array.from(new Set([...selectedIds, ...visibleRows.map((row) => row.id)])));
  };

  return (
    <section className="history-list">
      <div className="history-toolbar">
        <div className="segmented-control history-tabs">
          <button className={view === "history" ? "active" : ""} type="button" onClick={() => setView("history")}>
            {t("historyTab")}
          </button>
          <button className={view === "trash" ? "active" : ""} type="button" onClick={() => setView("trash")}>
            {t("trashTab")}
          </button>
        </div>
        <div className="filter-row">
          <label>
            <span>{t("source")}</span>
            <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as SourceFilter)}>
              {sourceOptions.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{t("favorite")}</span>
            <select value={favoriteFilter} onChange={(event) => setFavoriteFilter(event.target.value as FavoriteFilter)}>
              <option value="all">{t("allFavorites")}</option>
              <option value="favorite">{t("withFavorite")}</option>
              <option value="plain">{t("withoutFavorite")}</option>
            </select>
          </label>
          <label>
            <span>{t("status")}</span>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}>
              <option value="all">{t("allStatuses")}</option>
              <option value="succeeded">succeeded</option>
              <option value="failed">failed</option>
              <option value="running">running</option>
            </select>
          </label>
        </div>
        {view === "trash" && (
          <div className="section-actions">
            <button className="ghost-action" disabled={visibleRows.length === 0} type="button" onClick={toggleVisibleSelection}>
              {allVisibleSelected ? t("clearSelection") : t("selectFiltered")}
            </button>
            <button className="ghost-action danger" disabled={selectedVisibleIds.length === 0} type="button" onClick={purgeSelected}>
              <Trash2 size={17} />
              {t("deleteSelected")}
            </button>
          </div>
        )}
      </div>

      {isLoading && view === "history" && <EmptyState title={t("loadingData")} />}
      {appDataState === "failed" && view === "history" && <EmptyState title={t("loadFailed")} detail={appDataError} actionLabel={t("retry")} onAction={reload} />}
      {trashError && <EmptyState title={t("loadFailed")} detail={trashError} actionLabel={t("retry")} onAction={loadTrash} />}
      {appDataState === "ready" && visibleRows.length === 0 && !trashError && <EmptyState title={view === "trash" ? t("trashEmpty") : t("noHistoryItems")} />}

      {visibleRows.map((row) => (
        <article className="history-row" key={row.id}>
          {view === "trash" ? (
            <input
              aria-label={t("selectItem")}
              checked={selectedIds.includes(row.id)}
              type="checkbox"
              onChange={(event) => {
                setSelectedIds((ids) => event.target.checked ? [...ids, row.id] : ids.filter((id) => id !== row.id));
              }}
            />
          ) : (
            <AudioWaveform size={22} className="wave-icon" />
          )}
          <div className="history-main">
            <h2>{sourceLabel(row.source_mode, t)}</h2>
            <p>{row.status}</p>
            <span>{row.created_at}</span>
          </div>
          <div className="history-text">
            <strong>{row.description || row.control_instruction || row.prompt_text || t("noReference")}</strong>
            <p>{row.input_text}</p>
            {row.error_summary && <p className="status-line error">{row.error_summary}</p>}
          </div>
          <div className="history-output">
            {row.output_audio_path && <audio controls src={mediaUrl(row.output_audio_path)} />}
            <span>{row.output_audio_path || t("noOutput")}</span>
          </div>
          <div className="history-actions">
            <button className={row.is_favorite ? "active" : ""} title={t("favorite")} aria-label={t("favorite")} type="button" onClick={() => toggleFavorite(row)}>
              <Star size={19} fill={row.is_favorite ? "currentColor" : "none"} />
            </button>
            {row.output_audio_path && (
              <button title={t("exportAudio")} aria-label={t("exportAudio")} type="button" onClick={() => exportAudio(row)}>
                <Download size={18} />
              </button>
            )}
            {view === "trash" ? (
              <button title={t("restore")} aria-label={t("restore")} type="button" onClick={() => restore(row)}>
                <RotateCcw size={18} />
              </button>
            ) : (
              <button title={t("moveToTrash")} aria-label={t("moveToTrash")} type="button" onClick={() => moveToTrash(row)}>
                <Trash2 size={18} />
              </button>
            )}
          </div>
        </article>
      ))}
      <div className="end-note">{t("endReached")}</div>
    </section>
  );
}

function filterGenerations(
  rows: AppGeneration[],
  sourceFilter: SourceFilter,
  favoriteFilter: FavoriteFilter,
  statusFilter: StatusFilter,
): AppGeneration[] {
  return rows.filter((row) => {
    if (sourceFilter !== "all" && row.source_mode !== sourceFilter) {
      return false;
    }
    if (favoriteFilter === "favorite" && !row.is_favorite) {
      return false;
    }
    if (favoriteFilter === "plain" && row.is_favorite) {
      return false;
    }
    if (statusFilter !== "all" && row.status !== statusFilter) {
      return false;
    }
    return true;
  });
}

function sourceLabel(sourceMode: string, t: (key: MessageKey) => string): string {
  if (sourceMode === "voice-design") {
    return t("navDesign");
  }
  if (sourceMode === "voice-cloning") {
    return t("navClone");
  }
  if (sourceMode === "ultimate-cloning") {
    return t("navUltimate");
  }
  if (sourceMode === "indextts2-performance") {
    return t("navIndexTTS2");
  }
  return sourceMode || "legacy";
}
