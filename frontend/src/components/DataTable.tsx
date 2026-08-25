import { ChevronLeft, ChevronRight } from "lucide-react";
import { StatusBadge } from "./StatusBadge";

const important = ["status", "priority", "severity", "sku", "product_name_en", "product_name_ar", "business_name", "customer_code", "order_number", "invoice_number", "conversation_uid", "job_uid", "asset_uid", "recipe_uid", "rule_code", "total", "available"];
function display(value: unknown) {
  if (value == null) return <span className="muted">—</span>;
  if (typeof value === "object") return <span className="muted">Structured data</span>;
  return String(value);
}

export function DataTable({ rows, total, offset, limit, onPage, onSelect }: { rows: Record<string, unknown>[]; total: number; offset: number; limit: number; onPage: (offset: number) => void; onSelect: (row: Record<string, unknown>) => void }) {
  const keys = rows.length ? Object.keys(rows[0]).filter((key) => important.includes(key)).slice(0, 7) : [];
  if (keys.length < 4 && rows.length) for (const key of Object.keys(rows[0])) if (!keys.includes(key) && !["id", "metadata", "payload", "before", "after"].includes(key)) { keys.push(key); if (keys.length >= 7) break; }
  return <div className="table-wrap"><table><thead><tr>{keys.map((key) => <th key={key}>{key.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={String(row.id ?? index)} tabIndex={0} onClick={() => onSelect(row)} onKeyDown={(e) => e.key === "Enter" && onSelect(row)}>{keys.map((key) => <td key={key}>{/status|priority|severity/i.test(key) ? <StatusBadge value={row[key]} /> : display(row[key])}</td>)}</tr>)}</tbody></table>
    <footer className="pagination"><span>{total ? `${offset + 1}–${Math.min(offset + limit, total)} / ${total}` : "0 records"}</span><div><button className="icon-button" aria-label="Previous page" disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - limit))}><ChevronLeft /></button><button className="icon-button" aria-label="Next page" disabled={offset + limit >= total} onClick={() => onPage(offset + limit)}><ChevronRight /></button></div></footer>
  </div>;
}
