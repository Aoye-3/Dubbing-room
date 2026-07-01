import type { ShellStatus } from "./types";
export function LoadingPanel({ status }: { status: ShellStatus }) {
  return (
    <div className="loading-panel">
      <div className="loading-bar" />
      <h2>{status.message}</h2>
      <pre>{status.detail}</pre>
    </div>
  );
}
