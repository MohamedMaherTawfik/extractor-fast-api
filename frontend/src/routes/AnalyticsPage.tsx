import { useQuery } from "@tanstack/react-query";
import { BarChart3, Bot, Boxes, Factory, ShoppingCart } from "lucide-react";
import { operatorApi } from "../api/operator";
import { ErrorState, LoadingState } from "../components/States";

export default function AnalyticsPage() {
  const query = useQuery({ queryKey: ["dashboard"], queryFn: operatorApi.dashboard });
  if (query.isLoading) return <LoadingState />; if (query.isError) return <ErrorState error={query.error} />;
  const sections = [{ title: "Content", icon: BarChart3, values: [["Content items", query.data!.metrics.content_items], ["Pending collection", query.data!.metrics.pending_jobs]] }, { title: "Generation", icon: Factory, values: [["Active jobs", query.data!.metrics.generation_jobs]] }, { title: "Sales", icon: ShoppingCart, values: [["Sales today (EGP)", query.data!.metrics.sales_today], ["Orders", query.data!.metrics.orders]] }, { title: "Inventory & MSC", icon: Boxes, values: [["MSC pending", query.data!.metrics.msc_pending]] }, { title: "Customer service", icon: Bot, values: [["Open conversations", query.data!.metrics.open_conversations], ["Handoffs", query.data!.metrics.human_handoffs]] }];
  return <section className="page"><header className="page-header"><div><span className="eyebrow">Backend-derived only</span><h1>Analytics</h1><p>Operational summaries from existing domain metrics. No frontend projections or invented growth charts.</p></div></header><div className="analytics-grid">{sections.map(({ title, icon: Icon, values }) => <article className="panel" key={title}><div className="analytics-title"><Icon /><h2>{title}</h2></div>{values.map(([label, value]) => <div className="analytic-row" key={String(label)}><span>{label}</span><strong>{value}</strong></div>)}</article>)}</div></section>;
}
