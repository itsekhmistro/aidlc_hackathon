import { Outlet, useMatch } from "react-router-dom";
import { usePersonalRoomForUser } from "../hooks/useRooms";
import SidebarLeft from "./SidebarLeft";
import SidebarRight from "./SidebarRight";
import TopNav from "./TopNav";

export default function AppShell() {
  const roomMatch = useMatch("/chat/rooms/:roomId");
  const dmMatch = useMatch("/chat/dm/:userId");

  const urlRoomId = roomMatch?.params.roomId ?? null;
  const dmUserId = dmMatch?.params.userId ?? null;

  // Resolve the personal room for DM routes so we know which members list
  // to show in the right sidebar.
  const dmRoom = usePersonalRoomForUser(dmUserId);
  const activeRoomId = urlRoomId ?? dmRoom.data?.id ?? null;

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <TopNav />
      <div className="flex flex-1 overflow-hidden">
        <SidebarLeft />
        <main className="flex-1 overflow-hidden">
          <Outlet />
        </main>
        {activeRoomId && <SidebarRight roomId={activeRoomId} />}
      </div>
    </div>
  );
}
