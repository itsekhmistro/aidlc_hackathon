import { useEffect, useRef, useState } from "react";
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

export default function MessageThread({ room, currentUserId }: Props) {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage } = useMessages(room.id);
  const sendMessage = useSendMessage(room.id);
  const editMessage = useEditMessage(room.id);
  const deleteMessage = useDeleteMessage(room.id);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [replyTo, setReplyTo] = useState<MessagePublic | null>(null);

  // All messages in chronological order (pages are newest-first from cursor, so reverse)
  const messages = data?.pages
    .flatMap((p) => p.messages)
    .slice()
    .reverse() ?? [];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b px-4 py-3 font-semibold text-gray-800">
        # {room.name}
        {room.description && (
          <span className="ml-2 text-xs font-normal text-gray-500">{room.description}</span>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-2">
        {hasNextPage && (
          <button
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
            className="w-full text-xs text-gray-400 py-2 hover:text-gray-600"
          >
            {isFetchingNextPage ? "Loading…" : "Load earlier messages"}
          </button>
        )}
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            isOwn={msg.author_id === currentUserId}
            onReply={(m) => setReplyTo(m)}
            onEdit={(m, newContent) =>
              editMessage.mutate({ messageId: m.id, content: newContent })
            }
            onDelete={(m) => deleteMessage.mutate(m.id)}
          />
        ))}
        <div ref={bottomRef} />
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
