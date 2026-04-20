import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useCurrentUser } from "../hooks/useAuth";
import { usePersonalRoomForUser } from "../hooks/useRooms";
import { api } from "../lib/api";
import { clearUnread } from "../lib/unreadStore";

export default function DmChatPage() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const { data: me } = useCurrentUser();
  const { data: room, isLoading, isError } = usePersonalRoomForUser(userId);

  useEffect(() => {
    if (!room) return;
    clearUnread(room.id);
    api.post(`/api/unread/${room.id}/mark-read`).catch(() => {});
  }, [room?.id]);

  // Once the personal room is resolved, redirect to the stable /chat/rooms/:roomId
  // URL so the address is shareable and the regular RoomChatPage takes over.
  useEffect(() => {
    if (room?.id) {
      navigate(`/chat/rooms/${room.id}`, { replace: true });
    }
  }, [room?.id, navigate]);

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

  // The redirect effect above will unmount this component; render nothing
  // in the brief interval before navigation commits.
  return null;
}
