import { AlertTriangle, Inbox, LoaderCircle, RefreshCw, WifiOff } from "lucide-react";
import { ApiError } from "../types/operator";

export function LoadingState({ label = "Loading operational data" }: { label?: string }) { return <div className="state-card" role="status"><LoaderCircle className="spin" /><p>{label}</p></div>; }
export function EmptyState({ title = "No records yet", detail = "The backend returned an empty result. No sample rows are shown.", action }: { title?: string; detail?: string; action?: React.ReactNode }) { return <div className="state-card"><Inbox /><h3>{title}</h3><p>{detail}</p>{action}</div>; }
export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const apiError = error instanceof ApiError ? error : undefined;
  return <div className="state-card error" role="alert">{apiError?.status === 0 ? <WifiOff /> : <AlertTriangle />}<h3>{apiError?.status === 0 ? "Backend unavailable" : "Unable to load this workspace"}</h3><p>{error instanceof Error ? error.message : "Unknown error"}</p>{apiError?.requestId && <code>Request {apiError.requestId}</code>}{retry && <button className="button secondary" onClick={retry}><RefreshCw size={15} />Retry</button>}</div>;
}
