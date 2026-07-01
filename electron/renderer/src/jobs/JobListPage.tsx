import { RefreshCw, RotateCcw, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../shared/api/client";
import type { GenerationJob, GenerationTake } from "../shared/types";

type Labels = {
  jobs: string;
  retry: string;
  cancel: string;
  noJobs: string;
  takes: string;
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
        <article className="history-row" key={job.id}>
          <div className="history-main">
            <h2>{job.status}</h2>
            <p>{job.backend_id}</p>
            <span>{job.created_at}</span>
          </div>
          <div className="history-text">
            <strong>{job.mode}</strong>
            <p>{job.input_text}</p>
            {job.error_summary && <p className="status-line error">{job.error_summary}</p>}
            {takesByJob[job.id]?.length > 0 && (
              <p>{`${labels.takes}: ${takesByJob[job.id].map((take) => `${take.label || take.take_index}:${take.status}${take.is_selected ? "*" : ""}`).join(", ")}`}</p>
            )}
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
