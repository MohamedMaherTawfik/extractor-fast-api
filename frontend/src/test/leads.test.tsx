import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { normalizeLeadRunPlan } from "../api/leads";
import { json, mockBackend, renderApp } from "./renderApp";

const source = { source_uid: "SRC_OVERTURE", name: "Overture Maps Places", type: "BULK_DISCOVERY", enabled: true, configured: true, bulk_support: true, query_support: true, geo_support: "BBOX_STAC", credentials_required: false, freshness: "MONTHLY", terms_status: "REVIEWED_OPEN", storage_policy: "RAW_JSONL_AND_CANONICAL", rate_limit: "CLOUD_RANGE_READS", status: "READY" };
const control = { workbook: { available: false, status: "NOT_FOUND_USING_CONFIG_DEFAULTS", placement: "data/imports/lead_control/EMY_Egypt_Lead_Acquisition_OS_v1.xlsx", sheet_counts: {}, errors: [] }, segments: [{ category_id: "pharmacies", name: "Pharmacies", tier: 1, buyer_type: "RETAILER", terms: ["pharmacy", "صيدلية"] }], keywords: { set: "approved", count: 2, languages: ["ar", "en"] }, governorates: [{ id: "cairo", name: "Cairo", name_ar: "القاهرة", bbox: [31.1, 29.8, 31.75, 30.35], density: "HIGH" }], country: { code: "EG", name: "Egypt", bbox: [], polygon: [] }, run_modes: ["FULL_SCAN", "INCREMENTAL"] };
const run = { dry_run: false as const, run_uid: "LRUN_1", name: "UI run", mode: "FULL_SCAN", sources: ["SRC_OVERTURE"], geography: {}, segments: ["pharmacies"], keywords: ["pharmacy"], status: "RUNNING", planned_jobs: 1, processed: 20, found: 4, unique_count: 3, duplicates: 1, errors: 0, current_source: "SRC_OVERTURE", current_governorate: "cairo", current_category: "MULTI_SEGMENT", warnings: [], progress_percent: 50, created_at: new Date().toISOString(), jobs: [{ job_uid: "LJOB_1", source_uid: "SRC_OVERTURE", governorate: "cairo", category: "MULTI_SEGMENT", status: "RUNNING", processed: 20, found: 4, unique_count: 3, duplicates: 1 }] };
const lead = { lead_uid: "LEAD_1", business: "Real Pharmacy", category: "pharmacies", fit_class: "A", governorate: "cairo", city: "Cairo", phone: "+201000000000", website: "https://example.test", source: "SRC_OVERTURE", score: 78, freshness: new Date().toISOString(), verification: "UNVERIFIED" };

describe("data acquisition desktop", () => {
  it("normalizes undefined and empty dry-run arrays", () => {
    expect(normalizeLeadRunPlan({ dry_run: true, keyword_count: 431, planned_jobs: 11475 })).toEqual({
      dry_run: true,
      enabled_sources: [],
      governorates: [],
      segments: [],
      keyword_count: 431,
      planned_jobs: 11475,
      missing_credentials: [],
      warnings: [],
    });
    expect(normalizeLeadRunPlan({
      dry_run: true,
      enabled_sources: null,
      governorates: [],
      segments: null,
      missing_credentials: [],
      warnings: null,
    })).toMatchObject({ enabled_sources: [], governorates: [], segments: [], missing_credentials: [], warnings: [] });
  });

  it("loads a workbook-backed New Run and safely renders a partial dry-run response", async () => {
    const workbookControl = {
      ...control,
      active_command_source: "WORKBOOK",
      query_matrix_rows: 11475,
      enabled_query_jobs: 11475,
      workbook: {
        available: true,
        status: "VALID",
        active_command_source: "WORKBOOK",
        filename: "EMY_Egypt_Lead_Acquisition_OS_v1.xlsx",
        placement: "data/imports/lead_control/EMY_Egypt_Lead_Acquisition_OS_v1.xlsx",
        sheet_counts: { "Keyword Master": 431, "Lead Segments": 50, "Egypt Coverage": 27, "Query Matrix": 11475 },
        query_matrix_rows: 11475,
        enabled_query_jobs: 11475,
        errors: [],
      },
      keywords: { set: "approved", count: 431, languages: ["AR", "EN"] },
      segments: Array.from({ length: 50 }, (_, index) => ({ category_id: `segment_${index}`, name: `Segment ${index}`, tier: 1, buyer_type: "RETAILER", terms: [] })),
      governorates: Array.from({ length: 27 }, (_, index) => ({ id: `gov_${index}`, name: `Governorate ${index}`, name_ar: `Governorate ${index}`, bbox: [], density: "HIGH" })),
    };
    mockBackend((url, init) => {
      if (url.includes("/lead-sources")) return json([source]);
      if (url.includes("/lead-control")) return json(workbookControl);
      if (url.endsWith("/lead-runs") && init?.method === "POST") return json({ dry_run: true, keyword_count: 431, planned_jobs: 11475 }, 201);
      if (url.includes("/lead-runs")) return json({ items: [], total: 0, offset: 0, limit: 25 });
    });
    renderApp("/data-acquisition");
    const user = userEvent.setup();
    expect(await screen.findByText("Active command source: WORKBOOK")).toBeInTheDocument();
    expect(screen.getByText("Approved keywords").parentElement).toHaveTextContent("Approved keywords431");
    expect(screen.getByText("Segments").parentElement).toHaveTextContent("Segments50");
    expect(screen.getByText("Governorates").parentElement).toHaveTextContent("Governorates27");
    expect(screen.getByText("Query jobs").parentElement).toHaveTextContent("Query jobs11475");
    await user.click(screen.getByRole("tab", { name: "New Run" }));
    expect(await screen.findByRole("heading", { name: "New acquisition run" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dry Run" }));
    expect(await screen.findByText("Missing credentials")).toBeInTheDocument();
    expect(screen.getByText("None")).toBeInTheDocument();
  });

  it("preflights a new run, starts it, and exposes progress controls", async () => {
    mockBackend((url, init) => {
      if (url.includes("/lead-stats")) return json({ total_leads: 3, classes: { "A+": 1, A: 2, B: 0, C: 0 }, active_runs: 1, sources: 1, errors: 0 });
      if (url.includes("/lead-sources")) return json([source]);
      if (url.includes("/lead-control")) return json(control);
      if (url.endsWith("/lead-runs") && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        return json(body.dry_run ? { dry_run: true, enabled_sources: ["SRC_OVERTURE"], governorates: ["cairo"], segments: ["pharmacies"], keyword_count: 2, planned_jobs: 1, missing_credentials: [], warnings: [] } : run, 201);
      }
      if (url.includes("/lead-runs/LRUN_1/pause")) return json({ ...run, status: "PAUSED" });
      if (url.includes("/lead-runs/LRUN_1")) return json(run);
      if (url.includes("/lead-runs")) return json({ items: [run], total: 1, offset: 0, limit: 25 });
      if (url.includes("/leads")) return json({ items: [], total: 0, offset: 0, limit: 50 });
    });
    renderApp("/data-acquisition"); const user = userEvent.setup();
    expect(await screen.findByRole("heading", { name: "Data Acquisition" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "New Run" }));
    await waitFor(() => expect(screen.getByLabelText("Run Name")).toHaveValue("Egypt nationwide business lead collection"));
    await user.click(screen.getByRole("button", { name: "Dry Run" }));
    expect(await screen.findByText("Planned jobs")).toBeInTheDocument();
    expect(screen.getByText("Approved Keyword Master")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "START" }));
    expect(await screen.findByText("Live progress")).toBeInTheDocument();
    expect(await screen.findByText("50%")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Pause" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/lead-runs/LRUN_1/pause"), expect.objectContaining({ method: "POST" })));
  });

  it("uses server-side result filters, opens detail, and requests export", async () => {
    const createObjectURL = vi.fn(() => "blob:test"); const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { value: createObjectURL, configurable: true });
    Object.defineProperty(URL, "revokeObjectURL", { value: revokeObjectURL, configurable: true });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    mockBackend((url, init) => {
      if (url.includes("/lead-stats")) return json({ total_leads: 1, classes: { "A+": 0, A: 1, B: 0, C: 0 }, active_runs: 0, sources: 1, errors: 0 });
      if (url.includes("/lead-sources")) return json([source]);
      if (url.includes("/lead-control")) return json(control);
      if (url.includes("/leads/export") && init?.method === "POST") return Promise.resolve(new Response("lead_uid\nLEAD_1", { status: 200 }));
      if (url.includes("/leads/LEAD_1")) return json({ canonical: lead, source_records: [{ source_uid: "SRC_OVERTURE" }], dedupe_history: [], provenance: [{ run_id: "LRUN_1" }] });
      if (url.includes("/leads")) return json({ items: [lead], total: 1, offset: 0, limit: 50 });
      if (url.includes("/lead-runs")) return json({ items: [], total: 0, offset: 0, limit: 25 });
    });
    renderApp("/data-acquisition"); const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Data Acquisition" });
    await user.click(screen.getByRole("tab", { name: "Results" }));
    expect(await screen.findByText("Real Pharmacy")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Class Filter"), "A");
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("fit_class=A"), expect.anything()));
    await user.click(screen.getByText("Real Pharmacy"));
    expect(await screen.findByRole("dialog", { name: "LEAD_1" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close detail" }));
    await user.click(screen.getByRole("button", { name: "CSV" }));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalled());
  });
});
