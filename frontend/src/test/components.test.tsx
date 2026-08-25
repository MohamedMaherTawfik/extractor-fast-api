import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DataTable } from "../components/DataTable";
import { StatusBadge } from "../components/StatusBadge";

it("renders operational statuses with semantic tone", () => { render(<><StatusBadge value="READY" /><StatusBadge value="BLOCKED" /></>); expect(screen.getByText("READY")).toHaveClass("success"); expect(screen.getByText("BLOCKED")).toHaveClass("danger"); });
it("supports keyboard row selection and pagination controls", async () => { const selected = vi.fn(); render(<DataTable rows={[{ id: 1, sku: "SKU_1", status: "ACTIVE", total: "10" }]} total={1} offset={0} limit={50} onPage={vi.fn()} onSelect={selected} />); const row = screen.getByText("SKU_1").closest("tr")!; row.focus(); await userEvent.keyboard("{Enter}"); expect(selected).toHaveBeenCalled(); expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled(); });
