import React from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi, describe, it, expect, beforeEach } from "vitest";
import {
  useAcceptRoomInvitation,
  useDeclineRoomInvitation,
  useMyRoomInvitations,
  useMyRooms,
  usePersonalRoom,
  usePublicRooms,
} from "../hooks/useRooms";
import { api } from "../lib/api";
import type { RoomInvitationPublic, RoomPublic } from "../lib/types";

vi.mock("../lib/api");
const mockApi = vi.mocked(api);

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
  return { wrapper, qc };
}

const mockRoom: RoomPublic = {
  id: "room-1",
  name: "general",
  display_name: "general",
  description: null,
  visibility: "public",
  owner_id: "user-1",
  is_personal: false,
  created_at: "2026-04-20T10:00:00Z",
  member_count: 1,
};

describe("useMyRooms", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches /api/rooms/mine", async () => {
    mockApi.get = vi.fn().mockResolvedValueOnce([mockRoom]);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useMyRooms(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi.get).toHaveBeenCalledWith("/api/rooms/mine");
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].name).toBe("general");
  });

  it("returns empty array when no rooms", async () => {
    mockApi.get = vi.fn().mockResolvedValueOnce([]);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useMyRooms(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });
});

describe("usePublicRooms", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches /api/rooms without search parameter when no search given", async () => {
    mockApi.get = vi.fn().mockResolvedValueOnce([mockRoom]);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => usePublicRooms(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi.get).toHaveBeenCalledWith("/api/rooms");
    expect(result.current.data).toHaveLength(1);
  });

  it("fetches /api/rooms?search=test when search='test'", async () => {
    mockApi.get = vi.fn().mockResolvedValueOnce([mockRoom]);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => usePublicRooms("test"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi.get).toHaveBeenCalledWith("/api/rooms?search=test");
  });

  it("encodes special characters in search param", async () => {
    mockApi.get = vi.fn().mockResolvedValueOnce([]);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => usePublicRooms("my room"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi.get).toHaveBeenCalledWith("/api/rooms?search=my%20room");
  });

  it("returns multiple rooms", async () => {
    const room2 = { ...mockRoom, id: "room-2", name: "random" };
    mockApi.get = vi.fn().mockResolvedValueOnce([mockRoom, room2]);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => usePublicRooms(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(2);
  });
});

describe("usePersonalRoom", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls GET /api/personal-rooms/:userId", async () => {
    const fakeRoom: RoomPublic = { ...mockRoom, id: "room-dm-1", name: "__dm__:a:b", is_personal: true };
    mockApi.get = vi.fn().mockResolvedValue(fakeRoom);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => usePersonalRoom(), { wrapper });

    act(() => { result.current.mutate("user-456"); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi.get).toHaveBeenCalledWith("/api/personal-rooms/user-456");
    expect(result.current.data).toEqual(fakeRoom);
  });

  it("returns the room returned by the API", async () => {
    const fakeRoom: RoomPublic = { ...mockRoom, id: "room-dm-2", name: "__dm__:a:c", is_personal: true };
    mockApi.get = vi.fn().mockResolvedValue(fakeRoom);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => usePersonalRoom(), { wrapper });

    act(() => { result.current.mutate("user-789"); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.id).toBe("room-dm-2");
  });

  it("invalidates ['rooms','mine'] on success", async () => {
    const fakeRoom: RoomPublic = { ...mockRoom, id: "room-dm-3", name: "__dm__:a:d", is_personal: true };
    mockApi.get = vi.fn().mockResolvedValue(fakeRoom);
    const { wrapper, qc } = makeWrapper();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => usePersonalRoom(), { wrapper });

    act(() => { result.current.mutate("user-101"); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["rooms", "mine"] })
    );
  });

  it("caches the room detail under ['rooms','detail',room.id] on success", async () => {
    const fakeRoom: RoomPublic = { ...mockRoom, id: "room-dm-4", name: "__dm__:a:e", is_personal: true };
    mockApi.get = vi.fn().mockResolvedValue(fakeRoom);
    const { wrapper, qc } = makeWrapper();
    const { result } = renderHook(() => usePersonalRoom(), { wrapper });

    act(() => { result.current.mutate("user-202"); });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const cached = qc.getQueryData<RoomPublic>(["rooms", "detail", "room-dm-4"]);
    expect(cached).toEqual(fakeRoom);
  });

  it("surfaces API errors as mutation error state", async () => {
    mockApi.get = vi.fn().mockRejectedValue(new Error("Not found"));
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => usePersonalRoom(), { wrapper });

    act(() => { result.current.mutate("user-ghost"); });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect((result.current.error as Error).message).toBe("Not found");
  });
});

const mockInvitation: RoomInvitationPublic = {
  id: "inv-1",
  room_id: "room-1",
  room_name: "secret-room",
  invited_by_id: "u-1",
  invited_by_username: "alice",
  invited_user_id: "u-2",
  invited_username: "bob",
  created_at: "2026-04-21T10:00:00Z",
  accepted_at: null,
};

describe("useMyRoomInvitations", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetches /api/rooms/invitations/mine", async () => {
    mockApi.get = vi.fn().mockResolvedValueOnce([mockInvitation]);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useMyRoomInvitations(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi.get).toHaveBeenCalledWith("/api/rooms/invitations/mine");
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].room_name).toBe("secret-room");
    expect(result.current.data?.[0].invited_by_username).toBe("alice");
  });

  it("returns [] when no invitations", async () => {
    mockApi.get = vi.fn().mockResolvedValueOnce([]);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useMyRoomInvitations(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });
});

describe("useAcceptRoomInvitation", () => {
  beforeEach(() => vi.clearAllMocks());

  it("POSTs to /api/rooms/invitations/:id/accept", async () => {
    mockApi.post = vi.fn().mockResolvedValue(undefined);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useAcceptRoomInvitation(), { wrapper });

    act(() => { result.current.mutate("inv-1"); });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi.post).toHaveBeenCalledWith("/api/rooms/invitations/inv-1/accept");
  });

  it("invalidates invitations list and rooms/mine on success", async () => {
    mockApi.post = vi.fn().mockResolvedValue(undefined);
    const { wrapper, qc } = makeWrapper();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useAcceptRoomInvitation(), { wrapper });

    act(() => { result.current.mutate("inv-1"); });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(spy).toHaveBeenCalledWith({ queryKey: ["rooms", "invitations", "mine"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["rooms", "mine"] });
  });

  it("surfaces API errors", async () => {
    mockApi.post = vi.fn().mockRejectedValue(new Error("banned"));
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useAcceptRoomInvitation(), { wrapper });

    act(() => { result.current.mutate("inv-1"); });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect((result.current.error as Error).message).toBe("banned");
  });
});

describe("useDeclineRoomInvitation", () => {
  beforeEach(() => vi.clearAllMocks());

  it("POSTs to /api/rooms/invitations/:id/decline", async () => {
    mockApi.post = vi.fn().mockResolvedValue(undefined);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useDeclineRoomInvitation(), { wrapper });

    act(() => { result.current.mutate("inv-2"); });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi.post).toHaveBeenCalledWith("/api/rooms/invitations/inv-2/decline");
  });

  it("invalidates invitations list but not rooms/mine on success", async () => {
    mockApi.post = vi.fn().mockResolvedValue(undefined);
    const { wrapper, qc } = makeWrapper();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useDeclineRoomInvitation(), { wrapper });

    act(() => { result.current.mutate("inv-2"); });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(spy).toHaveBeenCalledWith({ queryKey: ["rooms", "invitations", "mine"] });
    expect(spy).not.toHaveBeenCalledWith({ queryKey: ["rooms", "mine"] });
  });
});
