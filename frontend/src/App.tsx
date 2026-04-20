import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import ProtectedRoute from "./components/ProtectedRoute";
import { useActivityTracker } from "./hooks/useActivityTracker";
import { useCurrentUser } from "./hooks/useAuth";
import { useWebSocket } from "./hooks/useWebSocket";
import { setBulkPresence, setPresence } from "./lib/presenceStore";
import { setUnreadCounts, incrementUnread, clearUnread } from "./lib/unreadStore";
import { api } from "./lib/api";
import type { ClientEvent, ServerEvent, UnreadCountsPublic } from "./lib/types";
import ChatEmpty from "./pages/ChatEmpty";
import DmChatPage from "./pages/DmChatPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import LoginPage from "./pages/LoginPage";
import ProfilePage from "./pages/ProfilePage";
import RegisterPage from "./pages/RegisterPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import RoomChatPage from "./pages/RoomChatPage";
import RoomsPage from "./pages/RoomsPage";
import SessionsPage from "./pages/SessionsPage";

// Stable tab ID persisted across soft reloads, gone on tab close
const TAB_ID = (() => {
  const stored = sessionStorage.getItem("tab_id");
  if (stored) return stored;
  const id = crypto.randomUUID?.() ?? Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
  sessionStorage.setItem("tab_id", id);
  return id;
})();

const WS_URL = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws?tab_id=${TAB_ID}`;

function AppWebSocket() {
  const { data: me } = useCurrentUser();
  const isAuthenticated = !!me;
  const qc = useQueryClient();

  const handleMessage = useCallback(
    (event: ServerEvent) => {
      if (event.type === "presence.update") {
        setPresence(event.user_id, event.status);
      } else if (event.type === "presence.bulk") {
        setBulkPresence(event.presences);
      } else if (event.type === "message.new") {
        qc.invalidateQueries({ queryKey: ["messages", event.room_id] });
      } else if (event.type === "message.edited") {
        qc.invalidateQueries({ queryKey: ["messages", event.message.room_id] });
      } else if (event.type === "message.deleted") {
        qc.invalidateQueries({ queryKey: ["messages", event.room_id] });
      } else if (event.type === "friend.request_received") {
        qc.invalidateQueries({ queryKey: ["friends", "requests"] });
      } else if (event.type === "friend.accepted") {
        qc.invalidateQueries({ queryKey: ["friends"] });
      } else if (event.type === "friend.removed") {
        qc.invalidateQueries({ queryKey: ["friends"] });
      } else if (event.type === "user.banned") {
        qc.invalidateQueries({ queryKey: ["friends"] });
        qc.invalidateQueries({ queryKey: ["bans"] });
      } else if (event.type === "unread.increment") {
        incrementUnread(event.room_id);
      } else if (event.type === "unread.cleared") {
        clearUnread(event.room_id);
      }
    },
    [qc],
  );

  const { sendMessage, readyState } = useWebSocket<ServerEvent>(
    isAuthenticated ? WS_URL : "",
    { onMessage: handleMessage },
  );

  useActivityTracker(TAB_ID, sendMessage as (e: ClientEvent) => void, isAuthenticated && readyState === "open");

  // Ping keepalive every 30s
  useEffect(() => {
    if (!isAuthenticated || readyState !== "open") return;
    const id = setInterval(() => sendMessage({ type: "ping" }), 30_000);
    return () => clearInterval(id);
  }, [isAuthenticated, readyState, sendMessage]);

  // Fetch initial unread counts when user logs in
  useEffect(() => {
    if (!me) return;
    api.get<UnreadCountsPublic>("/api/unread").then((data) => setUnreadCounts(data.counts)).catch(() => {});
  }, [me?.id]);

  return null;
}

export default function App() {
  return (
    <>
      <AppWebSocket />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route element={<AppShell />}>
            <Route path="/chat" element={<ChatEmpty />} />
            <Route path="/chat/rooms/:roomId" element={<RoomChatPage />} />
            <Route path="/chat/dm/:userId" element={<DmChatPage />} />
            <Route path="/rooms" element={<RoomsPage />} />
            <Route path="/sessions" element={<SessionsPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Route>
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Route>
      </Routes>
    </>
  );
}
