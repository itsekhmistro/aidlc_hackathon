import { Navigate } from "react-router-dom";
import { useCurrentUser } from "../../hooks/useAuth";
import { useJabberStatus } from "../../hooks/useJabber";
import { formatDuration } from "../../lib/utils";
import type { JabberSession } from "../../lib/types";

function MetricCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
}) {
  return (
    <div className="border border-gray-200 rounded-md bg-white p-4 flex flex-col gap-1 min-w-0">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider truncate">
        {label}
      </p>
      <p className="text-2xl font-semibold text-gray-900 truncate">{value}</p>
      {sub && <p className="text-xs text-gray-400 truncate">{sub}</p>}
    </div>
  );
}

function SessionsTable({ sessions }: { sessions: JabberSession[] }) {
  if (sessions.length === 0) {
    return (
      <p className="text-sm text-gray-400 py-4" data-testid="jabber-sessions-empty">
        No active XMPP sessions.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto border border-gray-200 rounded-md">
      <table className="w-full text-sm" data-testid="jabber-sessions-table">
        <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wider">
          <tr>
            <th className="text-left font-medium px-3 py-2">JID</th>
            <th className="text-left font-medium px-3 py-2">Client</th>
            <th className="text-left font-medium px-3 py-2">IP</th>
            <th className="text-left font-medium px-3 py-2">Connected</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {sessions.map((s) => (
            <tr key={`${s.jid}-${s.ip}`}>
              <td className="px-3 py-2 text-gray-800 font-mono text-xs truncate max-w-[18rem]">
                {s.jid}
              </td>
              <td className="px-3 py-2 text-gray-700">{s.client}</td>
              <td className="px-3 py-2 text-gray-700 font-mono text-xs">{s.ip}</td>
              <td className="px-3 py-2 text-gray-700">
                {formatDuration(s.connected_seconds)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function JabberDashboard() {
  const { data: me, isLoading: meLoading } = useCurrentUser();
  const { data, isLoading, isError, error } = useJabberStatus();

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
        <h1 className="text-xl font-semibold text-gray-900">Jabber connection dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">
          Live XMPP server state — polled every 10 s.
        </p>
      </header>

      {isLoading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : isError ? (
        <p className="text-sm text-gray-400">
          {error instanceof Error ? error.message : "Could not load XMPP status."}
        </p>
      ) : data ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <MetricCard label="XMPP Server" value={data.server_host} sub="Virtual host" />
            <MetricCard label="Connected clients" value={data.connected_clients} />
            <MetricCard label="S2S Links" value={data.s2s_links_active} sub="Active federation peers" />
            <MetricCard label="Uptime" value={formatDuration(data.uptime_seconds)} />
          </div>

          <section>
            <div className="flex items-baseline justify-between mb-2">
              <h2 className="text-sm font-semibold text-gray-900">Active XMPP Sessions</h2>
              {data.truncated && (
                <span className="text-xs text-amber-600">
                  Showing first {data.sessions.length} (truncated)
                </span>
              )}
            </div>
            <SessionsTable sessions={data.sessions} />
          </section>
        </>
      ) : null}
    </div>
  );
}
