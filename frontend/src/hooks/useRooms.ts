import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { RoomCreate, RoomPublic } from "../lib/types";

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
    },
  });
}
