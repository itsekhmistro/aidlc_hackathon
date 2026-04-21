import { useState } from "react";
import { useCancelInvitation, useInviteUser, useRoomInvitations } from "../../hooks/useAdmin";

interface Props {
  roomId: string;
}

export default function InvitationsTab({ roomId }: Props) {
  const { data: invites = [], isLoading } = useRoomInvitations(roomId);
  const invite = useInviteUser();
  const cancel = useCancelInvitation();
  const [username, setUsername] = useState("");

  const handleInvite = (e: React.FormEvent) => {
    e.preventDefault();
    const name = username.trim();
    if (!name) return;
    invite.mutate(
      { roomId, username: name },
      {
        onSuccess: () => setUsername(""),
      },
    );
  };

  return (
    <div className="space-y-4">
      <form onSubmit={handleInvite} className="flex gap-2">
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Invite by username"
          aria-label="Invite by username"
          className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="submit"
          disabled={invite.isPending || !username.trim()}
          className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {invite.isPending ? "Sending…" : "Send invite"}
        </button>
      </form>
      {invite.isError && (
        <p className="text-xs text-red-600">{(invite.error as Error).message}</p>
      )}

      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Pending invitations
        </p>
        <div className="max-h-72 overflow-y-auto divide-y divide-gray-100">
          {isLoading ? (
            <p className="text-xs text-gray-400 py-2">Loading…</p>
          ) : invites.length === 0 ? (
            <p className="text-xs text-gray-400 py-2">No pending invitations.</p>
          ) : (
            invites.map((inv) => (
              <div key={inv.id} className="flex items-center gap-2 py-2 text-sm">
                <span className="flex-1 text-xs text-gray-600">
                  <span className="font-medium text-gray-800">{inv.invited_username}</span>
                  {" · "}
                  {new Date(inv.created_at).toLocaleDateString()}
                </span>
                <button
                  type="button"
                  onClick={() =>
                    cancel.mutate({ roomId, invitationId: inv.id })
                  }
                  className="px-2 py-0.5 text-xs bg-gray-100 rounded hover:bg-gray-200"
                >
                  Cancel
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
