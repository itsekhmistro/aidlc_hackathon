import { useEffect } from "react";
import { useParams } from "react-router-dom";
import MessageThread from "../components/MessageThread";
import { useCurrentUser } from "../hooks/useAuth";
import { usePersonalRoomForUser } from "../hooks/useRooms";
import { api } from "../lib/api";
import { clearUnread } from "../lib/unreadStore";

export default function DmChatPage() {
  const { userId } = useParams<{ userId: string }>();
  const { data: me } = useCurrentUser();
  const { data: room, isLoading, isError } = usePersonalRoomForUser(userId);

  useEffect(() => {
    if (!room) return;
    clearUnread(room.id);
    api.post(`/api/unread/${room.id}/mark-read`).catch(() => {});
  }, [room?.id]);

  if (isError) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-sm">
        Could not open conversation
      </div>
    );
  }
  if (isLoading || !room || !me) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-sm">
        Opening conversation…
      </div>
    );
  }

  return <MessageThread room={room} currentUserId={me.id} />;
}
