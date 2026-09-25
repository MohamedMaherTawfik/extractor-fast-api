import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { json, mockBackend, renderApp } from "./renderApp";

test("renders the product image controls, presets, uploads, and queued submit", async () => {
  let submitted = false;
  mockBackend((url, init) => {
    if (url.includes("/image-studio/capabilities")) return json({ comfyui: "READY", generation_available: true, base_url: "http://127.0.0.1:8188", installation: "C:/ComfyUI", paths: {}, api: { reachable: true, api_available: true, checks: {} }, runtime_models: { checkpoints: ["verified.safetensors"], unets: [], text_encoders: [], vaes: [], generation_model_files_detected: true }, models: [{ model_id: "verified", display_name: "Verified", workflow_file: "image.json", required_custom_nodes: [] }], custom_nodes: [], supported_workflows: ["image.json"], missing_requirements: [] });
    if (url.includes("/image-studio/presets")) return json([{ preset_id: "E_COMMERCE", name: "E Commerce", settings: { camera_angle: "Front", shot_type: "Product Hero", pose: "Product on Table", background: "Pure Studio", lighting: "Product Commercial", visual_style: "E-commerce", aspect_ratio: "1:1", number_of_images: 1 } }]);
    if (url.includes("/image-studio/jobs") && init?.method === "POST") { submitted = true; return json({ job_id: "IJOB_1", status: "QUEUED" }, 202); }
    if (url.includes("/image-studio/jobs")) return json(submitted ? [{ job_id: "IJOB_1", status: "QUEUED", progress: 0, stage: "Queued", settings: { visual_style: "E-commerce" }, prompt: "", negative_prompt: "", output_images: [], created_at: new Date().toISOString() }] : []);
    return undefined;
  });
  renderApp("/image-studio");
  expect(await screen.findByRole("heading", { name: "AI Product Image Studio" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "E Commerce" }));
  expect((screen.getByLabelText("Camera angle") as HTMLSelectElement).value).toBe("Front");
  const character = new File(["character"], "character.png", { type: "image/png" });
  const product = new File(["product"], "product.png", { type: "image/png" });
  fireEvent.change(screen.getByLabelText("Upload Character Image"), { target: { files: [character] } });
  fireEvent.change(screen.getByLabelText("Upload Product Image"), { target: { files: [product] } });
  const submit = screen.getByRole("button", { name: /Generate images/i });
  expect(submit).toBeEnabled();
  await userEvent.click(submit);
  expect(await screen.findByText("0% · 0 images")).toBeInTheDocument();
});
