import { screen } from "@testing-library/react";
import { json, mockBackend, renderApp } from "./renderApp";

test("renders the ComfyUI AI Video Studio workflow", async () => {
  mockBackend((url) => {
    if (url.includes("/video-studio/config")) return json({ version: "1", provider: "comfyui", comfyui_configured: true, default_model: "wan_video", models: [{ model_id: "wan_video", display_name: "Wan Video", enabled: true, fps: 16, max_duration_seconds: 20, aspect_ratios: ["9:16"] }], recipes: [{ recipe_id: "EMY_CHARACTER_V1", name: "EMY Character V1", camera_style: "cinematic", lighting: "soft", colors: "warm", environment: "studio", realism_level: "photoreal", motion_style: "smooth" }], worker: { concurrency: 1, active_jobs: [] } });
    if (url.includes("/video-studio/characters")) return json([]);
    if (url.includes("/video-studio/jobs")) return json([]);
    return undefined;
  });
  renderApp("/video-studio");
  expect(await screen.findByRole("heading", { name: "AI Video Studio" })).toBeInTheDocument();
  expect(screen.getByText("Identity reference")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Generate video/i })).toBeDisabled();
  expect(screen.getByText("Wan Video")).toBeInTheDocument();
});
