import { Navigate } from "react-router-dom";
import { useCurrentUser } from "../../hooks/useAuth";
import { useJabberFederation } from "../../hooks/useJabber";
import { formatDuration, formatRelative } from "../../lib/utils";
import type { JabberFederationMessage, JabberFederationRemote } from "../../lib/types";

function directionBadge(direction: JabberFederationRemote["direction"]) {
  const base = "inline-block text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded";
  if (direction === "in") return `${base} bg-blue-100 text-blue-700`;
  if (direction === "out") return `${base} bg-green-100 text-green-700`;
  return `${base} bg-purple-100 text-purple-700`;
}

function RemotesTable({ remotes }: { remotes: JabberFederationRemote[] }) {
  if (remotes.length === 0) {
    return (
      <p className="text-sm text-gray-400 py-4" data-testid="jabber-remotes-empty">
        No federation peers have exchanged messages yet.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto border border-gray-200 rounded-md">
      <table className="w-full text-sm" data-testid="jabber-remotes-table">
        <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wider">
          <tr>
            <th className="text-left font-medium px-3 py-2">Remote server</th>
            <th className="text-left font-medium px-3 py-2">Direction</th>
            <th className="text-left font-medium px-3 py-2">Messages</th>
            <th className="text-left font-medium px-3 py-2">Last activity</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {remotes.map((r) => (
            <tr key={r.server}>
              <td className="px-3 py-2 text-gray-800 font-mono text-xs">{r.server}</td>
              <td className="px-3 py-2">
                <span className={directionBadge(r.direction)}>{r.direction}</span>
              </td>
              <td className="px-3 py-2 text-gray-700">{r.message_count.toLocaleString()}</td>
              <td className="px-3 py-2 text-gray-500 text-xs">
                {formatDuration(r.last_active_seconds_ago)} ago
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RecentMessages({ messages }: { messages: JabberFederationMessage[] }) {
  if (messages.length === 0) {
    return (
      <p className="text-sm text-gray-400 py-4" data-testid="jabber-recent-empty">
        No recent federation messages.
      </p>
    );
  }
  return (
    <ul className="divide-y divide-gray-100 border border-gray-200 rounded-md bg-white">
      {messages.map((m, i) => (
        <li key={`${m.ts}-${i}`} className="px-3 py-2 flex flex-col gap-0.5">
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs text-gray-500 font-mono truncate">
              <span className="text-gray-700">{m.from_jid}</span>
              <span className="mx-1 text-gray-400">→</span>
              <span className="text-gray-700">{m.to_jid}</span>
            </div>
            <span className="text-[11px] text-gray-400 shrink-0">{formatRelative(m.ts)}</span>
          </div>
          <p className="text-sm text-gray-800 truncate">
            {m.preview ?? <span className="text-gray-400">…</span>}
          </p>
        </li>
      ))}
    </ul>
  );
}

export default function JabberFederation() {
  const { data: me, isLoading: meLoading } = useCurrentUser();
  const { data, isLoading, isError, error } = useJabberFederation();

  if (meLoading) {
    return (
      <div className="min-h-full flex items-center justify-center text-gray-500 text-sm">
        Loading…
      </div>
    );
  }
  if (!me?.is_admin) {
    return <Navigate to="/chat" replace />;
  }

  return (
    <div className="max-w-5xl mx-auto p-6 h-full overflow-y-auto">
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">Federation traffic</h1>
        <p className="text-sm text-gray-500 mt-1">
          S2S peers and recent federation messages — polled every 10 s.
        </p>
      </header>

      {isLoading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : isError ? (
        <p className="text-sm text-gray-400">
          {error instanceof Error ? error.message : "Could not load federation data."}
        </p>
      ) : data ? (
        <>
          <section className="mb-6">
            <h2 className="text-sm font-semibold text-gray-900 mb-2">Remote servers</h2>
            <RemotesTable remotes={data.remotes} />
          </section>

          <section>
            <h2 className="text-sm font-semibold text-gray-900 mb-2">Recent federation messages</h2>
            <RecentMessages messages={data.recent} />
          </section>
        </>
      ) : null}
    </div>
  );
}
