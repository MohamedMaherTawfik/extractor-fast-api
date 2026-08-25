import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockBackend, renderApp } from "./renderApp";

describe("application shell", () => {
  it("discovers features, renders operational navigation, and hides unavailable leads", async () => {
    mockBackend(); renderApp();
    expect(await screen.findByText("Good morning, Operator.")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toBeInTheDocument();
    expect(screen.queryByText("Leads")).not.toBeInTheDocument();
    expect(screen.getByText("LOCAL_ONLY")).toBeInTheDocument();
  });
  it("opens the command palette with Ctrl+K and switches RTL to LTR", async () => {
    mockBackend(); renderApp(); const user = userEvent.setup();
    await screen.findByText("Good morning, Operator."); await user.keyboard("{Control>}k{/Control}");
    expect(screen.getByRole("dialog", { name: "Command palette" })).toBeInTheDocument();
    await user.keyboard("{Escape}"); await user.click(screen.getByRole("button", { name: "Language" }));
    await waitFor(() => expect(document.documentElement.dir).toBe("ltr"));
  });
  it("keeps diagnostics usable when the backend is offline", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("offline")); renderApp();
    expect(await screen.findByText("Backend unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Language" })).toBeInTheDocument();
  });
});
