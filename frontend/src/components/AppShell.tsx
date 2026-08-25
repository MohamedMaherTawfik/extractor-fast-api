import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity, Archive, BarChart3, Bell, Bot, Boxes, CalendarDays, ChevronLeft, CircleDollarSign, ClipboardCheck,
  Command, Factory, FileSearch, Gauge, Grid2X2, Languages, Menu, MessageSquareText, Moon, PackageSearch, PanelLeftClose,
  Search, Settings, ShieldCheck, Sparkles, Sun, UsersRound, WandSparkles,
} from "lucide-react";
import { operatorApi } from "../api/operator";
import { useFeatures } from "../app/FeatureContext";
import { usePreferences } from "../app/PreferencesContext";
import { translate } from "../i18n/translations";
import { CommandPalette } from "./CommandPalette";
import { StatusBadge } from "./StatusBadge";

const nav = [
  ["home", "/", Gauge, "content"], ["content", "/content", Grid2X2, "content"], ["intelligence", "/intelligence", Sparkles, "intelligence"],
  ["patterns", "/patterns", WandSparkles, "patterns_recipes"], ["rules", "/rules", ShieldCheck, "rules"], ["generation", "/generation", Factory, "generation"],
  ["assets", "/assets", Archive, "generation"], ["calendar", "/calendar", CalendarDays, "content_calendar"], ["products", "/products", PackageSearch, "sales"],
  ["customers", "/customers", UsersRound, "sales"], ["sales", "/sales", CircleDollarSign, "sales"], ["inventory", "/inventory", Boxes, "sales"],
  ["suppliers", "/suppliers", Factory, "sales"], ["msc", "/msc", FileSearch, "msc"], ["conversations", "/conversations", MessageSquareText, "answer_bot"],
  ["service", "/customer-service", Bot, "answer_bot"], ["approvals", "/approvals", ClipboardCheck, "rules"], ["analytics", "/analytics", BarChart3, "content"],
  ["audit", "/audit", Activity, "rules"], ["settings", "/settings", Settings, "content"],
] as const;

export function AppShell() {
  const { capabilities, loading, offline } = useFeatures(); const { language, setLanguage, theme, setTheme, sidebarCollapsed, setSidebarCollapsed } = usePreferences();
  const [palette, setPalette] = useState(false); const [notifications, setNotifications] = useState(false);
  const health = useQuery({ queryKey: ["health"], queryFn: operatorApi.health, refetchInterval: offline ? 5000 : 15000, retry: false });
  const alerts = useQuery({ queryKey: ["notifications"], queryFn: operatorApi.notifications, refetchInterval: 30000, enabled: !offline });
  useEffect(() => { const listener = (event: KeyboardEvent) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setPalette(true); } if (event.key === "Escape") { setPalette(false); setNotifications(false); } }; addEventListener("keydown", listener); return () => removeEventListener("keydown", listener); }, []);
  const visible = nav.filter(([, , , feature]) => capabilities?.modules[feature]?.enabled !== false);
  return <div className={`app-shell ${sidebarCollapsed ? "collapsed" : ""}`}>
    <aside className="sidebar"><div className="brand"><div className="brand-mark">E</div>{!sidebarCollapsed && <div><strong>EMY</strong><span>CONTROL CENTER</span></div>}<button className="icon-button collapse" aria-label="Toggle sidebar" onClick={() => setSidebarCollapsed(!sidebarCollapsed)}><PanelLeftClose /></button></div>
      <nav aria-label="Main navigation">{visible.map(([key, path, Icon]) => <NavLink key={path} to={path} end={path === "/"} title={translate(language, key)}><Icon /><span>{translate(language, key)}</span></NavLink>)}</nav>
      <div className="sidebar-foot"><span className={`connection-dot ${offline ? "offline" : health.isError ? "degraded" : ""}`} />{!sidebarCollapsed && <div><strong>{offline ? "Backend offline" : loading ? "Discovering…" : "Local core connected"}</strong><span>{capabilities?.privacy_mode || "LOCAL_ONLY"}</span></div>}</div>
    </aside>
    <main className="main-area"><header className="topbar"><button className="mobile-menu icon-button"><Menu /></button><button className="global-search" onClick={() => setPalette(true)}><Search /><span>{translate(language, "search")}</span><kbd>Ctrl K</kbd></button>
      <div className="topbar-actions"><StatusBadge value={offline ? "OFFLINE" : health.data?.backend || "UNKNOWN"} /><button className="icon-button" aria-label="Language" onClick={() => setLanguage(language === "ar" ? "en" : "ar")}><Languages /></button><button className="icon-button" aria-label="Theme" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? <Sun /> : <Moon />}</button><button className="icon-button notification-button" aria-label="Notifications" onClick={() => setNotifications(!notifications)}><Bell />{!!alerts.data?.length && <i>{alerts.data.length}</i>}</button><div className="user-chip"><span>OP</span><div><strong>{translate(language, "operator")}</strong><small>Local admin</small></div></div></div>
      {notifications && <div className="notification-popover"><header><h3>Notifications</h3><button className="icon-button" onClick={() => setNotifications(false)}><ChevronLeft /></button></header>{alerts.data?.length ? alerts.data.map((item) => <article key={item.id}><StatusBadge value={item.severity} /><div><strong>{item.type.replaceAll("_", " ")}</strong><p>{item.title}</p></div></article>) : <p className="empty-inline">No operational alerts</p>}</div>}
    </header><div className="route-frame"><Outlet /></div></main>
    <CommandPalette open={palette} onClose={() => setPalette(false)} />
  </div>;
}
