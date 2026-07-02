import { CheckCircle2, RefreshCw, RotateCcw, Save, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../shared/api/client";
import { mediaUrl } from "../shared/audio";
import type { GenerationJob, GenerationTake } from "../shared/types";

type Labels = {
  jobs: string;
  retry: string;
  cancel: string;
  noJobs: string;
  takes: string;
  selectTake: string;
  selected: string;
  saveVoice: string;
};

export function JobListPage({ labels }: { labels: Labels }) {
  const [jobs, setJobs] = useState<GenerationJob[]>([]);
  const [takesByJob, setTakesByJob] = useState<Record<string, GenerationTake[]>>({});
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setError("");
      const result = await apiClient.listGenerationJobs();
      const items = result?.items ?? [];
      setJobs(items);
      const takeEntries = await Promise.all(
        items
          .filter((job) => job.backend_id === "indextts2")
          .map(async (job) => {
            const takes = await apiClient.listGenerationTakes({ job_id: job.id });
            return [job.id, takes?.items ?? []] as const;
          }),
      );
      setTakesByJob(Object.fromEntries(takeEntries));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 3000);
    return () => window.clearInterval(timer);
  }, [load]);

  const cancel = async (id: string) => {
    await apiClient.cancelGenerationJob({ id });
    await load();
  };

  const retry = async (id: string) => {
    await apiClient.retryGenerationJob({ id });
    await load();
  };

  const selectTake = async (id: string) => {
    await apiClient.selectGenerationTake({ id });
    await load();
  };

  const saveTakeAsVoice = async (take: GenerationTake) => {
    if (!take.output_asset?.path) {
      return;
    }
    await apiClient.createVoice({
      source_audio_path: take.output_asset.path,
      display_name: take.label || `Take ${take.take_index}`,
      tags: ["take", take.backend_id],
      notes: `Saved from generation job ${take.job_id}`,
      source: "take",
      duration_seconds: take.output_asset.duration_seconds,
    });
    await load();
  };

  return (
    <section className="history-list">
      <div className="section-actions">
        <button className="ghost-action" type="button" onClick={load}>
          <RefreshCw size={17} />
          {labels.retry}
        </button>
      </div>
      {error && <p className="status-line error">{error}</p>}
      {jobs.length === 0 && <div className="empty-state"><h2>{labels.noJobs}</h2></div>}
      {jobs.map((job) => (
        <article className="history-row job-row" key={job.id}>
          <div className="history-main">
            <h2>{job.status}</h2>
            <p>{job.backend_id}</p>
            <span>{job.created_at}</span>
          </div>
          <div className="history-text">
            <strong>{job.mode}</strong>
            <p>{job.input_text}</p>
            {job.error_summary && <p className="status-line error">{job.error_summary}</p>}
            {takesByJob[job.id]?.length > 0 && <TakeList labels={labels} takes={takesByJob[job.id]} onSelect={selectTake} onSave={saveTakeAsVoice} />}
          </div>
          <div className="history-actions">
            {job.status === "queued" && (
              <button title={labels.cancel} aria-label={labels.cancel} type="button" onClick={() => cancel(job.id)}>
                <XCircle size={19} />
              </button>
            )}
            {job.status === "failed" && (
              <button title={labels.retry} aria-label={labels.retry} type="button" onClick={() => retry(job.id)}>
                <RotateCcw size={19} />
              </button>
            )}
          </div>
        </article>
      ))}
    </section>
  );
}

function TakeList({
  labels,
  takes,
  onSelect,
  onSave,
}: {
  labels: Labels;
  takes: GenerationTake[];
  onSelect: (id: string) => Promise<void>;
  onSave: (take: GenerationTake) => Promise<void>;
}) {
  return (
    <div className="take-list">
      <strong>{labels.takes}</strong>
      {takes.map((take) => (
        <div className="take-row" key={take.id}>
          <div>
            <span>{take.label || `Take ${take.take_index}`}</span>
            <small>{take.status}</small>
          </div>
          {take.output_asset?.path ? <audio controls src={mediaUrl(take.output_asset.path)} /> : <p>{take.error_summary || "--"}</p>}
          <div className="take-actions">
            <button
              aria-label={labels.selectTake}
              disabled={take.status !== "succeeded" || take.is_selected}
              title={labels.selectTake}
              type="button"
              onClick={() => onSelect(take.id)}
            >
              <CheckCircle2 size={17} />
            </button>
            <button
              aria-label={labels.saveVoice}
              disabled={take.status !== "succeeded" || !take.output_asset?.path}
              title={labels.saveVoice}
              type="button"
              onClick={() => onSave(take)}
            >
              <Save size={17} />
            </button>
          </div>
          {take.is_selected && <span className="take-selected">{labels.selected}</span>}
        </div>
      ))}
    </div>
  );
}
