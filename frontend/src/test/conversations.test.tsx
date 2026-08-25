import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConversationsPage from "../routes/ConversationsPage";
import { json } from "./renderApp";

it("keeps an approved outbound message available for manual send", async () => {
  const requests: Array<{ url: string; method: string }> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    requests.push({ url, method });
    if (url.includes("/messages/7/send")) return json({ status: "SENT" });
    if (url.includes("/conversations/conv-1")) return json({
      id: 1, conversation_uid: "conv-1", status: "OPEN", channel: "WEBSITE_CHAT", priority: "NORMAL",
      contact: { contact_uid: "contact-1", display_name: "Customer" }, state: {},
      messages: [{ id: 7, message_uid: "msg-7", direction: "OUTBOUND", text: "Approved reply", status: "APPROVED" }],
    });
    if (url.includes("/conversations?limit=100")) return json([{ id: 1, conversation_uid: "conv-1", status: "OPEN", channel: "WEBSITE_CHAT", priority: "NORMAL" }]);
    return json([]);
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><ConversationsPage /></QueryClientProvider>);
  const sendButton = await screen.findByRole("button", { name: "Send" });
  expect(sendButton).toBeEnabled();
  await userEvent.click(sendButton);
  await waitFor(() => expect(requests).toContainEqual(expect.objectContaining({ url: expect.stringContaining("/messages/7/send"), method: "POST" })));
});
