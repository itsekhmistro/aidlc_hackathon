import { useRevokeSession, useSessions } from "../hooks/useSessions";
import type { SessionPublic } from "../lib/types";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function SessionCard({
  session,
  onRevoke,
  revokePending,
}: {
  session: SessionPublic;
  onRevoke: () => void;
  revokePending: boolean;
}) {
  return (
    <div className="border border-gray-200 rounded-md p-4 flex items-start gap-3">
      <div className="flex-1 min-w-0 space-y-1">
        <p className="text-sm font-medium text-gray-900 truncate">
          {session.user_agent ?? "Unknown device"}
        </p>
        <p className="text-xs text-gray-500">IP: {session.ip_address ?? "—"}</p>
        <p className="text-xs text-gray-500">
          Last seen: {formatDate(session.last_seen_at)}
        </p>
        <p className="text-xs text-gray-400">Created: {formatDate(session.created_at)}</p>
      </div>
      {session.is_current ? (
        <span className="text-xs bg-blue-100 text-blue-700 rounded px-2 py-0.5">
          Current session
        </span>
      ) : (
        <button
          onClick={onRevoke}
          disabled={revokePending}
          className="text-xs px-3 py-1.5 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
        >
          {revokePending ? "Revoking…" : "Revoke"}
        </button>
      )}
    </div>
  );
}

export default function SessionsPage() {
  const { data: sessions = [], isLoading, isError } = useSessions();
  const revoke = useRevokeSession();

  return (
    <div className="max-w-2xl mx-auto p-6 h-full overflow-y-auto">
      <h1 className="text-xl font-semibold text-gray-900 mb-1">Active sessions</h1>
      <p className="text-sm text-gray-500 mb-4">
        Revoking the session you are currently using will sign you out on the next request.
      </p>

      {isLoading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : isError ? (
        <p className="text-sm text-gray-400">Could not load sessions</p>
      ) : sessions.length === 0 ? (
        <p className="text-sm text-gray-400">No active sessions.</p>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <SessionCard
              key={s.id}
              session={s}
              onRevoke={() => revoke.mutate(s.id)}
              revokePending={revoke.isPending && revoke.variables === s.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
