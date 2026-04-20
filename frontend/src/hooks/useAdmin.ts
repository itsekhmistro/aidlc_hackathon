import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type {
  RoomBanPublic,
  RoomInvitationPublic,
  RoomPublic,
  RoomUpdate,
} from "../lib/types";

// ── Queries ──────────────────────────────────────────────────────────────────

export function useRoomBans(roomId: string | null | undefined) {
  return useQuery<RoomBanPublic[]>({
    queryKey: ["rooms", roomId, "bans"],
    queryFn: () => api.get<RoomBanPublic[]>(`/api/rooms/${roomId}/bans`),
    retry: false,
    enabled: !!roomId,
  });
}

export function useRoomInvitations(roomId: string | null | undefined) {
  return useQuery<RoomInvitationPublic[]>({
    queryKey: ["rooms", roomId, "invitations"],
    queryFn: () =>
      api.get<RoomInvitationPublic[]>(`/api/rooms/${roomId}/invitations`),
    retry: false,
    enabled: !!roomId,
  });
}

// ── Mutations ────────────────────────────────────────────────────────────────

export function useGrantAdmin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ roomId, userId }: { roomId: string; userId: string }) =>
      api.post<void>(`/api/rooms/${roomId}/members/${userId}/admin`),
    onSuccess: (_data, { roomId }) => {
      qc.invalidateQueries({ queryKey: ["rooms", roomId, "members"] });
    },
  });
}

export function useRemoveAdmin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ roomId, userId }: { roomId: string; userId: string }) =>
      api.delete<void>(`/api/rooms/${roomId}/members/${userId}/admin`),
    onSuccess: (_data, { roomId }) => {
      qc.invalidateQueries({ queryKey: ["rooms", roomId, "members"] });
    },
  });
}

export function useBanMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ roomId, userId }: { roomId: string; userId: string }) =>
      api.delete<void>(`/api/rooms/${roomId}/members/${userId}`),
    onSuccess: (_data, { roomId }) => {
      qc.invalidateQueries({ queryKey: ["rooms", roomId, "members"] });
      qc.invalidateQueries({ queryKey: ["rooms", roomId, "bans"] });
    },
  });
}

export function useUnbanMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ roomId, userId }: { roomId: string; userId: string }) =>
      api.delete<void>(`/api/rooms/${roomId}/bans/${userId}`),
    onSuccess: (_data, { roomId }) => {
      qc.invalidateQueries({ queryKey: ["rooms", roomId, "bans"] });
    },
  });
}

export function useInviteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ roomId, username }: { roomId: string; username: string }) =>
      api.post<RoomInvitationPublic>(`/api/rooms/${roomId}/invitations`, {
        username,
      }),
    onSuccess: (_data, { roomId }) => {
      qc.invalidateQueries({ queryKey: ["rooms", roomId, "invitations"] });
    },
  });
}

export function useCancelInvitation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      roomId,
      invitationId,
    }: {
      roomId: string;
      invitationId: string;
    }) =>
      api.delete<void>(`/api/rooms/${roomId}/invitations/${invitationId}`),
    onSuccess: (_data, { roomId }) => {
      qc.invalidateQueries({ queryKey: ["rooms", roomId, "invitations"] });
    },
  });
}

export function useUpdateRoom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ roomId, patch }: { roomId: string; patch: RoomUpdate }) =>
      api.patch<RoomPublic>(`/api/rooms/${roomId}`, patch),
    onSuccess: (room) => {
      qc.setQueryData(["rooms", "detail", room.id], room);
      qc.invalidateQueries({ queryKey: ["rooms", "mine"] });
    },
  });
}

export function useDeleteRoom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (roomId: string) => api.delete<void>(`/api/rooms/${roomId}`),
    onSuccess: (_data, roomId) => {
      qc.removeQueries({ queryKey: ["rooms", "detail", roomId] });
      qc.invalidateQueries({ queryKey: ["rooms"] });
    },
  });
}
