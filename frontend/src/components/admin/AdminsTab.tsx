import { useRoomMembers } from "../../hooks/useRoomMembers";
import { useRemoveAdmin } from "../../hooks/useAdmin";
import type { MemberRole } from "../../lib/types";

interface Props {
  roomId: string;
  myRole: MemberRole;
}

export default function AdminsTab({ roomId, myRole }: Props) {
  const { data: members = [], isLoading } = useRoomMembers(roomId);
  const removeAdmin = useRemoveAdmin();

  const adminsAndOwner = members.filter(
    (m) => m.role === "owner" || m.role === "admin",
  );
  const owner = adminsAndOwner.find((m) => m.role === "owner");
  const admins = adminsAndOwner.filter((m) => m.role === "admin");

  const summary = adminsAndOwner.map((m) => m.username).join(", ");

  return (
    <div className="space-y-3">
      {isLoading ? (
        <p className="text-xs text-gray-400 py-2">Loading…</p>
      ) : (
        <>
          <p className="text-xs text-gray-500">
            Current admins: {summary || "—"}
          </p>
          <div className="max-h-96 overflow-y-auto divide-y divide-gray-100">
            {owner && (
              <div
                key={owner.user_id}
                className="flex items-center gap-2 py-2 text-sm"
              >
                <span className="flex-1 truncate text-gray-800">
                  {owner.username}
                </span>
                <span className="text-xs text-gray-500">
                  Owner — cannot remove admin
                </span>
              </div>
            )}
            {admins.length === 0 ? (
              <p className="text-xs text-gray-400 py-2">
                No admins beyond the owner.
              </p>
            ) : (
              admins.map((m) => (
                <div
                  key={m.user_id}
                  className="flex items-center gap-2 py-2 text-sm"
                >
                  <span className="flex-1 truncate text-gray-800">
                    {m.username}
                  </span>
                  {myRole === "owner" ? (
                    <button
                      type="button"
                      onClick={() =>
                        removeAdmin.mutate({ roomId, userId: m.user_id })
                      }
                      disabled={removeAdmin.isPending}
                      className="px-2 py-0.5 text-xs bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50"
                    >
                      Remove admin
                    </button>
                  ) : (
                    <span className="text-xs uppercase tracking-wider text-gray-500">
                      admin
                    </span>
                  )}
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
