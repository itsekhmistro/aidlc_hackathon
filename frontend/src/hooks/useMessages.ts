import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { MessagePage, MessagePublic } from "../lib/types";

export function useMessages(roomId: string | null) {
  return useInfiniteQuery<MessagePage>({
    queryKey: ["messages", roomId],
    queryFn: ({ pageParam }) =>
      api.get<MessagePage>(
        `/api/rooms/${roomId}/messages${pageParam ? `?before=${encodeURIComponent(pageParam as string)}` : ""}`
      ),
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    initialPageParam: undefined,
    enabled: !!roomId,
    retry: false,
  });
}

export function useSendMessage(roomId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ content, attachment_ids }: { content: string; attachment_ids?: string[] }) =>
      api.post<MessagePublic>(`/api/rooms/${roomId}/messages`, {
        content,
        reply_to_id: null,
        attachment_ids: attachment_ids ?? [],
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["messages", roomId] }),
  });
}

export function useEditMessage(roomId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ messageId, content }: { messageId: string; content: string }) =>
      api.patch<MessagePublic>(`/api/rooms/${roomId}/messages/${messageId}`, { content }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["messages", roomId] }),
  });
}

export function useDeleteMessage(roomId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (messageId: string) =>
      api.delete<void>(`/api/rooms/${roomId}/messages/${messageId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["messages", roomId] }),
  });
}
