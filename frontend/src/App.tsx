import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import AppShell from "./components/AppShell";
import ProtectedRoute from "./components/ProtectedRoute";
import { useActivityTracker } from "./hooks/useActivityTracker";
import { useCurrentUser } from "./hooks/useAuth";
import { useWebSocket } from "./hooks/useWebSocket";
import { setBulkPresence, setPresence } from "./lib/presenceStore";
import { setUnreadCounts, incrementUnread, clearUnread, useTotalUnread } from "./lib/unreadStore";
import { api } from "./lib/api";
import { handleSessionRevoked } from "./lib/sessionRevoked";
import type { ClientEvent, RoomMemberPublic, ServerEvent, UnreadCountsPublic } from "./lib/types";
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
  const navigate = useNavigate();

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
        // Kick the banned user out of any DM they're actively viewing with the banner.
        const path = window.location.pathname;
        const dmMatch = path.match(/^\/chat\/dm\/([^/]+)$/);
        if (dmMatch && dmMatch[1] === event.banner_id) {
          navigate("/chat", { replace: true });
        } else {
          const roomMatch = path.match(/^\/chat\/rooms\/([^/]+)$/);
          if (roomMatch) {
            const members = qc.getQueryData<RoomMemberPublic[]>(["rooms", roomMatch[1], "members"]);
            if (members?.some((m) => m.user_id === event.banner_id)) {
              navigate("/chat", { replace: true });
            }
          }
        }
      } else if (event.type === "unread.increment") {
        // Suppress the badge when the user is already viewing the room; keep the
        // server-side receipt fresh so the badge stays at 0 after relogin too.
        if (window.location.pathname === `/chat/rooms/${event.room_id}`) {
          api.post(`/api/unread/${event.room_id}/mark-read`).catch(() => {});
          return;
        }
        incrementUnread(event.room_id);
      } else if (event.type === "unread.cleared") {
        clearUnread(event.room_id);
      } else if (event.type === "session.revoked") {
        handleSessionRevoked(qc, navigate);
      }
    },
    [qc, navigate],
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

  // Mirror total unread count into the browser tab title
  const totalUnread = useTotalUnread();
  useEffect(() => {
    document.title = totalUnread > 0 ? `(${totalUnread > 99 ? "99+" : totalUnread}) Chat` : "Chat";
  }, [totalUnread]);

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
