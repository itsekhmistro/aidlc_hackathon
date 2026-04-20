import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import RoomsPage from "../pages/RoomsPage";
import { api } from "../lib/api";
import type { RoomPublic } from "../lib/types";

vi.mock("../lib/api");
const mockApi = vi.mocked(api);

function renderRoomsPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <RoomsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function room(overrides: Partial<RoomPublic>): RoomPublic {
  return {
    id: "r-1",
    name: "general",
    description: null,
    visibility: "public",
    owner_id: "u-1",
    is_personal: false,
    created_at: "2026-04-20T10:00:00Z",
    member_count: 3,
    ...overrides,
  };
}

function makeGet(mine: RoomPublic[], publicRooms: RoomPublic[]) {
  return vi.fn().mockImplementation((path: string) => {
    if (path === "/api/rooms/mine") return Promise.resolve(mine);
    return Promise.resolve(publicRooms);
  });
}

describe("RoomsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches public rooms on mount", async () => {
    mockApi.get = makeGet([], [room({})]);
    renderRoomsPage();
    await waitFor(() => expect(screen.getByText(/# general/)).toBeInTheDocument());
    expect(mockApi.get).toHaveBeenCalledWith("/api/rooms");
  });

  it("filters rooms by search query", async () => {
    mockApi.get = makeGet([], []);
    renderRoomsPage();
    await userEvent.type(screen.getByLabelText(/search rooms/i), "dev");
    await waitFor(() => {
      expect(mockApi.get).toHaveBeenCalledWith("/api/rooms?search=dev");
    });
  });

  it("shows a Join button and calls POST /api/rooms/:id/join", async () => {
    mockApi.get = makeGet([], [room({ id: "r-42", name: "random" })]);
    mockApi.post = vi.fn().mockResolvedValue(undefined);
    renderRoomsPage();
    const joinBtn = await screen.findByRole("button", { name: /join/i });
    await userEvent.click(joinBtn);
    await waitFor(() => {
      expect(mockApi.post).toHaveBeenCalledWith("/api/rooms/r-42/join");
    });
  });

  it("shows Open button (not Join) for rooms the user is already a member of", async () => {
    mockApi.get = makeGet([room({ id: "r-1" })], [room({ id: "r-1" })]);
    renderRoomsPage();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /open/i })).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /join/i })).not.toBeInTheDocument();
  });

  it("shows an empty-state message when no rooms match", async () => {
    mockApi.get = makeGet([], []);
    renderRoomsPage();
    await waitFor(() => {
      expect(screen.getByText(/No rooms match/i)).toBeInTheDocument();
    });
  });
});
