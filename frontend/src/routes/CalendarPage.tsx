import { useQuery } from "@tanstack/react-query";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { operatorApi } from "../api/operator";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export default function CalendarPage() {
  const assets = useQuery({ queryKey: ["calendar-assets"], queryFn: () => operatorApi.workspace("assets", 0, 50) });
  const days = Array.from({ length: 35 }, (_, index) => index - 2);
  return <section className="page"><header className="page-header"><div><span className="eyebrow">Planning only · no publishing</span><h1>Content calendar</h1><p>Week, month, and list planning views backed by approved assets; publishing is feature-gated off.</p></div><div className="segmented"><button>Week</button><button className="active">Month</button><button>List</button></div></header>
    <div className="calendar-toolbar"><button className="icon-button"><ChevronLeft /></button><h2>August 2026</h2><button className="icon-button"><ChevronRight /></button><span className="spacer" /><span className="status-badge neutral">Publishing unavailable</span></div>
    <div className="calendar-grid">{["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => <strong key={day}>{day}</strong>)}{days.map((day, index) => <div className={day < 1 || day > 31 ? "outside" : ""} key={index}><span>{day < 1 ? 31 + day : day > 31 ? day - 31 : day}</span></div>)}</div>
    <div className="panel"><div className="panel-heading"><div><h2>Unscheduled approved assets</h2><p>Content lines remain backend-owned; no targets or sample slots are invented.</p></div></div>{assets.isLoading ? <LoadingState /> : assets.isError ? <ErrorState error={assets.error} /> : !assets.data?.items.length ? <EmptyState title="No assets ready to schedule" /> : <div className="asset-strip">{assets.data.items.slice(0, 8).map((asset) => <article key={String(asset.id)}><CalendarDays /><strong>{String(asset.asset_uid)}</strong><span>{String(asset.asset_type || asset.status)}</span></article>)}</div>}</div>
  </section>;
}
