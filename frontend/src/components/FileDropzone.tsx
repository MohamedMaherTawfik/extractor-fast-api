import { useRef, useState } from "react";
import { FileUp } from "lucide-react";

export function FileDropzone() {
  const input = useRef<HTMLInputElement>(null); const [names, setNames] = useState<string[]>([]);
  async function choose() {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({ multiple: true, directory: false, filters: [{ name: "MSC documents", extensions: ["png", "jpg", "jpeg", "pdf", "csv", "xlsx"] }] });
      const values = Array.isArray(selected) ? selected : selected ? [selected] : [];
      setNames(values.map((value) => String(value).replaceAll("\\", "/").split("/").pop() || "selected file"));
    } catch { input.current?.click(); }
  }
  return <div className="file-picker"><button className="button primary" onClick={choose}><FileUp size={16} />Choose intake files</button><input ref={input} hidden type="file" multiple accept=".png,.jpg,.jpeg,.pdf,.csv,.xlsx" onChange={(event) => setNames(Array.from(event.target.files || []).map((file) => file.name))} />{names.length > 0 && <span aria-live="polite">{names.length} file(s): {names.slice(0, 2).join(", ")}</span>}</div>;
}
