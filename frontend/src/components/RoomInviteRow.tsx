import { useAcceptRoomInvitation, useDeclineRoomInvitation } from "../hooks/useRooms";
import type { RoomInvitationPublic } from "../lib/types";

export default function RoomInviteRow({ invite }: { invite: RoomInvitationPublic }) {
  const accept = useAcceptRoomInvitation();
  const decline = useDeclineRoomInvitation();

  return (
    <div className="flex items-center gap-2 px-3 py-2">
      <span className="text-sm text-gray-700 flex-1 truncate">
        <span className="font-medium">{invite.invited_by_username}</span>
        <span className="text-gray-400"> invited you to </span>
        <span className="font-medium">#{invite.room_name}</span>
      </span>
      <button
        onClick={() => accept.mutate(invite.id)}
        disabled={accept.isPending}
        className="text-xs px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
        aria-label={`Accept invitation to ${invite.room_name}`}
      >
        ✓
      </button>
      <button
        onClick={() => decline.mutate(invite.id)}
        disabled={decline.isPending}
        className="text-xs px-2 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
        aria-label={`Decline invitation to ${invite.room_name}`}
      >
        ✕
      </button>
    </div>
  );
}
