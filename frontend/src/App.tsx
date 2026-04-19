import { useCallback, useState } from "react";
import { Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import { useLogout } from "./hooks/useAuth";
import { useWebSocket } from "./hooks/useWebSocket";
import type { ServerEvent } from "./lib/types";
import LoginPage from "./pages/LoginPage";

const CLIENT_ID = crypto.randomUUID();
const WS_URL = `ws://localhost:8000/ws/${CLIENT_ID}`;

function Dashboard() {
  const [events, setEvents] = useState<ServerEvent[]>([]);
  const logout = useLogout();

  const handleMessage = useCallback((data: ServerEvent) => {
    setEvents((prev) => [...prev.slice(-99), data]);
  }, []);

  const { sendMessage, readyState } = useWebSocket<ServerEvent>(WS_URL, {
    onMessage: handleMessage,
  });

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Hackathon App</h1>
        <button
          onClick={logout}
          className="text-sm text-gray-500 hover:text-gray-700 underline"
        >
          Sign out
        </button>
      </div>
      <p className="mb-4 text-sm text-gray-500">
        WS: <span className="font-mono">{readyState}</span>
      </p>
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => sendMessage({ type: "ping" })}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
        >
          Ping
        </button>
        <button
          onClick={() => sendMessage({ type: "broadcast", payload: "hello everyone" })}
          className="px-4 py-2 bg-green-600 text-white text-sm rounded hover:bg-green-700"
        >
          Broadcast
        </button>
      </div>
      <div className="space-y-1">
        {events.map((e, i) => (
          <pre key={i} className="text-xs bg-white border rounded p-2 font-mono">
            {JSON.stringify(e)}
          </pre>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="*" element={<Dashboard />} />
      </Route>
    </Routes>
  );
}
