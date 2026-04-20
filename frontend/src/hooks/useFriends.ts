import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { FriendshipPublic } from "../lib/types";

export function useFriends() {
  return useQuery<FriendshipPublic[]>({
    queryKey: ["friends"],
    queryFn: () => api.get<FriendshipPublic[]>("/api/friends"),
    retry: false,
  });
}

export function useFriendRequests() {
  return useQuery<FriendshipPublic[]>({
    queryKey: ["friends", "requests"],
    queryFn: () => api.get<FriendshipPublic[]>("/api/friends/requests/incoming"),
    retry: false,
  });
}

export function useSendFriendRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ username, message }: { username: string; message?: string }) =>
      api.post<FriendshipPublic>("/api/friends/request", { username, message }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["friends"] }),
  });
}

export function useAcceptFriendRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (friendshipId: string) =>
      api.patch<FriendshipPublic>(`/api/friends/${friendshipId}/accept`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["friends"] }),
  });
}

export function useRemoveFriend() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (friendshipId: string) => api.delete<void>(`/api/friends/${friendshipId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["friends"] }),
  });
}

export function useBanUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => api.post<void>(`/api/user-bans/${userId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["friends"] }),
  });
}
