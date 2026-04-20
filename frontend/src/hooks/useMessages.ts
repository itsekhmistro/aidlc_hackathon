import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
  type QueryClient,
} from "@tanstack/react-query";
import { api } from "../lib/api";
import type { MessagePage, MessagePublic } from "../lib/types";

type MessagesCache = InfiniteData<MessagePage>;

// Idempotent surgical insert of a freshly arrived message into the infinite-
// query cache. Skips work when the cache is empty (room never opened by this
// client) or when the id already exists (dedupes echo/race between the POST
// response and the WS broadcast). Returns true if the cache was mutated.
export function mergeNewMessage(
  qc: QueryClient,
  roomId: string,
  message: MessagePublic,
): boolean {
  const key = ["messages", roomId];
  const existing = qc.getQueryData<MessagesCache>(key);
  if (!existing || existing.pages.length === 0) return false;
  const [first, ...rest] = existing.pages;
  if (first.messages.some((m) => m.id === message.id)) return false;
  qc.setQueryData<MessagesCache>(key, {
    ...existing,
    pages: [{ ...first, messages: [message, ...first.messages] }, ...rest],
  });
  return true;
}

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
    mutationFn: ({
      content,
      attachment_ids,
      reply_to_id,
    }: {
      content: string;
      attachment_ids?: string[];
      reply_to_id?: string | null;
    }) =>
      api.post<MessagePublic>(`/api/rooms/${roomId}/messages`, {
        content,
        reply_to_id: reply_to_id ?? null,
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
