import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { json, mockBackend, renderApp } from "./renderApp";

const connector = (platform: string) => ({ platform, configured: false, name_discovery: "API_REQUIRED", direct_url: "SUPPORTED", profile_enumeration: "MANUAL_URL_REQUIRED", content_sampling: "API_REQUIRED", detail: "Direct public profile URLs are accepted." });
const run = { run_uid: "CDRUN_1", status: "PARTIAL", stage: "PARTIAL", progress_percent: 100, input_count: 2, platforms: ["youtube", "instagram"], options: {}, processed: 2, matched: 1, review_required: 1, failed: 0, warnings: [], errors: [], created_at: new Date().toISOString(), jobs: [{ job_uid: "CDJOB_1", input_value: "Ahmed Example", normalized_input: "ahmed example", input_kind: "NAME", platforms: ["youtube", "instagram"], status: "PARTIAL", stage: "PARTIAL", progress_percent: 100, attempt: 1, checkpoint: { current_creator: "Ahmed Example" }, candidate_count: 1 }] };
const candidate = { candidate_uid: "CDC_1", platform: "youtube", display_name: "Ahmed Example", username: "ahmed", profile_url: "https://www.youtube.com/@ahmed", public_bio: "Educational technology reviews", followers: 800000, discovery_source: "youtube_data_api_v3", confidence: 96, classification: "CONFIRMED", review_status: "PENDING", profile_data: {}, provenance: [], retrieved_at: new Date().toISOString() };
const creator = { profile_uid: "CDP_1", creator_uid: "CR_000001", name: "Ahmed Example", normalized_name: "ahmed example", niche: "Technology / Gadgets", industry: "Technology", main_platform: "youtube", main_platform_confidence: .95, platforms_found: ["youtube", "instagram"], youtube_url: "https://www.youtube.com/@ahmed", instagram_url: "https://www.instagram.com/ahmed", content_mechanism_style: "Reviews and comparisons", influence_size: "+800K", influence_size_numeric: 800000, kpi_impact: "Strong product-review influence", start_year: 2018, start_year_confidence: 1, match_confidence: 96, analysis_status: "COMPLETED", possible_duplicate: false, created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
const detail = { unified_profile: creator, platform_accounts: [{ platform: "youtube" }], content_samples: [{ title: "Phone review" }], analysis: [{ status: "COMPLETED" }], match_evidence: [{ signal: "normalized_name" }], provenance: [{ source: "youtube_data_api_v3" }], history: [{ action: "ANALYZED" }] };
const metaStatus = { configured: false, app_id_configured: false, app_secret_configured: false, access_token_configured: false, graph_api_version: "v26.0", token_status: "NOT_CONFIGURED", token_message: "Meta credentials are not fully configured.", granted_permissions: [], last_validation: new Date().toISOString(), instagram: { status: "NOT_CONFIGURED", message: "Credentials required", account_configured: false, required_permissions: [], missing_permissions: [] }, facebook: { status: "NOT_CONFIGURED", message: "Credentials required", account_configured: false, required_permissions: [], missing_permissions: [] } };

function discoveryBackend() {
  return mockBackend((url, init) => {
    if (url.includes("/creator-discovery/meta/validate")) return json(metaStatus);
    if (url.includes("/creator-discovery/meta/status")) return json(metaStatus);
    if (url.includes("/creator-discovery/connectors")) return json(["youtube", "facebook", "instagram", "tiktok", "snapchat", "linkedin", "x"].map(connector));
    if (url.includes("/creator-discovery/industries")) return json([{ code: "technology", name: "Technology", aliases: [] }]);
    if (url.endsWith("/creator-discovery/runs") && init?.method === "POST") return json(run, 201);
    if (url.includes("/creator-discovery/runs/CDRUN_1")) return json(run);
    if (url.includes("/creator-discovery/runs")) return json({ items: [run], total: 1, offset: 0, limit: 50 });
    if (url.includes("/creator-discovery/candidates/CDC_1/confirm")) return json(detail);
    if (url.includes("/creator-discovery/candidates")) return json({ items: [candidate], total: 1, offset: 0, limit: 50 });
    if (url.includes("/creator-discovery/creators/CDP_1")) return json(detail);
    if (url.includes("/creator-discovery/creators")) return json({ items: [creator], total: 1, offset: 0, limit: 50 });
    if (url.includes("/creators/export")) return Promise.resolve(new Response("xlsx", { status: 200 }));
  });
}

describe("creator discovery studio", () => {
  it("starts a multiline multi-platform discovery", async () => {
    discoveryBackend(); renderApp("/creator-discovery"); const user = userEvent.setup();
    expect(await screen.findByRole("heading", { name: "Creator Discovery" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Bulk Discovery" }));
    await user.type(screen.getByLabelText("Creator Name(s)"), "Ahmed Example\nSara Example");
    await user.click(screen.getByRole("checkbox", { name: /TikTok/i }));
    await user.click(screen.getByRole("button", { name: "START BULK DISCOVERY" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/creator-discovery/runs"), expect.objectContaining({ method: "POST", body: expect.stringContaining("Ahmed Example") })));
    expect((await screen.findAllByText(/CDRUN_1/)).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Creator Intelligence workbook/ })).toBeInTheDocument();
  }, 15_000);

  it("renders the candidate review and confirms an identity", async () => {
    discoveryBackend(); renderApp("/creator-discovery"); const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Creator Discovery" });
    await user.click(screen.getByRole("tab", { name: "Review Matches" }));
    expect(await screen.findByText("Ahmed Example")).toBeInTheDocument();
    expect(screen.getByText("96%")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /THIS IS THE ACCOUNT/ }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/candidates/CDC_1/confirm"), expect.objectContaining({ method: "POST" })));
  });

  it("opens creator evidence detail and exports the exact workbook surface", async () => {
    const createObjectURL = vi.fn(() => "blob:creator"); Object.defineProperty(URL, "createObjectURL", { value: createObjectURL, configurable: true });
    Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), configurable: true }); vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    discoveryBackend(); renderApp("/creator-discovery"); const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Creator Discovery" });
    await user.click(screen.getByRole("tab", { name: "Creators" }));
    await user.click(await screen.findByText("Ahmed Example"));
    expect(await screen.findByRole("dialog", { name: "CR_000001" })).toBeInTheDocument();
    expect(screen.getByText("Platform Accounts (1)")).toBeInTheDocument();
    await user.clear(screen.getByLabelText("Edit niche"));
    await user.type(screen.getByLabelText("Edit niche"), "Technology / Reviews");
    await user.click(screen.getByRole("button", { name: "Save manual corrections" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/creator-discovery/creators/CDP_1"), expect.objectContaining({ method: "PATCH", body: expect.stringContaining("Technology / Reviews") })));
    await user.click(screen.getByRole("button", { name: "Close detail" }));
    await user.click(screen.getByRole("tab", { name: "Export" }));
    await user.click(screen.getByRole("button", { name: "Standard XLSX" }));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalled());
  });

  it("shows secret-safe Meta connection status and validates on demand", async () => {
    discoveryBackend(); renderApp("/creator-discovery"); const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Creator Discovery" });
    await user.click(screen.getByRole("tab", { name: "Connections" }));
    expect(await screen.findByText("Meta / Instagram / Facebook")).toBeInTheDocument();
    expect(screen.getAllByText("NO").length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByText(/APP_SECRET=/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /VALIDATE CONNECTION/ }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/creator-discovery/meta/validate"), expect.objectContaining({ method: "POST" })));
  });
});
