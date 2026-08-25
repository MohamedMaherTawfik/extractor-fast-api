import { useEffect, useMemo, useState } from "react";
import { Command, Search, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { operatorApi } from "../api/operator";
import { usePreferences } from "../app/PreferencesContext";

const commands = [
  ["Create generation job", "/generation?tab=create"], ["Open products", "/products"], ["Search customers", "/customers"],
  ["Open conversation inbox", "/conversations"], ["Create order draft", "/sales?tab=orders"], ["View MSC intake", "/msc"], ["Open approvals", "/approvals"],
] as const;

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState(""); const navigate = useNavigate(); const { language } = usePreferences();
  const search = useQuery({ queryKey: ["search", query], queryFn: () => operatorApi.search(query), enabled: query.trim().length >= 2 });
  useEffect(() => { if (!open) setQuery(""); }, [open]);
  const visible = useMemo(() => commands.filter(([name]) => name.toLowerCase().includes(query.toLowerCase())), [query]);
  if (!open) return null;
  const go = (path: string) => { navigate(path); onClose(); };
  return <div className="palette-scrim" onMouseDown={onClose}><div className="command-palette" role="dialog" aria-modal="true" aria-label="Command palette" onMouseDown={(e) => e.stopPropagation()}>
    <div className="palette-input"><Search /><input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder={language === "ar" ? "اكتب أمرًا أو ابحث…" : "Type a command or search…"} /><button className="icon-button" onClick={onClose}><X /></button></div>
    <div className="command-list"><span className="section-label"><Command size={14} />Commands</span>{visible.map(([name, path]) => <button key={path} onClick={() => go(path)}><span>{name}</span><kbd>↵</kbd></button>)}
      {search.data?.length ? <><span className="section-label">Search results</span>{search.data.map((item) => <button key={`${item.type}-${item.uid}`} onClick={() => go(`/${item.type === "generation" ? "generation" : item.type + "s"}`)}><span><small>{item.type}</small>{item.label}</span><code>{item.uid}</code></button>)}</> : null}
    </div>
  </div></div>;
}
