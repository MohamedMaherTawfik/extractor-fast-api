import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  Download,
  ExternalLink,
  FileSpreadsheet,
  Grid2X2,
  List,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { DetailDrawer } from "../../../components/DetailDrawer";
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from "../../../components/States";
import { StatusBadge } from "../../../components/StatusBadge";
import { socialInventoryApi as client } from "../api/socialInventoryApi";
import { socialIntelligenceApi } from "../api/socialIntelligenceApi";
import { ContentAnalysisView } from "../components/ContentAnalysisView";
import { CreatorIntelligenceView } from "../components/CreatorIntelligenceView";
import type { CreateSource, Platform, SocialItem } from "../types";

const terminal = new Set(["succeeded", "partial", "failed", "cancelled"]);
const platforms: Platform[] = [
  "instagram",
  "tiktok",
  "facebook",
  "youtube",
  "x",
  "linkedin",
];
const count = (value?: number | null) =>
  value == null ? "—" : value.toLocaleString();

function AddSourceDialog({
  open,
  close,
  maxItems = 500,
  maxComments = 100,
}: {
  open: boolean;
  close: () => void;
  maxItems?: number;
  maxComments?: number;
}) {
  const cache = useQueryClient();
  const [form, setForm] = useState<CreateSource>({
    source_url: "",
    provider: "apify",
    max_items: 100,
    include_comments: false,
    max_comments_per_post: 25,
  });
  const [validation, setValidation] = useState("");
  const create = useMutation({
    mutationFn: client.createSource,
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["social"] });
      close();
    },
  });
  if (!open) return null;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setValidation("");
    try {
      const url = new URL(form.source_url);
      if (url.protocol !== "https:")
        throw new Error("Use a public HTTPS social URL.");
      if (form.max_items < 1 || form.max_items > maxItems)
        throw new Error(`Items must be between 1 and ${maxItems}.`);
      create.mutate(form);
    } catch (error) {
      setValidation(error instanceof Error ? error.message : "Invalid URL");
    }
  };
  return (
    <div
      className="social-modal"
      role="dialog"
      aria-modal="true"
      aria-label="Add social source"
    >
      <form className="panel" onSubmit={submit}>
        <header>
          <div>
            <span className="eyebrow">PUBLIC DATA ONLY</span>
            <h2>Start inventory</h2>
          </div>
          <button type="button" className="icon-button" onClick={close}>
            <X />
          </button>
        </header>
        <label>
          Account, page, or channel URL
          <input
            aria-label="Social URL"
            type="url"
            required
            placeholder="https://www.instagram.com/example/"
            value={form.source_url}
            onChange={(e) => setForm({ ...form, source_url: e.target.value })}
          />
        </label>
        <div className="social-form-grid">
          <label>
            Platform
            <select
              aria-label="Platform"
              value={form.platform || ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  platform: (e.target.value || undefined) as
                    | Platform
                    | undefined,
                })
              }
            >
              <option value="">Auto detect</option>
              {platforms.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </label>
          <label>
            Provider
            <select value={form.provider} disabled>
              <option>apify</option>
            </select>
          </label>
          <label>
            Maximum items
            <input
              aria-label="Maximum items"
              type="number"
              min="1"
              max={maxItems}
              value={form.max_items}
              onChange={(e) =>
                setForm({ ...form, max_items: Number(e.target.value) })
              }
            />
          </label>
          <label>
            From
            <input
              type="date"
              value={form.date_from || ""}
              onChange={(e) =>
                setForm({ ...form, date_from: e.target.value || undefined })
              }
            />
          </label>
          <label>
            To
            <input
              type="date"
              value={form.date_to || ""}
              onChange={(e) =>
                setForm({ ...form, date_to: e.target.value || undefined })
              }
            />
          </label>
          <label className="social-check">
            <input
              type="checkbox"
              checked={form.include_comments}
              onChange={(e) =>
                setForm({ ...form, include_comments: e.target.checked })
              }
            />{" "}
            Include comments
          </label>
          {form.include_comments && (
            <label>
              Comments per post
              <input
                type="number"
                min="0"
                max={maxComments}
                value={form.max_comments_per_post}
                onChange={(e) =>
                  setForm({
                    ...form,
                    max_comments_per_post: Number(e.target.value),
                  })
                }
              />
            </label>
          )}
        </div>
        {(validation || create.error) && (
          <p className="inline-error">
            {validation || (create.error as Error).message}
          </p>
        )}
        <footer>
          <button type="button" className="button ghost" onClick={close}>
            Cancel
          </button>
          <button className="button primary" disabled={create.isPending}>
            {create.isPending ? "Starting…" : "Start inventory"}
          </button>
        </footer>
      </form>
    </div>
  );
}

export default function SocialInventoryPage() {
  const cache = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState(params.get("tab") || "overview");
  const [dialog, setDialog] = useState(false);
  const [grid, setGrid] = useState(params.get("view") === "grid");
  const [selected, setSelected] = useState<SocialItem>();
  const [selectedUuids, setSelectedUuids] = useState<string[]>([]);
  const [report, setReport] = useState<Record<string, unknown>>();

  const analyzeBatchMutation = useMutation({
    mutationFn: () => socialIntelligenceApi.analyzeBatch(selectedUuids),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["social"] });
      setSelectedUuids([]);
    },
  });

  const toggleSelect = (uuid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedUuids((prev) =>
      prev.includes(uuid) ? prev.filter((id) => id !== uuid) : [...prev, uuid]
    );
  };
  const runs = useQuery({
    queryKey: ["social", "runs"],
    queryFn: client.runs,
    refetchInterval: (query) =>
      query.state.data?.some((run) => !terminal.has(run.status)) ? 2000 : false,
  });
  const capabilities = useQuery({
    queryKey: ["social", "capabilities"],
    queryFn: client.capabilities,
  });
  const overview = useQuery({
    queryKey: ["social", "overview"],
    queryFn: client.overview,
  });
  const sources = useQuery({
    queryKey: ["social", "sources"],
    queryFn: client.sources,
  });
  const offset = Number(params.get("offset") || 0);
  const limit = 50;
  const filters = useMemo(
    () => ({
      offset,
      limit,
      platform: params.get("platform") || undefined,
      source_id: params.get("source") || undefined,
      content_type: params.get("type") || undefined,
      keyword: params.get("q") || undefined,
      min_engagement: params.get("engagement") || undefined,
      sort: params.get("sort") || "newest",
    }),
    [params, offset],
  );
  const items = useQuery({
    queryKey: ["social", "items", filters],
    queryFn: () => client.items(filters),
  });
  const sync = useMutation({
    mutationFn: client.sync,
    onSuccess: () => cache.invalidateQueries({ queryKey: ["social"] }),
  });
  const cancel = useMutation({
    mutationFn: client.cancel,
    onSuccess: () => cache.invalidateQueries({ queryKey: ["social", "runs"] }),
  });
  const retry = useMutation({
    mutationFn: client.retry,
    onSuccess: () => cache.invalidateQueries({ queryKey: ["social", "runs"] }),
  });
  const research = useMutation({
    mutationFn: client.research,
    onSuccess: setReport,
  });
  useEffect(() => {
    if (runs.data?.some((run) => !terminal.has(run.status))) {
      cache.invalidateQueries({ queryKey: ["social", "overview"] });
      cache.invalidateQueries({ queryKey: ["social", "items"] });
      cache.invalidateQueries({ queryKey: ["social", "sources"] });
    }
  }, [runs.data, cache]);
  const change = (key: string, value?: string) => {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    if (key !== "offset") next.delete("offset");
    setParams(next);
  };
  const changeTab = (value: string) => {
    setTab(value);
    change("tab", value);
  };
  return (
    <section className="social-inventory-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">SOCIAL MEDIA INVENTORY</span>
          <h1>Public content, normalized</h1>
          <p>Durable account inventories powered by backend-only providers.</p>
        </div>
        <button className="button primary" onClick={() => setDialog(true)}>
          <Plus size={15} />
          Add source
        </button>
      </header>
      <nav className="social-tabs">
        {["overview", "sources", "content", "intelligence", "runs", "research"].map((value) => (
          <button
            key={value}
            className={tab === value ? "active" : ""}
            onClick={() => changeTab(value)}
          >
            {value}
          </button>
        ))}
      </nav>
      {tab === "overview" &&
        (overview.isLoading ? (
          <LoadingState />
        ) : overview.isError ? (
          <ErrorState error={overview.error} retry={() => overview.refetch()} />
        ) : (
          <>
            <div className="metric-grid social-metrics">
              {[
                ["Sources", overview.data?.sources],
                ["Posts", overview.data?.items],
                ["Views", overview.data?.total_views],
                ["Engagement", overview.data?.total_engagement],
                ["Problem runs", overview.data?.problem_runs],
                [
                  "Last sync",
                  overview.data?.last_sync
                    ? new Date(overview.data.last_sync).toLocaleString()
                    : "Never",
                ],
              ].map(([label, value]) => (
                <article className="metric-card" key={String(label)}>
                  <span>{label}</span>
                  <strong>
                    {typeof value === "number" ? count(value) : value}
                  </strong>
                </article>
              ))}
            </div>
            <section className="panel social-capabilities">
              <div className="panel-heading">
                <h2>Provider readiness</h2>
              </div>
              {capabilities.data ? (
                <>
                  <p>
                    <StatusBadge
                      value={
                        capabilities.data.apify.enabled
                          ? "APIFY_READY"
                          : "APIFY_SETUP_REQUIRED"
                      }
                    />{" "}
                    {capabilities.data.apify.reason}
                  </p>
                  <p>
                    <StatusBadge
                      value={
                        capabilities.data.jev.enabled
                          ? "JEV_READY"
                          : "JEV_DISABLED"
                      }
                    />{" "}
                    {capabilities.data.jev.reason}
                  </p>
                </>
              ) : (
                <LoadingState />
              )}
            </section>
          </>
        ))}
      {tab === "sources" && (
        <section className="panel">
          <div className="panel-heading">
            <h2>Sources</h2>
          </div>
          {sources.isLoading ? (
            <LoadingState />
          ) : sources.isError ? (
            <ErrorState error={sources.error} />
          ) : sources.data?.length ? (
            <div className="social-source-grid">
              {sources.data.map((source) => (
                <article key={source.uuid}>
                  <header>
                    <StatusBadge value={source.platform} />
                    <StatusBadge value={source.status} />
                  </header>
                  <h3>
                    {source.display_name ||
                      source.username ||
                      source.canonical_url.split("/").filter(Boolean).at(-1)}
                  </h3>
                  <a
                    href={source.canonical_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {source.canonical_url}
                    <ExternalLink size={12} />
                  </a>
                  <p>
                    Last sync:{" "}
                    {source.last_synced_at
                      ? new Date(source.last_synced_at).toLocaleString()
                      : "Never"}
                  </p>
                  <button
                    className="button secondary"
                    disabled={sync.isPending}
                    onClick={() => sync.mutate(source.uuid)}
                  >
                    <RefreshCw size={14} />
                    Sync
                  </button>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No social sources"
              action={
                <button
                  className="button primary"
                  onClick={() => setDialog(true)}
                >
                  Add the first source
                </button>
              }
            />
          )}
        </section>
      )}
      {tab === "content" && (
        <section className="panel">
          <div className="panel-heading">
            <h2>Content</h2>
            <div className="social-view">
              <button
                className={!grid ? "active" : ""}
                onClick={() => {
                  setGrid(false);
                  change("view");
                }}
              >
                <List />
              </button>
              <button
                className={grid ? "active" : ""}
                onClick={() => {
                  setGrid(true);
                  change("view", "grid");
                }}
              >
                <Grid2X2 />
              </button>
            </div>
          </div>
          <div className="social-filters">
            <label>
              <Search size={14} />
              <input
                aria-label="Content keyword"
                placeholder="Search caption or title"
                value={params.get("q") || ""}
                onChange={(e) => change("q", e.target.value)}
              />
            </label>
            <select
              aria-label="Platform filter"
              value={params.get("platform") || ""}
              onChange={(e) => change("platform", e.target.value)}
            >
              <option value="">All platforms</option>
              {platforms.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
            <select
              aria-label="Source filter"
              value={params.get("source") || ""}
              onChange={(e) => change("source", e.target.value)}
            >
              <option value="">All sources</option>
                  {sources.data?.map((source) => (
                    <option key={source.uuid} value={source.id}>
                  {source.display_name || source.platform}
                </option>
              ))}
            </select>
            <select
              aria-label="Sort content"
              value={params.get("sort") || "newest"}
              onChange={(e) => change("sort", e.target.value)}
            >
              {[
                "newest",
                "oldest",
                "most_viewed",
                "most_liked",
                "most_commented",
              ].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
            <input
              type="number"
              min="0"
              placeholder="Min engagement"
              value={params.get("engagement") || ""}
              onChange={(e) => change("engagement", e.target.value)}
            />
          </div>
          {selectedUuids.length > 0 && (
            <div className="batch-toolbar">
              <span>{selectedUuids.length} selected</span>
              <div className="batch-actions">
                <button
                  className="button primary small"
                  disabled={analyzeBatchMutation.isPending}
                  onClick={() => analyzeBatchMutation.mutate()}
                >
                  <Sparkles size={13} />
                  {analyzeBatchMutation.isPending
                    ? "Queuing..."
                    : `Analyze Selected (${selectedUuids.length})`}
                </button>
                <a
                  className="button secondary small"
                  href={socialIntelligenceApi.streamExportUrl()}
                  download
                >
                  <Download size={13} />
                  Export Selected (.XLSX)
                </a>
                <button
                  className="button ghost small"
                  onClick={() => setSelectedUuids([])}
                >
                  Clear
                </button>
              </div>
            </div>
          )}
          {items.isLoading ? (
            <LoadingState />
          ) : items.isError ? (
            <ErrorState error={items.error} retry={() => items.refetch()} />
          ) : items.data?.items.length ? (
            <div
              className={grid ? "social-content-grid" : "social-content-list"}
            >
              {items.data.items.map((item) => (
                <article key={item.uuid} onClick={() => setSelected(item)}>
                  {typeof item.media?.[0]?.thumbnail_url === "string" && (
                    <img
                      src={item.media[0].thumbnail_url}
                      alt=""
                      loading="lazy"
                      referrerPolicy="no-referrer"
                    />
                  )}
                  <div>
                    <header>
                      <input
                        type="checkbox"
                        className="item-checkbox"
                        checked={selectedUuids.includes(item.uuid)}
                        onClick={(e) => toggleSelect(item.uuid, e)}
                        onChange={() => {}}
                        aria-label={`Select ${item.title || item.caption || item.uuid}`}
                      />
                      <StatusBadge value={item.platform} />
                      <span>
                        {item.published_at
                          ? new Date(item.published_at).toLocaleDateString()
                          : "Unknown date"}
                      </span>
                    </header>
                    <h3>{item.title || item.caption || "Untitled content"}</h3>
                    <footer>
                      <span>Views {count(item.metrics?.views)}</span>
                      <span>Likes {count(item.metrics?.likes)}</span>
                      <a
                        href={item.canonical_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                      >
                        Original <ExternalLink size={11} />
                      </a>
                    </footer>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="No imported content" />
          )}
          {items.data && (
            <div className="pagination">
              <span>{items.data.total} items</span>
              <div>
                <button
                  disabled={!offset}
                  onClick={() =>
                    change("offset", String(Math.max(0, offset - limit)))
                  }
                >
                  Previous
                </button>
                <button
                  disabled={offset + limit >= items.data.total}
                  onClick={() => change("offset", String(offset + limit))}
                >
                  Next
                </button>
              </div>
            </div>
          )}
          <div className="social-export">
            <a
              className="button primary"
              href={socialIntelligenceApi.streamExportUrl()}
              download
              title="Export complete 14-sheet Excel intelligence report"
            >
              <FileSpreadsheet size={15} />
              Full 14-Sheet Excel Intelligence Report (.xlsx)
            </a>
            <Download size={15} />
            {(["csv", "xlsx", "json"] as const).map((format) => (
              <a
                className="button secondary"
                key={format}
                href={client.exportUrl(format, filters)}
                download
              >
                {format.toUpperCase()}
              </a>
            ))}
          </div>
        </section>
      )}
      {tab === "intelligence" && (
        <section className="panel" style={{ padding: "16px" }}>
          <CreatorIntelligenceView />
        </section>
      )}
      {tab === "runs" && (
        <section className="panel">
          <div className="panel-heading">
            <h2>Durable runs</h2>
          </div>
          {runs.isLoading ? (
            <LoadingState />
          ) : runs.data?.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Progress</th>
                    <th>Created</th>
                    <th>Warnings / error</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.data.map((run) => (
                    <tr key={run.uuid}>
                      <td>
                        <StatusBadge value={run.status} />
                      </td>
                      <td>
                        {run.items_seen}/{run.max_items} · +{run.items_created}{" "}
                        / ↻{run.items_updated}
                      </td>
                      <td>{new Date(run.created_at).toLocaleString()}</td>
                      <td>
                        {run.error_message ||
                          (run.warnings?.length
                            ? `${run.warnings.length} warnings`
                            : "—")}
                      </td>
                      <td>
                        {!terminal.has(run.status) ? (
                          <button onClick={() => cancel.mutate(run.uuid)}>
                            Cancel
                          </button>
                        ) : (
                          run.status !== "succeeded" && (
                            <button onClick={() => retry.mutate(run.uuid)}>
                              Retry
                            </button>
                          )
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="No inventory runs" />
          )}
        </section>
      )}
      {tab === "research" && (
        <section className="panel social-research">
          <div className="panel-heading">
            <h2>Jev research</h2>
            <StatusBadge
              value={
                capabilities.data?.jev.enabled
                  ? "AVAILABLE"
                  : "LOCAL_RUNNER_REQUIRED"
              }
            />
          </div>
          {!capabilities.data?.jev.enabled ? (
            <EmptyState
              title="Jev local runner is unavailable"
              detail={
                capabilities.data?.jev.reason ||
                "Enable and configure JEV_SOCIAL_COMMAND on this machine."
              }
            />
          ) : (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                const data = new FormData(event.currentTarget);
                research.mutate({
                  source_uuid: String(data.get("source")),
                  goal: String(data.get("goal")),
                  target_count: Number(data.get("count")),
                });
              }}
            >
              <select name="source" required>
                <option value="">Choose source</option>
                {sources.data?.map((source) => (
                  <option value={source.uuid} key={source.uuid}>
                    {source.platform} · {source.canonical_url}
                  </option>
                ))}
              </select>
              <textarea
                name="goal"
                required
                minLength={3}
                placeholder="Research goal"
              />
              <input
                name="count"
                type="number"
                min="1"
                max="100"
                defaultValue="20"
              />
              <button className="button primary">Run read-only research</button>
            </form>
          )}
          {report && <pre>{JSON.stringify(report, null, 2)}</pre>}
        </section>
      )}
      <AddSourceDialog
        open={dialog}
        close={() => setDialog(false)}
        maxItems={capabilities.data?.limits.max_items}
        maxComments={capabilities.data?.limits.max_comments_per_post}
      />
      <DetailDrawer
        item={selected as unknown as Record<string, unknown> | undefined}
        title={selected?.title || selected?.caption?.slice(0, 45) || "Content details"}
        onClose={() => setSelected(undefined)}
      >
        {selected && (
          <ContentAnalysisView item={selected} onClose={() => setSelected(undefined)} />
        )}
      </DetailDrawer>
    </section>
  );
}
