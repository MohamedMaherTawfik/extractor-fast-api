import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { json, mockBackend, renderApp } from "./renderApp";

const capability = { apify: { enabled: true, platforms: { instagram: true, tiktok: false, facebook: false, youtube: false, x: false, linkedin: false } }, jev: { enabled: false, reason: "JEV_SOCIAL_ENABLED is false" }, limits: { max_items: 500, max_comments_per_post: 100 } };
function socialBackend() {
  return mockBackend((url) => {
    if (url.includes("/social-inventory/capabilities")) return json(capability);
    if (url.includes("/social-inventory/overview")) return json({ sources: 1, items: 2, total_views: 10, total_engagement: 3, problem_runs: 1 });
    if (url.includes("/social-inventory/sources")) return json([{ id: 1, uuid: "source-1", provider: "apify", platform: "instagram", source_url: "https://instagram.com/demo/", canonical_url: "https://instagram.com/demo/", status: "active", sync_enabled: false, created_at: new Date().toISOString(), updated_at: new Date().toISOString() }]);
    if (url.includes("/social-inventory/runs")) return json([{ uuid: "run-1", source_id: 1, provider: "apify", status: "failed", request_id: "r", max_items: 3, include_comments: false, items_seen: 1, items_created: 1, items_updated: 0, comments_created: 0, attempts: 1, error_message: "Provider unavailable", created_at: new Date().toISOString(), updated_at: new Date().toISOString() }]);
    if (url.includes("/social-inventory/items")) return json({ items: [], total: 0, offset: 0, limit: 50 });
  });
}

test("renders overview, failed state, and Jev capability", async () => {
  socialBackend(); renderApp("/social-inventory");
  expect(await screen.findByText("Public content, normalized")).toBeInTheDocument();
  expect(await screen.findByText("Provider readiness")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "runs" }));
  expect(await screen.findByText("Provider unavailable")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "research" }));
  expect(await screen.findByText("Jev local runner is unavailable")).toBeInTheDocument();
});

test("validates add-source URL before sending", async () => {
  const fetch = socialBackend(); renderApp("/social-inventory");
  await screen.findByText("Public content, normalized");
  await userEvent.click(screen.getByRole("button", { name: "Add source" }));
  await userEvent.type(screen.getByLabelText("Social URL"), "http://instagram.com/demo");
  await userEvent.click(screen.getByRole("button", { name: "Start inventory" }));
  expect(await screen.findByText("Use a public HTTPS social URL.")).toBeInTheDocument();
  await waitFor(() => expect(fetch.mock.calls.filter(([input]) => String(input).endsWith("/social-inventory/sources"))).toHaveLength(1));
});

test("stores content filters in the URL query", async () => {
  socialBackend(); renderApp("/social-inventory?tab=content");
  await userEvent.type(await screen.findByLabelText("Content keyword"), "launch");
  await waitFor(() => expect(window.location.hash).toContain("q=launch"));
});
