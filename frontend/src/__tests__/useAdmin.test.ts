import React from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  useBanMember,
  useCancelInvitation,
  useDeleteRoom,
  useGrantAdmin,
  useInviteUser,
  useRemoveAdmin,
  useRoomBans,
  useRoomInvitations,
  useUnbanMember,
  useUpdateRoom,
} from "../hooks/useAdmin";
import { api } from "../lib/api";
import type { RoomBanPublic, RoomInvitationPublic, RoomPublic } from "../lib/types";

vi.mock("../lib/api");
const mockApi = vi.mocked(api);

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
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
  member_count: 2,
};

describe("useRoomBans", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetches bans for the room", async () => {
    const bans: RoomBanPublic[] = [
      {
        user_id: "u-2",
        username: "troll",
        banned_by_id: "u-1",
        banned_by_username: "owner",
        banned_at: "2026-04-20T10:00:00Z",
      },
    ];
    mockApi.get = vi.fn().mockResolvedValueOnce(bans);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useRoomBans("room-1"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi.get).toHaveBeenCalledWith("/api/rooms/room-1/bans");
    expect(result.current.data?.[0].username).toBe("troll");
  });

  it("is disabled when roomId is falsy", () => {
    mockApi.get = vi.fn().mockResolvedValueOnce([]);
    const { wrapper } = makeWrapper();
    renderHook(() => useRoomBans(null), { wrapper });
    expect(mockApi.get).not.toHaveBeenCalled();
  });
});

describe("useRoomInvitations", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetches invitations for the room", async () => {
    const invites: RoomInvitationPublic[] = [
      {
        id: "inv-1",
        room_id: "room-1",
        invited_by_id: "u-1",
        invited_user_id: "u-3",
        created_at: "2026-04-20T10:00:00Z",
        accepted_at: null,
      },
    ];
    mockApi.get = vi.fn().mockResolvedValueOnce(invites);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useRoomInvitations("room-1"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi.get).toHaveBeenCalledWith("/api/rooms/room-1/invitations");
  });
});

describe("admin mutations", () => {
  beforeEach(() => vi.clearAllMocks());

  it("useGrantAdmin POSTs to /admin and invalidates members", async () => {
    mockApi.post = vi.fn().mockResolvedValue(undefined);
    const { wrapper, qc } = makeWrapper();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useGrantAdmin(), { wrapper });

    act(() => {
      result.current.mutate({ roomId: "room-1", userId: "u-2" });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi.post).toHaveBeenCalledWith("/api/rooms/room-1/members/u-2/admin");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["rooms", "room-1", "members"] });
  });

  it("useRemoveAdmin DELETEs /admin", async () => {
    mockApi.delete = vi.fn().mockResolvedValue(undefined);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useRemoveAdmin(), { wrapper });
    act(() => {
      result.current.mutate({ roomId: "room-1", userId: "u-2" });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi.delete).toHaveBeenCalledWith("/api/rooms/room-1/members/u-2/admin");
  });

  it("useBanMember DELETEs the member and invalidates members + bans", async () => {
    mockApi.delete = vi.fn().mockResolvedValue(undefined);
    const { wrapper, qc } = makeWrapper();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useBanMember(), { wrapper });

    act(() => {
      result.current.mutate({ roomId: "room-1", userId: "u-2" });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi.delete).toHaveBeenCalledWith("/api/rooms/room-1/members/u-2");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["rooms", "room-1", "members"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["rooms", "room-1", "bans"] });
  });

  it("useUnbanMember DELETEs the ban", async () => {
    mockApi.delete = vi.fn().mockResolvedValue(undefined);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useUnbanMember(), { wrapper });
    act(() => {
      result.current.mutate({ roomId: "room-1", userId: "u-2" });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi.delete).toHaveBeenCalledWith("/api/rooms/room-1/bans/u-2");
  });

  it("useInviteUser POSTs { username } and invalidates invitations", async () => {
    const invite: RoomInvitationPublic = {
      id: "inv-1",
      room_id: "room-1",
      invited_by_id: "u-1",
      invited_user_id: "u-3",
      created_at: "2026-04-20T10:00:00Z",
      accepted_at: null,
    };
    mockApi.post = vi.fn().mockResolvedValue(invite);
    const { wrapper, qc } = makeWrapper();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useInviteUser(), { wrapper });

    act(() => {
      result.current.mutate({ roomId: "room-1", username: "bob" });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi.post).toHaveBeenCalledWith("/api/rooms/room-1/invitations", {
      username: "bob",
    });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["rooms", "room-1", "invitations"] });
  });

  it("useCancelInvitation DELETEs the invitation", async () => {
    mockApi.delete = vi.fn().mockResolvedValue(undefined);
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useCancelInvitation(), { wrapper });
    act(() => {
      result.current.mutate({ roomId: "room-1", invitationId: "inv-1" });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi.delete).toHaveBeenCalledWith("/api/rooms/room-1/invitations/inv-1");
  });

  it("useUpdateRoom PATCHes the room and caches the response", async () => {
    const updated = { ...mockRoom, name: "renamed" };
    mockApi.patch = vi.fn().mockResolvedValue(updated);
    const { wrapper, qc } = makeWrapper();
    const { result } = renderHook(() => useUpdateRoom(), { wrapper });

    act(() => {
      result.current.mutate({ roomId: "room-1", patch: { name: "renamed" } });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi.patch).toHaveBeenCalledWith("/api/rooms/room-1", { name: "renamed" });
    expect(qc.getQueryData<RoomPublic>(["rooms", "detail", "room-1"])).toEqual(updated);
  });

  it("useDeleteRoom DELETEs and drops the detail cache", async () => {
    mockApi.delete = vi.fn().mockResolvedValue(undefined);
    const { wrapper, qc } = makeWrapper();
    qc.setQueryData(["rooms", "detail", "room-1"], mockRoom);
    const { result } = renderHook(() => useDeleteRoom(), { wrapper });

    act(() => {
      result.current.mutate("room-1");
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi.delete).toHaveBeenCalledWith("/api/rooms/room-1");
    expect(qc.getQueryData(["rooms", "detail", "room-1"])).toBeUndefined();
  });
});
