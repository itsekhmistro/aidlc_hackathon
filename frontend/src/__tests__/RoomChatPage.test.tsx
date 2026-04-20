import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import RoomChatPage from "../pages/RoomChatPage";
import { api } from "../lib/api";
import { incrementUnread, useUnreadCount } from "../lib/unreadStore";
import type { RoomPublic, UserPublic } from "../lib/types";

vi.mock("../lib/api");
const mockApi = vi.mocked(api);

// MessageThread pulls in jsdom-unfriendly scroll behaviors and extra queries.
// For page-level tests, a stub that just renders the room name is enough.
vi.mock("../components/MessageThread", () => ({
  __esModule: true,
  default: ({ room, currentUserId }: { room: RoomPublic; currentUserId: string }) => (
    <div data-testid="thread">
      <span data-testid="thread-room"># {room.name}</span>
      <span data-testid="thread-user">{currentUserId}</span>
    </div>
  ),
}));

const mockRoom: RoomPublic = {
  id: "room-42",
  name: "general",
  description: "the main room",
  visibility: "public",
  owner_id: "u-1",
  is_personal: false,
  created_at: "2026-04-20T10:00:00Z",
  member_count: 3,
};

const mockUser: UserPublic = {
  id: "u-1",
  username: "alice",
  email: "alice@example.com",
  created_at: "2026-04-20T10:00:00Z",
};

function setupApi(overrides: Partial<{ me: UserPublic; myRooms: RoomPublic[]; roomDetail: RoomPublic }> = {}) {
  mockApi.get = vi.fn().mockImplementation((path: string) => {
    if (path === "/api/auth/me") return Promise.resolve(overrides.me ?? mockUser);
    if (path === "/api/rooms/mine") return Promise.resolve(overrides.myRooms ?? [mockRoom]);
    if (path === "/api/rooms/room-42") return Promise.resolve(overrides.roomDetail ?? mockRoom);
    return Promise.resolve([]);
  });
  mockApi.post = vi.fn().mockResolvedValue(undefined);
}

function renderAtRoute(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/chat/rooms/:roomId" element={<RoomChatPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function UnreadProbe({ roomId }: { roomId: string }) {
  const count = useUnreadCount(roomId);
  return <span data-testid="unread">{count}</span>;
}

describe("RoomChatPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupApi();
  });

  it("renders the thread for the active room (shows room name)", async () => {
    renderAtRoute("/chat/rooms/room-42");
    await waitFor(() => {
      expect(screen.getByTestId("thread-room").textContent).toBe("# general");
    });
  });

  it("calls POST /api/unread/:roomId/mark-read when the route mounts", async () => {
    renderAtRoute("/chat/rooms/room-42");
    await waitFor(() => {
      expect(mockApi.post).toHaveBeenCalledWith("/api/unread/room-42/mark-read");
    });
  });

  it("clears the unread count in the store on mount", async () => {
    incrementUnread("room-42");
    incrementUnread("room-42");

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/chat/rooms/room-42"]}>
          <Routes>
            <Route
              path="/chat/rooms/:roomId"
              element={
                <>
                  <RoomChatPage />
                  <UnreadProbe roomId="room-42" />
                </>
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
    await waitFor(() => {
      expect(screen.getByTestId("unread").textContent).toBe("0");
    });
  });

  it("falls back to GET /api/rooms/:id when the room is not in my rooms", async () => {
    setupApi({ myRooms: [] });
    renderAtRoute("/chat/rooms/room-42");
    await waitFor(() => {
      expect(mockApi.get).toHaveBeenCalledWith("/api/rooms/room-42");
    });
    await waitFor(() => {
      expect(screen.getByTestId("thread-room").textContent).toBe("# general");
    });
  });

  it("passes the current user id to the thread", async () => {
    renderAtRoute("/chat/rooms/room-42");
    await waitFor(() => {
      expect(screen.getByTestId("thread-user").textContent).toBe("u-1");
    });
  });
});
