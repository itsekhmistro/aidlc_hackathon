import { useState } from "react";
import { PresenceDot } from "../PresenceDot";
import { useRoomMembers } from "../../hooks/useRoomMembers";
import { useBanMember, useGrantAdmin, useRemoveAdmin } from "../../hooks/useAdmin";
import ConfirmModal from "../ConfirmModal";
import type { MemberRole, RoomMemberPublic } from "../../lib/types";

interface Props {
  roomId: string;
  myRole: MemberRole;
  roomName: string;
}

export default function MembersTab({ roomId, myRole, roomName }: Props) {
  const { data: members = [], isLoading } = useRoomMembers(roomId);
  const grantAdmin = useGrantAdmin();
  const removeAdmin = useRemoveAdmin();
  const banMember = useBanMember();

  const [search, setSearch] = useState("");
  const [confirmBan, setConfirmBan] = useState<RoomMemberPublic | null>(null);

  const filtered = members.filter((m) =>
    m.username.toLowerCase().includes(search.toLowerCase()),
  );

  const canActOn = (target: RoomMemberPublic): boolean => {
    if (target.role === "owner") return false;
    if (myRole === "owner") return true;
    if (myRole === "admin" && target.role === "member") return true;
    return false;
  };

  return (
    <div className="space-y-3">
      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search member"
        aria-label="Search member"
        className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <div className="max-h-96 overflow-y-auto divide-y divide-gray-100">
        {isLoading ? (
          <p className="text-xs text-gray-400 py-2">Loading…</p>
        ) : filtered.length === 0 ? (
          <p className="text-xs text-gray-400 py-2">No members match.</p>
        ) : (
          filtered.map((m) => (
            <div key={m.user_id} className="flex items-center gap-2 py-2 text-sm">
              <PresenceDot status={m.presence_status} />
              <span className="flex-1 truncate text-gray-800">{m.username}</span>
              <span className="text-xs uppercase tracking-wider text-gray-500 w-14">
                {m.role}
              </span>
              {canActOn(m) && (
                <div className="flex gap-1">
                  {myRole === "owner" && m.role === "member" && (
                    <button
                      type="button"
                      onClick={() =>
                        grantAdmin.mutate({ roomId, userId: m.user_id })
                      }
                      className="px-2 py-0.5 text-xs bg-gray-100 rounded hover:bg-gray-200"
                    >
                      Make admin
                    </button>
                  )}
                  {myRole === "owner" && m.role === "admin" && (
                    <button
                      type="button"
                      onClick={() =>
                        removeAdmin.mutate({ roomId, userId: m.user_id })
                      }
                      className="px-2 py-0.5 text-xs bg-gray-100 rounded hover:bg-gray-200"
                    >
                      Remove admin
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setConfirmBan(m)}
                    className="px-2 py-0.5 text-xs text-red-600 hover:bg-red-50 rounded"
                  >
                    Ban
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>
      {confirmBan && (
        <ConfirmModal
          title="Ban member"
          body={`Ban ${confirmBan.username} from #${roomName}? They will not be able to rejoin.`}
          confirmLabel="Ban"
          danger
          pending={banMember.isPending}
          onCancel={() => setConfirmBan(null)}
          onConfirm={() => {
            banMember.mutate(
              { roomId, userId: confirmBan.user_id },
              { onSuccess: () => setConfirmBan(null) },
            );
          }}
        />
      )}
    </div>
  );
}
