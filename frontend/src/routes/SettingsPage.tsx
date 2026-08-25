import { useQuery } from "@tanstack/react-query";
import { Database, HardDrive, Languages, LockKeyhole, MessageCircle, Moon, Server, Shield, Sun } from "lucide-react";
import { apiUrl } from "../api/client";
import { operatorApi } from "../api/operator";
import { useFeatures } from "../app/FeatureContext";
import { usePreferences } from "../app/PreferencesContext";
import { ErrorState, LoadingState } from "../components/States";
import { StatusBadge } from "../components/StatusBadge";

export default function SettingsPage() {
  const settings = useQuery({ queryKey: ["safe-settings"], queryFn: operatorApi.settings }); const { capabilities } = useFeatures(); const { language, setLanguage, theme, setTheme } = usePreferences();
  if (settings.isLoading) return <LoadingState />; if (settings.isError) return <ErrorState error={settings.error} />;
  const data = settings.data as { backend: Record<string, unknown>; privacy: Record<string, unknown>; versions: Record<string, unknown>; channels: Array<Record<string, unknown>> };
  return <section className="page"><header className="page-header"><div><span className="eyebrow">Safe configuration view</span><h1>Settings</h1><p>Business settings remain backend-owned. This page never reads or stores secrets.</p></div></header><div className="settings-layout"><nav className="settings-nav"><a href="#general">General</a><a href="#backend">Backend</a><a href="#providers">Providers</a><a href="#privacy">Privacy</a><a href="#accessibility">Accessibility</a><a href="#system">System</a></nav><div className="settings-content">
    <section id="general" className="panel"><div className="setting-heading"><Moon /><div><h2>Appearance</h2><p>Stored locally as a safe UI preference.</p></div></div><div className="choice-row">{(["light", "dark", "system"] as const).map((item) => <button className={theme === item ? "active" : ""} onClick={() => setTheme(item)} key={item}>{item === "light" ? <Sun /> : <Moon />}{item}</button>)}</div><div className="setting-heading"><Languages /><div><h2>Interface language</h2><p>Arabic defaults to RTL; English switches to LTR.</p></div></div><div className="choice-row"><button className={language === "ar" ? "active" : ""} onClick={() => setLanguage("ar")}>العربية</button><button className={language === "en" ? "active" : ""} onClick={() => setLanguage("en")}>English</button></div></section>
    <section id="backend" className="panel"><div className="setting-heading"><Server /><div><h2>Backend connection</h2><p>{apiUrl}</p></div><StatusBadge value="ONLINE" /></div><dl className="settings-list">{Object.entries(data.backend).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl></section>
    <section id="providers" className="panel"><div className="setting-heading"><MessageCircle /><div><h2>Messaging providers</h2><p>Full credentials are never exposed.</p></div></div><div className="provider-list">{data.channels.map((channel) => <div key={String(channel.channel)}><strong>{String(channel.channel)}</strong><StatusBadge value={channel.availability} /><span>{channel.adapter_registered ? "Adapter registered" : "No adapter"}</span></div>)}</div></section>
    <section id="privacy" className="panel"><div className="setting-heading"><Shield /><div><h2>Privacy & execution</h2><p>Policy values returned by the backend.</p></div><StatusBadge value={capabilities?.privacy_mode} /></div><dl className="settings-list">{Object.entries(data.privacy).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{String(value)}</dd></div>)}</dl></section>
    <section id="system" className="panel"><div className="setting-heading"><Database /><div><h2>System information</h2><p>Development control center · no packaging state.</p></div></div><div className="system-cards"><article><HardDrive /><span>Database</span><strong>SQLite · managed by backend</strong></article><article><LockKeyhole /><span>Secrets</span><strong>Backend only</strong></article></div></section>
  </div></div></section>;
}
