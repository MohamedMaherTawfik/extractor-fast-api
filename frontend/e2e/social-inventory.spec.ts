import { expect, test } from "@playwright/test";

test("inventory survives refresh, filters, details, export, and resync", async ({ page }) => {
  let sourceCreated = false;
  let poll = 0;
  let likes = 2;
  const now = new Date().toISOString();
  const source = { id: 1, uuid: "source-1", provider: "apify", platform: "instagram", source_url: "https://www.instagram.com/demo/", canonical_url: "https://instagram.com/demo/", status: "active", sync_enabled: false, last_synced_at: now, created_at: now, updated_at: now };
  const run = () => ({ uuid: "run-1", source_id: 1, provider: "apify", status: poll < 2 ? "queued" : poll < 3 ? "running" : poll < 4 ? "importing" : "succeeded", request_id: "request-1", max_items: 3, include_comments: false, items_seen: poll >= 4 ? 1 : 0, items_created: poll >= 4 ? 1 : 0, items_updated: 0, comments_created: 0, attempts: 0, created_at: now, updated_at: now });
  const item = () => ({ uuid: "item-1", source_id: 1, platform: "instagram", external_id: "post-1", canonical_url: "https://instagram.com/p/post-1/", content_type: "post", caption: "Launch day inventory", author: { username: "demo" }, media: [], metrics: { views: 10, likes, comments: 1, shares: 0, saves: null }, hashtags: ["launch"], mentions: [], provider: "apify", first_observed_at: now, last_observed_at: now });
  await page.route("http://127.0.0.1:8000/**", async (route) => {
    const request = route.request(); const url = new URL(request.url()); const path = url.pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/system/capabilities") return json({ app: { name: "EMY", version: "1", environment: "test" }, modules: { content: { enabled: true }, social_inventory: { enabled: true } }, features: {}, privacy_mode: "LOCAL_ONLY", realtime: { transport: "adaptive_polling", recommended_interval_seconds: 1 } });
    if (path === "/system/health-detail") return json({ backend: "ONLINE", database: "ONLINE" });
    if (path === "/system/notifications") return json([]);
    if (path === "/social-inventory/capabilities") return json({ apify: { enabled: true, platforms: { instagram: true, tiktok: false, facebook: false, youtube: false, x: false, linkedin: false } }, jev: { enabled: false, reason: "disabled" }, limits: { max_items: 500, max_comments_per_post: 100 } });
    if (path === "/social-inventory/overview") return json({ sources: sourceCreated ? 1 : 0, items: sourceCreated && poll >= 4 ? 1 : 0, total_views: sourceCreated && poll >= 4 ? 10 : 0, total_engagement: sourceCreated && poll >= 4 ? likes + 1 : 0, problem_runs: 0, last_sync: sourceCreated && poll >= 4 ? now : null });
    if (path === "/social-inventory/sources" && request.method() === "POST") { sourceCreated = true; poll = 1; return json({ source, run: run() }, 201); }
    if (path === "/social-inventory/sources") return json(sourceCreated ? [source] : []);
    if (path.endsWith("/sync")) { poll = 3; likes = 5; return json(run(), 202); }
    if (path === "/social-inventory/runs") { if (sourceCreated) poll += 1; return json(sourceCreated ? [run()] : []); }
    if (path === "/social-inventory/items") return json({ items: sourceCreated && poll >= 4 ? [item()] : [], total: sourceCreated && poll >= 4 ? 1 : 0, offset: 0, limit: 50 });
    if (path === "/social-inventory/exports/csv") return route.fulfill({ status: 200, contentType: "text/csv", headers: { "Content-Disposition": "attachment; filename=social-inventory-instagram.csv" }, body: "platform,caption\ninstagram,Launch day inventory\n" });
    return json([]);
  });
  await page.goto("/#/social-inventory");
  await expect(page.getByText("Public content, normalized")).toBeVisible();
  await page.getByRole("button", { name: "Add source" }).click();
  await page.getByLabel("Social URL").fill("https://www.instagram.com/demo/");
  await page.getByRole("button", { name: "Start inventory" }).click();
  await page.getByRole("button", { name: "runs" }).click();
  await expect(page.getByText("succeeded", { exact: true })).toBeVisible({ timeout: 12_000 });
  await page.reload();
  await page.getByRole("button", { name: "content" }).click();
  await expect(page.getByText("Launch day inventory")).toBeVisible();
  await page.getByLabel("Content keyword").fill("Launch");
  await expect(page).toHaveURL(/q=Launch/);
  await page.getByText("Launch day inventory").click();
  await expect(page.getByText("item-1")).toBeVisible();
  await page.getByRole("button", { name: "Close detail" }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "CSV" }).click();
  expect((await download).suggestedFilename()).toBe("social-inventory-instagram.csv");
  await page.getByRole("button", { name: "sources" }).click();
  await page.getByRole("button", { name: "Sync" }).click();
  await page.getByRole("button", { name: "content" }).click();
  await expect(page.getByText("Launch day inventory")).toHaveCount(1);
});
