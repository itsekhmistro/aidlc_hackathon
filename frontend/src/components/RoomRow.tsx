import { useUnreadCount } from "../lib/unreadStore";
import type { RoomPublic } from "../lib/types";

export default function RoomRow({
  room,
  isActive,
  onClick,
}: {
  room: RoomPublic;
  isActive: boolean;
  onClick: () => void;
}) {
  const unread = useUnreadCount(room.id);
  return (
    <button
      onClick={onClick}
      className={`w-full text-left flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${
        isActive
          ? "bg-blue-100 text-blue-800 font-medium"
          : "text-gray-700 hover:bg-gray-100"
      }`}
    >
      <span className="text-gray-400">{room.is_personal ? "@" : "#"}</span>
      <span className="flex-1 truncate">{room.display_name}</span>
      {unread > 0 && (
        <span className="text-xs bg-blue-500 text-white rounded-full px-1.5 min-w-[1.25rem] text-center leading-5">
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </button>
  );
}
