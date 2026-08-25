export function StatusBadge({ value }: { value: unknown }) {
  const text = String(value ?? "UNKNOWN");
  const tone = /fail|block|critical|overdue|offline|out_of_stock/i.test(text) ? "danger" : /warn|pending|review|low|degraded|waiting/i.test(text) ? "warning" : /complete|active|online|approved|ready|sent|delivered|in_stock/i.test(text) ? "success" : "neutral";
  return <span className={`status-badge ${tone}`}>{text.replaceAll("_", " ")}</span>;
}
