import { useCurrentUser } from "../hooks/useAuth";
import { useRoomDetail } from "../hooks/useRooms";
import { useRoomMembers } from "../hooks/useRoomMembers";
import type { MemberRole } from "../lib/types";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import MembersTab from "./admin/MembersTab";
import BannedTab from "./admin/BannedTab";
import InvitationsTab from "./admin/InvitationsTab";
import SettingsTab from "./admin/SettingsTab";

interface Props {
  roomId: string;
  onClose: () => void;
}

export default function ManageRoomModal({ roomId, onClose }: Props) {
  const { data: me } = useCurrentUser();
  const { data: members = [] } = useRoomMembers(roomId);
  const { data: room } = useRoomDetail(roomId);

  const myRole: MemberRole =
    members.find((m) => m.user_id === me?.id)?.role ?? "member";
  const isAdmin = myRole === "owner" || myRole === "admin";

  if (!isAdmin) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-xl p-6 w-[32rem] max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-900">
            Manage room {room ? `· #${room.display_name}` : ""}
          </h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-gray-500 hover:text-gray-800"
          >
            ✕
          </button>
        </div>
        <Tabs defaultValue="members" className="flex-1 overflow-hidden flex flex-col">
          <TabsList className="mb-4">
            <TabsTrigger value="members">Members</TabsTrigger>
            <TabsTrigger value="banned">Banned</TabsTrigger>
            <TabsTrigger value="invitations">Invitations</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
          </TabsList>
          <div className="flex-1 overflow-y-auto">
            <TabsContent value="members">
              <MembersTab
                roomId={roomId}
                myRole={myRole}
                roomName={room?.name ?? ""}
              />
            </TabsContent>
            <TabsContent value="banned">
              <BannedTab roomId={roomId} />
            </TabsContent>
            <TabsContent value="invitations">
              <InvitationsTab roomId={roomId} />
            </TabsContent>
            <TabsContent value="settings">
              {room ? (
                <SettingsTab
                  room={room}
                  canEdit={myRole === "owner"}
                  onClose={onClose}
                />
              ) : (
                <p className="text-xs text-gray-400">Loading room…</p>
              )}
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </div>
  );
}
