import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Filter, RefreshCw } from "lucide-react";
import { operatorApi } from "../api/operator";
import { DataTable } from "./DataTable";
import { DetailDrawer } from "./DetailDrawer";
import { EmptyState, ErrorState, LoadingState } from "./States";

export type WorkspaceTab = { label: string; workspace: string; description?: string };
export function WorkspacePage({ title, subtitle, tabs, actions }: { title: string; subtitle: string; tabs: WorkspaceTab[]; actions?: React.ReactNode }) {
  const [tab, setTab] = useState(tabs[0]); const [offset, setOffset] = useState(0); const [selected, setSelected] = useState<Record<string, unknown>>();
  const query = useQuery({ queryKey: ["workspace", tab.workspace, offset], queryFn: () => operatorApi.workspace(tab.workspace, offset), placeholderData: (previous) => previous });
  return <section className="page"><header className="page-header"><div><span className="eyebrow">Operations workspace</span><h1>{title}</h1><p>{subtitle}</p></div><div className="header-actions">{actions}<button className="button secondary" onClick={() => query.refetch()}><RefreshCw size={16} />Refresh</button></div></header>
    <div className="tabbar" role="tablist">{tabs.map((item) => <button role="tab" aria-selected={item.workspace === tab.workspace} key={`${item.workspace}:${item.label}`} onClick={() => { setTab(item); setOffset(0); }}>{item.label}</button>)}</div>
    <div className="panel"><div className="panel-heading"><div><h2>{tab.label}</h2><p>{tab.description || "Live records from the backend"}</p></div><button className="button ghost"><Filter size={15} />Filters</button></div>
      {query.isLoading ? <LoadingState /> : query.isError ? <ErrorState error={query.error} retry={() => query.refetch()} /> : !query.data?.items.length ? <EmptyState /> : <DataTable rows={query.data.items} total={query.data.total} offset={query.data.offset} limit={query.data.limit} onPage={setOffset} onSelect={setSelected} />}
    </div><DetailDrawer item={selected} title={tab.label} onClose={() => setSelected(undefined)} />
  </section>;
}
