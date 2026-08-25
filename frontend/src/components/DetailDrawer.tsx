import { X } from "lucide-react";
import { StatusBadge } from "./StatusBadge";

function Value({ value }: { value: unknown }) {
  if (value == null || value === "") return <span className="muted">—</span>;
  if (typeof value === "boolean") return <StatusBadge value={value ? "YES" : "NO"} />;
  if (typeof value === "object") return <pre>{JSON.stringify(value, null, 2)}</pre>;
  if (/status|state|priority|severity/i.test(String(value))) return <span>{String(value)}</span>;
  return <span>{String(value)}</span>;
}

export function DetailDrawer({ item, title, onClose, children }: { item?: Record<string, unknown>; title: string; onClose: () => void; children?: React.ReactNode }) {
  if (!item) return null;
  return <div className="drawer-scrim" onMouseDown={onClose}><aside className="detail-drawer" role="dialog" aria-modal="true" aria-label={title} onMouseDown={(e) => e.stopPropagation()}>
    <header><div><span className="eyebrow">Record detail</span><h2>{title}</h2></div><button className="icon-button" aria-label="Close detail" onClick={onClose}><X /></button></header>
    {children}
    <dl className="detail-list">{Object.entries(item).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd><Value value={value} /></dd></div>)}</dl>
  </aside></div>;
}
