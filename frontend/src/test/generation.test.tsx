import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { json, mockBackend, renderApp } from "./renderApp";

it("blocks generation until the backend contract is READY", async () => {
  mockBackend((url) => url.includes("/generation-contracts/") ? json({ contract_uid: "GCON_TEST", version: 1, status: "not_ready", recipe_id: 1, recipe_version: 1, payload: { blockers: ["missing evidence"] }, evaluation_uid: "EVAL_1" }) : undefined);
  renderApp("/generation"); const user = userEvent.setup(); await user.click(await screen.findByRole("button", { name: "Create" }));
  await user.type(screen.getByLabelText("Contract UID or ID"), "GCON_TEST"); await user.click(screen.getByRole("button", { name: "Inspect readiness" }));
  expect(await screen.findByRole("button", { name: /Generation blocked/ })).toBeDisabled();
});

it("enables job creation for the lowercase READY value returned by the backend", async () => {
  mockBackend((url) => url.includes("/generation-contracts/") ? json({ contract_uid: "GCON_READY", version: 2, status: "ready", recipe_id: 1, recipe_version: 3, payload: { qa: ["rights", "accessibility"] }, evaluation_uid: "EVAL_2" }) : undefined);
  renderApp("/generation"); const user = userEvent.setup(); await user.click(await screen.findByRole("button", { name: "Create" }));
  await user.type(screen.getByLabelText("Contract UID or ID"), "GCON_READY"); await user.click(screen.getByRole("button", { name: "Inspect readiness" }));
  expect(await screen.findByRole("button", { name: "Create queued job" })).toBeEnabled();
});
