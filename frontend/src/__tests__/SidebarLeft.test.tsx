import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SidebarLeft from "../components/SidebarLeft";
import { api } from "../lib/api";
import type { FriendshipPublic, RoomPublic } from "../lib/types";

vi.mock("../lib/api");
const mockApi = vi.mocked(api);

function friend(overrides: Partial<FriendshipPublic> = {}): FriendshipPublic {
  return {
    id: "f-1",
    requester_id: "u-1",
    requester_username: "me",
    addressee_id: "u-2",
    addressee_username: "bob",
    status: "accepted",
    message: null,
    created_at: "",
    updated_at: "",
    ...overrides,
  };
}

function room(overrides: Partial<RoomPublic> = {}): RoomPublic {
  return {
    id: "r-1",
    name: "general",
    description: null,
    visibility: "public",
    owner_id: "u-1",
    is_personal: false,
    created_at: "",
    member_count: 3,
    ...overrides,
  };
}

function renderSidebar(initialPath: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/chat" element={<SidebarLeft />} />
          <Route path="/chat/rooms/:roomId" element={<SidebarLeft />} />
          <Route path="/chat/dm/:userId" element={<SidebarLeft />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function stubApi({
  friends = [friend()],
  rooms = [room()],
  requests = [] as FriendshipPublic[],
}: {
  friends?: FriendshipPublic[];
  rooms?: RoomPublic[];
  requests?: FriendshipPublic[];
} = {}) {
  mockApi.get = vi.fn(async (path: string) => {
    if (path === "/api/auth/me")
      return {
        id: "u-1",
        username: "me",
        email: "me@test.com",
        created_at: "",
      } as unknown as never;
    if (path === "/api/friends") return friends as unknown as never;
    if (path === "/api/friends/requests/incoming") return requests as unknown as never;
    if (path === "/api/rooms/mine") return rooms as unknown as never;
    return [] as unknown as never;
  });
  mockApi.post = vi.fn().mockResolvedValue(undefined);
}

describe("SidebarLeft accordion", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    stubApi();
  });

  it("keeps both sections expanded on /chat (no active room)", async () => {
    renderSidebar("/chat");
    await waitFor(() => {
      expect(screen.getByText("bob")).toBeVisible();
      expect(screen.getByText("general")).toBeVisible();
    });
    expect(
      screen.getByRole("button", { name: /contacts/i }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /rooms/i })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("auto-collapses Contacts when a regular room is active", async () => {
    renderSidebar("/chat/rooms/r-1");
    await waitFor(() => {
      expect(screen.getByText("general")).toBeVisible();
    });
    expect(
      screen.getByRole("button", { name: /contacts/i }),
    ).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("bob")).toBeNull();
    expect(screen.getByRole("button", { name: /rooms/i })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("auto-collapses Rooms when on a DM route", async () => {
    renderSidebar("/chat/dm/u-2");
    await waitFor(() => {
      expect(screen.getByText("bob")).toBeVisible();
    });
    expect(screen.getByRole("button", { name: /rooms/i })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByText("general")).toBeNull();
    expect(
      screen.getByRole("button", { name: /contacts/i }),
    ).toHaveAttribute("aria-expanded", "true");
  });

  it("lets the user re-expand a collapsed section manually", async () => {
    const user = userEvent.setup();
    renderSidebar("/chat/rooms/r-1");
    await waitFor(() =>
      expect(screen.queryByText("bob")).toBeNull(),
    );
    await user.click(screen.getByRole("button", { name: /contacts/i }));
    expect(
      screen.getByRole("button", { name: /contacts/i }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("bob")).toBeVisible();
  });

  it("lets the user collapse Rooms while a room is active", async () => {
    const user = userEvent.setup();
    renderSidebar("/chat/rooms/r-1");
    await waitFor(() => expect(screen.getByText("general")).toBeVisible());
    await user.click(screen.getByRole("button", { name: /rooms/i }));
    expect(screen.getByRole("button", { name: /rooms/i })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByText("general")).toBeNull();
  });
});
