import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowUpRight, Boxes, ClipboardCheck, Factory, FileStack, MessageSquareText, PackageCheck, RefreshCw, ShoppingBag } from "lucide-react";
import { operatorApi } from "../api/operator";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { StatusBadge } from "../components/StatusBadge";

const metricMeta: Record<string, { label: string; icon: typeof Boxes; accent: string }> = {
  pending_jobs: { label: "Pending jobs", icon: FileStack, accent: "violet" }, generation_jobs: { label: "Generation queue", icon: Factory, accent: "cyan" },
  content_items: { label: "Content master", icon: PackageCheck, accent: "blue" }, approvals: { label: "Awaiting approval", icon: ClipboardCheck, accent: "amber" },
  sales_today: { label: "Sales today · EGP", icon: ArrowUpRight, accent: "green" }, orders: { label: "Sales orders", icon: ShoppingBag, accent: "indigo" },
  msc_pending: { label: "MSC pending", icon: AlertTriangle, accent: "orange" }, open_conversations: { label: "Open conversations", icon: MessageSquareText, accent: "pink" },
  human_handoffs: { label: "Human handoffs", icon: AlertTriangle, accent: "red" },
};

export default function DashboardPage() {
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: operatorApi.dashboard, refetchInterval: 15000 });
  const health = useQuery({ queryKey: ["health"], queryFn: operatorApi.health, refetchInterval: 15000 });
  if (dashboard.isLoading) return <LoadingState label="Building the command center" />;
  if (dashboard.isError) return <ErrorState error={dashboard.error} retry={() => dashboard.refetch()} />;
  return <section className="page"><header className="page-header hero"><div><span className="eyebrow">Live operational overview</span><h1>Good morning, Operator.</h1><p>One surface for system health, queues, approvals, commerce, and customer operations.</p></div><button className="button secondary" onClick={() => dashboard.refetch()}><RefreshCw size={16} />Refresh data</button></header>
    <div className="metric-grid">{Object.entries(dashboard.data!.metrics).map(([key, value]) => { const meta = metricMeta[key] || { label: key, icon: Boxes, accent: "blue" }; const Icon = meta.icon; return <article className={`metric-card ${meta.accent}`} key={key}><div className="metric-icon"><Icon /></div><div><span>{meta.label}</span><strong>{value}</strong></div><small>Backend snapshot</small></article>; })}</div>
    <div className="dashboard-grid"><div className="panel health-panel"><div className="panel-heading"><div><span className="eyebrow">Infrastructure</span><h2>System health</h2></div><span className="live-pulse">LIVE</span></div>{health.isError ? <ErrorState error={health.error} retry={() => health.refetch()} /> : <div className="health-grid">{Object.entries(health.data || {}).map(([name, state]) => <div key={name}><span>{name.replaceAll("_", " ")}</span><StatusBadge value={state} /></div>)}</div>}</div>
      <div className="panel activity-panel"><div className="panel-heading"><div><span className="eyebrow">Needs attention</span><h2>Operational inbox</h2></div></div>{dashboard.data!.notifications.length ? dashboard.data!.notifications.map((item) => <article key={item.id}><span className="activity-line" /><div><StatusBadge value={item.severity} /><h3>{item.type.replaceAll("_", " ")}</h3><p>{item.title}</p><time>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.created_at))}</time></div></article>) : <EmptyState title="All clear" detail="No critical backend events need attention." />}</div></div>
  </section>;
}
