import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { RoomMemberPublic } from "../lib/types";

export function useRoomMembers(roomId: string | null | undefined) {
  return useQuery<RoomMemberPublic[]>({
    queryKey: ["rooms", roomId, "members"],
    queryFn: () => api.get<RoomMemberPublic[]>(`/api/rooms/${roomId}/members`),
    retry: false,
    enabled: !!roomId,
  });
}
