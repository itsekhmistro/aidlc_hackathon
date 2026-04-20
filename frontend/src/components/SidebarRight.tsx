import { useState } from "react";
import { useRoomMembers } from "../hooks/useRoomMembers";
import { useCurrentUser } from "../hooks/useAuth";
import { PresenceDot } from "./PresenceDot";
import { usePresence } from "../lib/presenceStore";
import type { MemberRole, PresenceStatus, RoomMemberPublic } from "../lib/types";
import ManageRoomModal from "./ManageRoomModal";

interface Props {
  roomId: string;
}

const STATUS_ORDER: Record<PresenceStatus, number> = {
  online: 0,
  afk: 1,
  offline: 2,
};

function RoleBadge({ role }: { role: MemberRole }) {
  if (role === "member") return null;
  const label = role === "owner" ? "owner" : "admin";
  const classes =
    role === "owner"
      ? "bg-purple-100 text-purple-700"
      : "bg-blue-100 text-blue-700";
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wider ${classes}`}>
      {label}
    </span>
  );
}

function MemberRow({ member }: { member: RoomMemberPublic }) {
  // usePresence returns "offline" by default; fall back to the API snapshot
  // until the presence store has a live entry for this user.
  const live = usePresence(member.user_id);
  const status: PresenceStatus =
    live === "offline" && member.presence_status !== "offline"
      ? member.presence_status
      : live;
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 text-sm">
      <PresenceDot status={status} />
      <span className="flex-1 truncate text-gray-800">{member.username}</span>
      <RoleBadge role={member.role} />
    </div>
  );
}

export default function SidebarRight({ roomId }: Props) {
  const { data: members = [], isLoading, isError } = useRoomMembers(roomId);
  const { data: me } = useCurrentUser();
  const [manageOpen, setManageOpen] = useState(false);

  // Sort: status order, then username.
  const sorted = [...members].sort((a, b) => {
    const sa = STATUS_ORDER[a.presence_status];
    const sb = STATUS_ORDER[b.presence_status];
    if (sa !== sb) return sa - sb;
    return a.username.localeCompare(b.username);
  });

  const myRole = members.find((m) => m.user_id === me?.id)?.role;
  const canManage = myRole === "owner" || myRole === "admin";

  return (
    <aside className="w-56 bg-white border-l border-gray-200 flex flex-col h-full">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          Members ({members.length})
        </p>
        {canManage && (
          <button
            type="button"
            onClick={() => setManageOpen(true)}
            className="text-xs text-blue-600 hover:text-blue-800"
          >
            Manage
          </button>
        )}
      </div>
      <div className="flex-1 overflow-y-auto py-1">
        {isLoading ? (
          <p className="text-xs text-gray-400 px-4 py-2">Loading…</p>
        ) : isError ? (
          <p className="text-xs text-gray-400 px-4 py-2">Could not load members</p>
        ) : sorted.length === 0 ? (
          <p className="text-xs text-gray-400 px-4 py-2">No members</p>
        ) : (
          sorted.map((m) => <MemberRow key={m.user_id} member={m} />)
        )}
      </div>
      {manageOpen && (
        <ManageRoomModal roomId={roomId} onClose={() => setManageOpen(false)} />
      )}
    </aside>
  );
}
