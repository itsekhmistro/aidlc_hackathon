import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { RoomCreate, RoomInvitationPublic, RoomPublic } from "../lib/types";

export function useMyRooms() {
  return useQuery<RoomPublic[]>({
    queryKey: ["rooms", "mine"],
    queryFn: () => api.get<RoomPublic[]>("/api/rooms/mine"),
    retry: false,
  });
}

export function usePublicRooms(search?: string) {
  return useQuery<RoomPublic[]>({
    queryKey: ["rooms", "public", search ?? ""],
    queryFn: () =>
      api.get<RoomPublic[]>(`/api/rooms${search ? `?search=${encodeURIComponent(search)}` : ""}`),
    retry: false,
  });
}

export function useCreateRoom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: RoomCreate) => api.post<RoomPublic>("/api/rooms", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rooms"] }),
  });
}

export function useJoinRoom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (roomId: string) => api.post<void>(`/api/rooms/${roomId}/join`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rooms"] }),
  });
}

export function useLeaveRoom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (roomId: string) => api.post<void>(`/api/rooms/${roomId}/leave`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rooms"] }),
  });
}

export function usePersonalRoom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => api.get<RoomPublic>(`/api/personal-rooms/${userId}`),
    onSuccess: (room) => {
      qc.setQueryData(["rooms", "detail", room.id], room);
      qc.invalidateQueries({ queryKey: ["rooms", "mine"] });
    },
  });
}

export function usePersonalRoomForUser(userId: string | null | undefined) {
  return useQuery<RoomPublic>({
    queryKey: ["personal-rooms", userId],
    queryFn: () => api.get<RoomPublic>(`/api/personal-rooms/${userId}`),
    retry: false,
    enabled: !!userId,
  });
}

export function useRoomDetail(roomId: string | null | undefined) {
  return useQuery<RoomPublic>({
    queryKey: ["rooms", "detail", roomId],
    queryFn: () => api.get<RoomPublic>(`/api/rooms/${roomId}`),
    retry: false,
    enabled: !!roomId,
  });
}

export function useMyRoomInvitations() {
  return useQuery<RoomInvitationPublic[]>({
    queryKey: ["rooms", "invitations", "mine"],
    queryFn: () => api.get<RoomInvitationPublic[]>("/api/rooms/invitations/mine"),
    retry: false,
  });
}

export function useAcceptRoomInvitation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: string) =>
      api.post<void>(`/api/rooms/invitations/${invitationId}/accept`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rooms", "invitations", "mine"] });
      qc.invalidateQueries({ queryKey: ["rooms", "mine"] });
    },
  });
}

export function useDeclineRoomInvitation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: string) =>
      api.post<void>(`/api/rooms/invitations/${invitationId}/decline`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rooms", "invitations", "mine"] });
    },
  });
}
