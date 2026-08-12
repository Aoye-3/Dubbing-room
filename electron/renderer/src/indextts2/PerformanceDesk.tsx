import { CheckCircle2, Download, Save, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { mediaUrl } from "../shared/audio";
import { apiClient } from "../shared/api/client";
import { classifyBackendError } from "../shared/api/errors";
import type { GenerationJob, GenerationTake } from "../shared/types";

const terminalJobStatuses = new Set(["succeeded", "failed", "cancelled", "deleted"]);

export function PerformanceDesk({ jobId, onHistoryChanged }: { jobId: string | null; onHistoryChanged: () => void | Promise<void> }) {
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [takes, setTakes] = useState<GenerationTake[]>([]);
  const [error, setError] = useState("");
  const [activeAction, setActiveAction] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!jobId) return;
    try {
      const [nextJob, takeResult] = await Promise.all([
        apiClient.getGenerationJob({ id: jobId }),
        apiClient.listGenerationTakes({ job_id: jobId }),
      ]);
      setJob(nextJob ?? null);
      setTakes(takeResult.items);
      setError("");
      return nextJob?.status;
    } catch (value) {
      const classified = classifyBackendError(value);
      setError(`${classified.category}: ${classified.message}`);
    }
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return;
    let active = true;
    let timer: number | undefined;
    const poll = async () => {
      const status = await load();
      if (active && !terminalJobStatuses.has(status ?? "")) timer = window.setTimeout(() => void poll(), 3000);
    };
    void poll();
    return () => {
      active = false;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [jobId, load]);

  const runAction = async (key: string, action: () => Promise<void>) => {
    if (activeAction) return;
    setActiveAction(key);
    setError("");
    try {
      await action();
    } catch (value) {
      const classified = classifyBackendError(value);
      setError(`${classified.category}: ${classified.message}`);
    } finally {
      setActiveAction(null);
    }
  };

  const selectTake = (take: GenerationTake) => runAction(`select:${take.id}`, async () => {
    await apiClient.selectGenerationTake({ id: take.id });
    await onHistoryChanged();
    await load();
  });

  const saveTake = (take: GenerationTake) => runAction(`save:${take.id}`, async () => {
    if (!take.output_asset?.path) return;
    await apiClient.createVoice({
      source_audio_path: take.output_asset.path,
      display_name: take.label || `Take ${take.take_index}`,
      tags: ["take", "indextts2-2.5"],
      notes: `Saved from generation job ${take.job_id}`,
      source: "take",
      source_generation_id: take.legacy_generation_id,
      duration_seconds: take.output_asset.duration_seconds,
    });
  });

  const exportTake = (take: GenerationTake) => runAction(`export:${take.id}`, async () => {
    if (!take.output_asset?.path) return;
    await apiClient.exportAudioFile({ project_relative_path: take.output_asset.path, suggested_name: `${take.label || take.id}.wav` });
  });

  const cancel = () => runAction("cancel", async () => {
    if (!jobId) return;
    await apiClient.cancelGenerationJob({ id: jobId });
    await load();
  });

  if (!jobId) {
    return <aside className="result-panel performance-desk"><h2>Performance Desk</h2><p className="mode-description">Generate Takes to compare performances here.</p></aside>;
  }

  return (
    <aside className="result-panel performance-desk" aria-live="polite">
      <div className="result-header"><h2>Performance Desk</h2><code>{jobId}</code></div>
      <div className="performance-job-summary">
        <strong>{job?.status ?? "loading"}</strong>
        {(job?.status === "queued" || job?.status === "running") && <button className="ghost-action danger" disabled={activeAction !== null} type="button" onClick={() => void cancel()}><XCircle size={16} />Cancel</button>}
      </div>
      {error && <p className="status-line error">{error}</p>}
      {job?.error_summary && <p className="status-line error">{job.error_summary}</p>}
      <div className="performance-takes">
        {takes.map((take) => (
          <article className={`performance-take ${take.is_selected ? "selected" : ""}`} key={take.id}>
            <header><strong>{take.label || `Take ${take.take_index}`}</strong><span>{take.status}</span></header>
            {take.output_asset?.path && <TakeAudio path={take.output_asset.path} />}
            <details><summary>Parameters</summary><pre>{JSON.stringify(take.params ?? {}, null, 2)}</pre></details>
            {take.warnings?.map((warning) => <p className="status-line warning" key={`${warning.code}:${warning.message}`}>{warning.message}</p>)}
            {take.error_summary && <p className="status-line error">{take.error_summary}</p>}
            <div className="take-actions">
              <button aria-label={`Select ${take.label || `Take ${take.take_index}`}`} disabled={activeAction !== null || take.status !== "succeeded" || take.is_selected} type="button" onClick={() => void selectTake(take)}><CheckCircle2 size={17} /></button>
              <button aria-label={`Export ${take.label || `Take ${take.take_index}`}`} disabled={activeAction !== null || !take.output_asset?.path} type="button" onClick={() => void exportTake(take)}><Download size={17} /></button>
              <button aria-label={`Save ${take.label || `Take ${take.take_index}`} to Voice Library`} disabled={activeAction !== null || !take.output_asset?.path} type="button" onClick={() => void saveTake(take)}><Save size={17} /></button>
            </div>
          </article>
        ))}
      </div>
    </aside>
  );
}

function TakeAudio({ path }: { path: string }) {
  const source = mediaUrl(path);
  return source ? <audio controls src={source} /> : <span>{path}</span>;
}
