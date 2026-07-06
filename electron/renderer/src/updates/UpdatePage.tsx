import { AlertTriangle, CheckCircle2, DownloadCloud, GitBranch, RefreshCw, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient } from "../shared/api/client";
import type { ShellState, UpdateActionResult, UpdateStatus } from "../shared/types";
import type { MessageKey } from "../app/i18n";

type UpdatePageProps = {
  shellState: ShellState | null;
  t: (key: MessageKey) => string;
};

const defaultRepository = "https://github.com/Aoye-3/Dubbing-room.git";

export function UpdatePage({ shellState, t }: UpdatePageProps) {
  const [repositoryUrl, setRepositoryUrl] = useState(defaultRepository);
  const [branch, setBranch] = useState("main");
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [result, setResult] = useState<UpdateActionResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"check" | "fetch" | "apply" | "">("");

  const request = useMemo(() => ({ repositoryUrl, branch }), [branch, repositoryUrl]);
  const canApply = status?.state === "updateAvailable" && status.blockers.length === 0 && status.behind > 0 && !busy;
  const canFetch = !busy && repositoryUrl.trim().length > 0 && branch.trim().length > 0;

  const runStatusAction = useCallback(
    async (action: "check" | "fetch" | "apply") => {
      setBusy(action);
      setError("");
      setResult(null);
      try {
        if (action === "check") {
          const nextStatus = await apiClient.preflightUpdate(request);
          setStatus(nextStatus);
          if (!repositoryUrl && nextStatus.remoteUrl) {
            setRepositoryUrl(nextStatus.remoteUrl);
          }
          return;
        }
        const nextResult = action === "fetch" ? await apiClient.fetchUpdate(request) : await apiClient.applyUpdate(request);
        setResult(nextResult);
        setStatus(nextResult.status);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : String(caught));
      } finally {
        setBusy("");
      }
    },
    [repositoryUrl, request],
  );

  useEffect(() => {
    let mounted = true;
    apiClient.getUpdateStatus(request)
      .then((nextStatus) => {
        if (!mounted) {
          return;
        }
        setStatus(nextStatus);
        if (nextStatus.remoteUrl) {
          setRepositoryUrl(nextStatus.remoteUrl);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : String(caught));
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <section className="update-page">
      <div className="update-panel update-connect">
        <div className="update-panel-title">
          <DownloadCloud size={19} />
          <h2>{t("updatePageTitle")}</h2>
        </div>
        <div className="field-stack">
          <label>
            <span>{t("updateRepository")}</span>
            <input value={repositoryUrl} onChange={(event) => setRepositoryUrl(event.target.value)} placeholder={defaultRepository} />
          </label>
          <label>
            <span>{t("updateBranch")}</span>
            <input value={branch} onChange={(event) => setBranch(event.target.value)} placeholder="main" />
          </label>
        </div>
        <div className="update-actions">
          <button className="ghost-action" type="button" onClick={() => runStatusAction("check")} disabled={!canFetch}>
            <RefreshCw size={16} />
            {busy === "check" ? t("checkingUpdates") : t("checkUpdates")}
          </button>
          <button className="ghost-action" type="button" onClick={() => runStatusAction("fetch")} disabled={!canFetch}>
            <DownloadCloud size={16} />
            {busy === "fetch" ? t("fetchingUpdates") : t("fetchUpdates")}
          </button>
          <button className="primary-action" type="button" onClick={() => runStatusAction("apply")} disabled={!canApply}>
            <CheckCircle2 size={16} />
            {busy === "apply" ? t("applyingUpdate") : t("applyUpdate")}
          </button>
        </div>
        {result?.ok && <p className="status-line success">{result.summary}</p>}
        {(error || result?.error) && <p className="status-line error">{error || result?.error}</p>}
        {result?.ok && result.state === "succeeded" && <p className="status-line success">{t("restartRequired")}</p>}
      </div>

      <div className={`update-panel ${status?.blockers.length ? "blocked" : "ready"}`}>
        <div className="update-panel-title">
          {status?.blockers.length ? <AlertTriangle size={19} /> : <ShieldCheck size={19} />}
          <h2>{t("updateStatus")}</h2>
        </div>
        <dl className="update-meta">
          <dt>{t("project")}</dt>
          <dd>{shellState?.projectDir ?? "--"}</dd>
          <dt>{t("currentBranch")}</dt>
          <dd>{status?.currentBranch || "--"}</dd>
          <dt>{t("targetBranch")}</dt>
          <dd>{status?.targetBranch || branch}</dd>
          <dt>{t("currentCommit")}</dt>
          <dd>{shortHash(status?.currentCommit)}</dd>
          <dt>{t("remoteCommit")}</dt>
          <dd>{shortHash(status?.upstreamCommit)}</dd>
          <dt>{t("aheadBehind")}</dt>
          <dd>{`${status?.ahead ?? 0} / ${status?.behind ?? 0}`}</dd>
        </dl>
      </div>

      <div className="update-panel">
        <div className="update-panel-title">
          <ShieldCheck size={19} />
          <h2>{t("protectedPaths")}</h2>
        </div>
        <div className="update-check-list">
          {(status?.protectedPaths ?? []).map((item) => (
            <div className={item.ignored ? "update-check good" : "update-check bad"} key={item.path}>
              <span>{item.path}</span>
              <strong>{item.ignored ? t("ignored") : t("notIgnored")}</strong>
              <small>{item.classification}</small>
            </div>
          ))}
        </div>
      </div>

      <div className="update-panel">
        <div className="update-panel-title">
          <GitBranch size={19} />
          <h2>{t("updateDiagnostics")}</h2>
        </div>
        <UpdateList title={t("blockers")} empty={t("noBlockers")} items={status?.blockers ?? []} tone="error" />
        <UpdateList title={t("dirtyFiles")} empty={t("noDirtyFiles")} items={status?.dirtyTrackedFiles ?? []} />
        <UpdateList title={t("updateLog")} empty={t("noUpdateLog")} items={[...(status?.log ?? []), ...(result?.log ?? [])]} />
      </div>
    </section>
  );
}

function UpdateList({ title, empty, items, tone }: { title: string; empty: string; items: string[]; tone?: "error" }) {
  return (
    <div className="update-list-block">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p className="status-line success">{empty}</p>
      ) : (
        <ul className={tone === "error" ? "update-list error" : "update-list"}>
          {items.map((item, index) => (
            <li key={`${item}-${index}`}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function shortHash(value: string | undefined): string {
  return value ? value.slice(0, 12) : "--";
}
