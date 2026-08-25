import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import { WorkspacePage, type WorkspaceTab } from "../components/WorkspacePage";
import { FileDropzone } from "../components/FileDropzone";

const page = (title: string, subtitle: string, tabs: WorkspaceTab[], action?: React.ReactNode) => () => <WorkspacePage title={title} subtitle={subtitle} tabs={tabs} actions={action} />;

export const ContentPage = page("Content", "Collected content and analysis state from the canonical Content Master.", [
  { label: "Collected content", workspace: "content" }, { label: "Collection jobs", workspace: "collection-jobs" }, { label: "Analysis runs", workspace: "analysis" },
]);
export const IntelligencePage = page("Intelligence", "Observable analysis, Content DNA inputs, themes, hooks, formats, and evidence-backed patterns.", [
  { label: "Analysis", workspace: "analysis" }, { label: "Patterns", workspace: "patterns" }, { label: "Content", workspace: "content" },
]);
export const PatternRecipePage = page("Patterns & Recipes", "Explainable evidence and editable, versioned generation plans.", [
  { label: "Patterns", workspace: "patterns" }, { label: "Recipes", workspace: "recipes", description: "Select a recipe to inspect its structured plan and provenance." },
], <Link className="button primary" to="/rules"><Plus size={16} />Validate recipe</Link>);
export const RulesPage = page("Rules", "Versioned controls, evaluation evidence, dependencies, overrides, and human reviews.", [
  { label: "Rule registry", workspace: "rules" }, { label: "Human reviews", workspace: "rule-reviews" }, { label: "Rule audit", workspace: "rule-audit" },
]);
export const AssetsPage = page("Asset Library", "Generated image, video, audio, copy, document, accessibility, QA, rights, and provenance records.", [
  { label: "Assets", workspace: "assets" }, { label: "Generation jobs", workspace: "generation-jobs" },
]);
export const ProductsPage = page("Products", "Product Master, approved prices, inventory, sales context, supplier links, and version history.", [
  { label: "Products", workspace: "products" }, { label: "PriceBooks", workspace: "pricebooks" }, { label: "Inventory", workspace: "inventory" },
]);
export const CustomersPage = page("Customer 360", "Customer accounts with orders, invoices, payments, balance workflows, collections, delivery, and conversations.", [
  { label: "Customers", workspace: "customers" }, { label: "Orders", workspace: "orders" }, { label: "Invoices", workspace: "invoices" }, { label: "Payments", workspace: "payments" }, { label: "Collections", workspace: "collections" },
]);
export const SalesPage = page("Sales", "Backend-calculated orders, invoices, payments, collections, returns, and daily close.", [
  { label: "Orders", workspace: "orders" }, { label: "Invoices", workspace: "invoices" }, { label: "Payments", workspace: "payments" }, { label: "Collections", workspace: "collections" }, { label: "Daily close", workspace: "daily-close" },
], <button className="button primary"><Plus size={16} />Order draft</button>);
export const InventoryPage = page("Inventory", "Immutable stock movements, warehouse operations, transfers, stocktakes, and availability evidence.", [
  { label: "Movements", workspace: "inventory" }, { label: "Warehouses", workspace: "warehouses" }, { label: "Products", workspace: "products" },
]);
export const SuppliersPage = page("Suppliers & Purchases", "Supplier master, purchase orders, receipts, invoices, payments, and payables context.", [
  { label: "Suppliers", workspace: "suppliers" }, { label: "Purchases", workspace: "purchases" },
]);
export const MscPage = page("MSC Intake", "Staged file intake, extraction confidence, validation exceptions, approval, and atomic posting readiness.", [
  { label: "Batches", workspace: "msc" }, { label: "Validation review", workspace: "msc" }, { label: "Daily close", workspace: "daily-close" },
], <FileDropzone />);
export const CustomerServicePage = page("Customer Service", "Queues, handoffs, follow-ups, and reviewable AI-assisted operations.", [
  { label: "Conversation queue", workspace: "conversations" }, { label: "Human handoffs", workspace: "handoffs" }, { label: "Follow-ups", workspace: "followups" },
]);
export const ApprovalsPage = page("Approval Center", "Central review inbox for sales, rules, high-impact decisions, and operational gates.", [
  { label: "Sales approvals", workspace: "approvals" }, { label: "Rule reviews", workspace: "rule-reviews" }, { label: "High-risk messages", workspace: "conversations" },
]);
export const AuditPage = page("Unified Audit", "Paginated actor, domain, action, entity, source, reason, and before/after records.", [
  { label: "Sales audit", workspace: "audit" }, { label: "Rules audit", workspace: "rule-audit" },
]);
