import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { HashRouter } from "react-router-dom";
import App from "../App";
import { FeatureProvider } from "../app/FeatureContext";
import { PreferencesProvider } from "../app/PreferencesContext";

export const capabilities = { app: { name: "EMY", version: "1", environment: "test" }, modules: { content: { enabled: true }, intelligence: { enabled: true }, patterns_recipes: { enabled: true }, rules: { enabled: true }, generation: { enabled: true }, sales: { enabled: true }, msc: { enabled: true }, answer_bot: { enabled: true }, content_calendar: { enabled: true }, lead_engine: { enabled: false } }, features: {}, privacy_mode: "LOCAL_ONLY", realtime: { transport: "adaptive_polling", recommended_interval_seconds: 15 } };
export function json(value: unknown, status = 200) { return Promise.resolve(new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } })); }
export function mockBackend(extra?: (url: string, init?: RequestInit) => Promise<Response> | undefined) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => { const url = String(input); const custom = extra?.(url, init); if (custom) return custom; if (url.includes("/system/capabilities")) return json(capabilities); if (url.includes("/system/health-detail")) return json({ backend: "ONLINE", database: "ONLINE" }); if (url.includes("/system/notifications")) return json([]); if (url.includes("/system/dashboard")) return json({ as_of: new Date().toISOString(), metrics: { pending_jobs: 0, generation_jobs: 0, content_items: 0, approvals: 0, sales_today: "0", orders: 0, msc_pending: 0, open_conversations: 0, human_handoffs: 0 }, notifications: [] }); if (url.includes("/system/workspaces/")) return json({ workspace: "test", items: [], total: 0, offset: 0, limit: 50 }); return json([]); });
}
export function renderApp(path = "/") { window.location.hash = `#${path}`; const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); return render(<QueryClientProvider client={client}><PreferencesProvider><FeatureProvider><HashRouter><App /></HashRouter></FeatureProvider></PreferencesProvider></QueryClientProvider>); }
