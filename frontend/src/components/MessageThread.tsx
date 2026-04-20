import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  useDeleteMessage,
  useEditMessage,
  useMessages,
  useSendMessage,
} from "../hooks/useMessages";
import MessageBubble from "./MessageBubble";
import MessageInput from "./MessageInput";
import type { MessagePublic, RoomPublic } from "../lib/types";

interface Props {
  room: RoomPublic;
  currentUserId: string;
}

// Distance from bottom (in px) within which we consider the user "at bottom"
// and therefore should follow along when a new message arrives.
const FOLLOW_BOTTOM_THRESHOLD_PX = 120;

export default function MessageThread({ room, currentUserId }: Props) {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage } = useMessages(room.id);
  const sendMessage = useSendMessage(room.id);
  const editMessage = useEditMessage(room.id);
  const deleteMessage = useDeleteMessage(room.id);
  const [replyTo, setReplyTo] = useState<MessagePublic | null>(null);

  // All messages in chronological order (pages are newest-first from cursor, so reverse)
  const messages = useMemo<MessagePublic[]>(
    () => data?.pages.flatMap((p) => p.messages).slice().reverse() ?? [],
    [data],
  );

  const parentRef = useRef<HTMLDivElement>(null);
  // When true, the most recent change to `messages` came from loading older
  // history at the top. We use this to preserve scroll position instead of
  // auto-scrolling to the bottom.
  const loadingOlderRef = useRef(false);
  // Scroll height captured immediately before an older-history fetch, used to
  // compute the delta once the new rows are rendered.
  const prevScrollHeightRef = useRef<number | null>(null);
  // Track the id of the last (newest) message so we can detect "a new message
  // arrived at the bottom" without confusing it with "older messages prepended
  // at the top".
  const lastBottomIdRef = useRef<string | null>(null);
  // Has the initial auto-scroll-to-bottom happened yet?
  const didInitialScrollRef = useRef(false);

  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80,
    overscan: 10,
    getItemKey: (index) => messages[index]?.id ?? index,
  });

  const virtualItems = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();

  // Auto-load older messages when scrolled near the top.
  useEffect(() => {
    if (!virtualItems.length) return;
    const firstIndex = virtualItems[0].index;
    if (firstIndex < 3 && hasNextPage && !isFetchingNextPage) {
      const parent = parentRef.current;
      if (parent) {
        prevScrollHeightRef.current = parent.scrollHeight;
      }
      loadingOlderRef.current = true;
      fetchNextPage();
    }
  }, [virtualItems, hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Preserve scroll position after older messages are prepended.
  // useLayoutEffect so the adjustment happens before the browser paints,
  // avoiding a visible jump.
  useLayoutEffect(() => {
    if (!loadingOlderRef.current) return;
    const parent = parentRef.current;
    const prev = prevScrollHeightRef.current;
    if (!parent || prev == null) return;
    const delta = parent.scrollHeight - prev;
    if (delta > 0) {
      parent.scrollTop += delta;
    }
    loadingOlderRef.current = false;
    prevScrollHeightRef.current = null;
    // We intentionally depend on messages.length so this runs after the new
    // page has rendered and the scroll container has grown.
  }, [messages.length]);

  // Auto-scroll on (a) initial mount when data first arrives, and
  // (b) new message arriving at the bottom while user is already near bottom.
  useEffect(() => {
    if (!messages.length) return;
    const parent = parentRef.current;
    if (!parent) return;

    // Older-history prepend: handled by the layout effect above — do nothing.
    if (loadingOlderRef.current) return;

    const newestId = messages[messages.length - 1].id;
    const prevNewestId = lastBottomIdRef.current;

    if (!didInitialScrollRef.current) {
      // Initial render: jump to bottom once.
      virtualizer.scrollToIndex(messages.length - 1, { align: "end" });
      didInitialScrollRef.current = true;
      lastBottomIdRef.current = newestId;
      return;
    }

    if (newestId !== prevNewestId) {
      // A new message landed at the bottom. Only follow if the user was
      // already near the bottom.
      const distanceFromBottom =
        parent.scrollHeight - parent.scrollTop - parent.clientHeight;
      if (distanceFromBottom <= FOLLOW_BOTTOM_THRESHOLD_PX) {
        virtualizer.scrollToIndex(messages.length - 1, { align: "end" });
      }
      lastBottomIdRef.current = newestId;
    }
  }, [messages, virtualizer]);

  // Reset bookkeeping when switching rooms.
  useEffect(() => {
    didInitialScrollRef.current = false;
    lastBottomIdRef.current = null;
    loadingOlderRef.current = false;
    prevScrollHeightRef.current = null;
  }, [room.id]);

  const measureElement = useCallback(
    (node: Element | null) => {
      if (node) virtualizer.measureElement(node);
    },
    [virtualizer],
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b px-4 py-3 font-semibold text-gray-800">
        {room.is_personal ? "@" : "#"} {room.display_name}
        {room.description && (
          <span className="ml-2 text-xs font-normal text-gray-500">{room.description}</span>
        )}
      </div>

      {/* Messages (virtualized) */}
      <div ref={parentRef} className="flex-1 overflow-y-auto px-4 py-2">
        {isFetchingNextPage && (
          <div className="w-full text-xs text-gray-400 py-2 text-center">
            Loading earlier messages…
          </div>
        )}
        <div
          style={{
            height: `${totalSize}px`,
            width: "100%",
            position: "relative",
          }}
        >
          {virtualItems.map((virtualRow) => {
            const msg = messages[virtualRow.index];
            if (!msg) return null;
            return (
              <div
                key={virtualRow.key}
                data-index={virtualRow.index}
                ref={measureElement}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <MessageBubble
                  message={msg}
                  isOwn={msg.author_id === currentUserId}
                  onReply={(m) => setReplyTo(m)}
                  onEdit={(m, newContent) =>
                    editMessage.mutate({ messageId: m.id, content: newContent })
                  }
                  onDelete={(m) => deleteMessage.mutate(m.id)}
                />
              </div>
            );
          })}
        </div>
      </div>

      {/* Input */}
      <MessageInput
        roomId={room.id}
        replyTo={replyTo}
        onCancelReply={() => setReplyTo(null)}
        onSend={(content, attachmentIds, replyToId) => {
          sendMessage.mutate({
            content,
            attachment_ids: attachmentIds,
            reply_to_id: replyToId ?? null,
          });
          setReplyTo(null);
        }}
        disabled={sendMessage.isPending}
      />
    </div>
  );
}
