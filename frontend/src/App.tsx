import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { LoadingState } from "./components/States";
import { RouteErrorBoundary } from "./app/RouteErrorBoundary";
import {
  ApprovalsPage, AssetsPage, AuditPage, ContentPage, CustomerServicePage, CustomersPage, IntelligencePage,
  InventoryPage, MscPage, PatternRecipePage, ProductsPage, RulesPage, SalesPage, SuppliersPage,
} from "./routes/ModulePages";

const DashboardPage = lazy(() => import("./routes/DashboardPage"));
const GenerationPage = lazy(() => import("./routes/GenerationPage"));
const ConversationsPage = lazy(() => import("./routes/ConversationsPage"));
const CalendarPage = lazy(() => import("./routes/CalendarPage"));
const AnalyticsPage = lazy(() => import("./routes/AnalyticsPage"));
const SettingsPage = lazy(() => import("./routes/SettingsPage"));

const Guard = ({ children }: { children: React.ReactNode }) => <RouteErrorBoundary><Suspense fallback={<LoadingState />}>{children}</Suspense></RouteErrorBoundary>;
export default function App() {
  return <Routes><Route element={<AppShell />}>
    <Route index element={<Guard><DashboardPage /></Guard>} />
    <Route path="content" element={<Guard><ContentPage /></Guard>} /><Route path="intelligence" element={<Guard><IntelligencePage /></Guard>} />
    <Route path="patterns" element={<Guard><PatternRecipePage /></Guard>} /><Route path="rules" element={<Guard><RulesPage /></Guard>} />
    <Route path="generation" element={<Guard><GenerationPage /></Guard>} /><Route path="assets" element={<Guard><AssetsPage /></Guard>} />
    <Route path="calendar" element={<Guard><CalendarPage /></Guard>} /><Route path="products" element={<Guard><ProductsPage /></Guard>} />
    <Route path="customers" element={<Guard><CustomersPage /></Guard>} /><Route path="sales" element={<Guard><SalesPage /></Guard>} />
    <Route path="inventory" element={<Guard><InventoryPage /></Guard>} /><Route path="suppliers" element={<Guard><SuppliersPage /></Guard>} />
    <Route path="msc" element={<Guard><MscPage /></Guard>} /><Route path="conversations" element={<Guard><ConversationsPage /></Guard>} />
    <Route path="customer-service" element={<Guard><CustomerServicePage /></Guard>} /><Route path="approvals" element={<Guard><ApprovalsPage /></Guard>} />
    <Route path="analytics" element={<Guard><AnalyticsPage /></Guard>} /><Route path="audit" element={<Guard><AuditPage /></Guard>} />
    <Route path="settings" element={<Guard><SettingsPage /></Guard>} /><Route path="*" element={<Navigate to="/" replace />} />
  </Route></Routes>;
}
