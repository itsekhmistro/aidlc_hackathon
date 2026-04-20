import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MessageThread from "../components/MessageThread";
import { api } from "../lib/api";
import type { RoomPublic } from "../lib/types";

vi.mock("../lib/api");
const mockApi = vi.mocked(api);

function baseRoom(overrides: Partial<RoomPublic> = {}): RoomPublic {
  return {
    id: "r-1",
    name: "general",
    display_name: "general",
    description: null,
    visibility: "public",
    owner_id: "u-1",
    is_personal: false,
    created_at: "",
    member_count: 2,
    ...overrides,
  };
}

function renderThread(room: RoomPublic) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MessageThread room={room} currentUserId="u-1" />
    </QueryClientProvider>,
  );
}

describe("MessageThread header title", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // useMessages issues an infinite query against /api/rooms/:id/messages.
    mockApi.get = vi.fn().mockResolvedValue({ messages: [], next_cursor: null });
    // jsdom doesn't implement scrollIntoView; MessageThread calls it on mount.
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("renders a regular room as `# <name>`", () => {
    renderThread(baseRoom());
    expect(screen.getByText(/^#\s*general\s*$/)).toBeInTheDocument();
  });

  it("renders a DM as `@ <counterpart> (email)` from display_name", () => {
    renderThread(
      baseRoom({
        is_personal: true,
        name: "__dm__:0a691fcb-21d0-4c25-9ca0-4829dc1949b0:d8617c24-a53e-4971-82bc-6fe121e84b81",
        display_name: "jack (jack@test.com)",
      }),
    );
    expect(
      screen.getByText(/^@\s*jack \(jack@test\.com\)\s*$/),
    ).toBeInTheDocument();
    // Canonical internal name must not leak into the header.
    expect(screen.queryByText(/__dm__/)).toBeNull();
  });
});
