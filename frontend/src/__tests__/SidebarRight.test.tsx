import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SidebarRight from "../components/SidebarRight";
import { api } from "../lib/api";
import { setBulkPresence } from "../lib/presenceStore";
import type { RoomMemberPublic } from "../lib/types";

vi.mock("../lib/api");
const mockApi = vi.mocked(api);

function renderSidebarRight(roomId: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SidebarRight roomId={roomId} />
    </QueryClientProvider>
  );
}

function member(overrides: Partial<RoomMemberPublic>): RoomMemberPublic {
  return {
    user_id: "u-1",
    username: "alice",
    role: "member",
    presence_status: "offline",
    joined_at: "2026-04-20T10:00:00Z",
    ...overrides,
  };
}

describe("SidebarRight", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches members from /api/rooms/:id/members", async () => {
    mockApi.get = vi.fn().mockResolvedValue([]);
    renderSidebarRight("room-1");
    await waitFor(() => {
      expect(mockApi.get).toHaveBeenCalledWith("/api/rooms/room-1/members");
    });
  });

  it("renders all members", async () => {
    mockApi.get = vi.fn().mockResolvedValue([
      member({ user_id: "u-1", username: "alice" }),
      member({ user_id: "u-2", username: "bob" }),
    ]);
    renderSidebarRight("room-1");
    await waitFor(() => {
      expect(screen.getByText("alice")).toBeInTheDocument();
      expect(screen.getByText("bob")).toBeInTheDocument();
    });
  });

  it("shows a presence dot per member", async () => {
    mockApi.get = vi.fn().mockResolvedValue([
      member({ user_id: "u-1", username: "alice", presence_status: "online" }),
    ]);
    const { container } = renderSidebarRight("room-1");
    await waitFor(() => {
      expect(screen.getByText("alice")).toBeInTheDocument();
    });
    // Presence dot renders a span with bg-green-500 / bg-yellow-400 / bg-gray-300
    const dot = container.querySelector(".bg-green-500");
    expect(dot).toBeTruthy();
  });

  it("sorts members: online, afk, offline, then alphabetical", async () => {
    mockApi.get = vi.fn().mockResolvedValue([
      member({ user_id: "u-1", username: "zeta", presence_status: "offline" }),
      member({ user_id: "u-2", username: "bob", presence_status: "online" }),
      member({ user_id: "u-3", username: "alice", presence_status: "afk" }),
      member({ user_id: "u-4", username: "carol", presence_status: "online" }),
    ]);
    const { container } = renderSidebarRight("room-1");
    await waitFor(() => {
      expect(screen.getByText("bob")).toBeInTheDocument();
    });
    // The rendered order should be: bob (online), carol (online), alice (afk), zeta (offline)
    const rows = container.querySelectorAll(".flex.items-center.gap-2.px-3.py-1\\.5");
    const names = Array.from(rows).map((r) => within(r as HTMLElement).getByText(/.+/).textContent);
    expect(names[0]).toBe("bob");
    expect(names[1]).toBe("carol");
    expect(names[2]).toBe("alice");
    expect(names[3]).toBe("zeta");
  });

  it("renders owner and admin role badges", async () => {
    mockApi.get = vi.fn().mockResolvedValue([
      member({ user_id: "u-1", username: "alice", role: "owner" }),
      member({ user_id: "u-2", username: "bob", role: "admin" }),
      member({ user_id: "u-3", username: "carol", role: "member" }),
    ]);
    renderSidebarRight("room-1");
    await waitFor(() => {
      expect(screen.getByText("alice")).toBeInTheDocument();
    });
    expect(screen.getByText("owner")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
  });

  it("uses live presence when available (overrides API snapshot)", async () => {
    mockApi.get = vi.fn().mockResolvedValue([
      member({ user_id: "u-1", username: "alice", presence_status: "offline" }),
    ]);
    // Mark u-1 online in the live store BEFORE render
    setBulkPresence([{ user_id: "u-1", status: "online" }]);
    const { container } = renderSidebarRight("room-1");
    await waitFor(() => {
      expect(screen.getByText("alice")).toBeInTheDocument();
    });
    expect(container.querySelector(".bg-green-500")).toBeTruthy();
    // Reset so other tests aren't affected
    setBulkPresence([{ user_id: "u-1", status: "offline" }]);
  });

  it("shows member count header", async () => {
    mockApi.get = vi.fn().mockResolvedValue([
      member({ user_id: "u-1", username: "alice" }),
      member({ user_id: "u-2", username: "bob" }),
    ]);
    renderSidebarRight("room-1");
    await waitFor(() => {
      expect(screen.getByText(/Members \(2\)/)).toBeInTheDocument();
    });
  });
});
