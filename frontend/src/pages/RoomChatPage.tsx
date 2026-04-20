import { useEffect } from "react";
import { useParams } from "react-router-dom";
import MessageThread from "../components/MessageThread";
import { useCurrentUser } from "../hooks/useAuth";
import { useMyRooms, useRoomDetail } from "../hooks/useRooms";
import { api } from "../lib/api";
import { clearUnread } from "../lib/unreadStore";

export default function RoomChatPage() {
  const { roomId } = useParams<{ roomId: string }>();
  const { data: me } = useCurrentUser();
  const { data: myRooms = [] } = useMyRooms();
  const fromMine = myRooms.find((r) => r.id === roomId) ?? null;
  const { data: fetched } = useRoomDetail(fromMine ? null : roomId);
  const room = fromMine ?? fetched ?? null;

  useEffect(() => {
    if (!roomId) return;
    clearUnread(roomId);
    api.post(`/api/unread/${roomId}/mark-read`).catch(() => {});
  }, [roomId]);

  if (!room || !me) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-sm">
        Loading…
      </div>
    );
  }

  return <MessageThread room={room} currentUserId={me.id} />;
}
