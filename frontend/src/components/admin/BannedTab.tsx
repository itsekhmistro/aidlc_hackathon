import { useRoomBans, useUnbanMember } from "../../hooks/useAdmin";

interface Props {
  roomId: string;
}

export default function BannedTab({ roomId }: Props) {
  const { data: bans = [], isLoading } = useRoomBans(roomId);
  const unban = useUnbanMember();

  return (
    <div className="max-h-96 overflow-y-auto divide-y divide-gray-100">
      {isLoading ? (
        <p className="text-xs text-gray-400 py-2">Loading…</p>
      ) : bans.length === 0 ? (
        <p className="text-xs text-gray-400 py-2">No banned users.</p>
      ) : (
        bans.map((b) => (
          <div key={b.user_id} className="flex items-center gap-2 py-2 text-sm">
            <span className="flex-1 truncate text-gray-800">{b.username}</span>
            <span className="text-xs text-gray-500">
              by {b.banned_by_username} · {new Date(b.banned_at).toLocaleDateString()}
            </span>
            <button
              type="button"
              onClick={() => unban.mutate({ roomId, userId: b.user_id })}
              disabled={unban.isPending}
              className="px-2 py-0.5 text-xs bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50"
            >
              Unban
            </button>
          </div>
        ))
      )}
    </div>
  );
}
