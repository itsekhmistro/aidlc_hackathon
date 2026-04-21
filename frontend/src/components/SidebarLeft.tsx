import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import AddFriendModal from "./AddFriendModal";
import ContactRow from "./ContactRow";
import CreateRoomForm from "./CreateRoomForm";
import RequestRow from "./RequestRow";
import RoomInviteRow from "./RoomInviteRow";
import RoomRow from "./RoomRow";
import { useFriendRequests, useFriends } from "../hooks/useFriends";
import { useMyRoomInvitations, useMyRooms } from "../hooks/useRooms";
import { clearUnread } from "../lib/unreadStore";
import { api } from "../lib/api";

export default function SidebarLeft() {
  const { data: friends = [], isError: friendsError } = useFriends();
  const { data: requests = [] } = useFriendRequests();
  const { data: roomInvites = [] } = useMyRoomInvitations();
  const { data: rooms = [], isError: roomsError } = useMyRooms();
  const [showAddFriend, setShowAddFriend] = useState(false);
  const [showCreateRoom, setShowCreateRoom] = useState(false);
  const [contactsCollapsed, setContactsCollapsed] = useState(false);
  const [roomsCollapsed, setRoomsCollapsed] = useState(false);

  const navigate = useNavigate();
  const params = useParams<{ roomId?: string }>();
  const location = useLocation();
  const activeRoomId = params.roomId ?? null;
  const isOnDm = location.pathname.startsWith("/chat/dm/");

  // Auto-collapse the non-active section when a room/DM is open. Resets every
  // time the active surface changes; user toggles after that point win until
  // the next navigation.
  useEffect(() => {
    if (isOnDm) {
      setRoomsCollapsed(true);
      setContactsCollapsed(false);
    } else if (activeRoomId) {
      setContactsCollapsed(true);
      setRoomsCollapsed(false);
    } else {
      setContactsCollapsed(false);
      setRoomsCollapsed(false);
    }
  }, [activeRoomId, isOnDm]);

  const handleRoomClick = (roomId: string) => {
    clearUnread(roomId);
    api.post(`/api/unread/${roomId}/mark-read`).catch(() => {});
    navigate(`/chat/rooms/${roomId}`);
  };

  const Caret = ({ collapsed }: { collapsed: boolean }) => (
    <span
      aria-hidden="true"
      className={`text-[10px] text-gray-400 transition-transform ${
        collapsed ? "" : "rotate-90"
      }`}
    >
      ▶
    </span>
  );

  return (
    <aside className="w-64 bg-white border-r border-gray-200 flex flex-col h-full">
      {/* Incoming requests */}
      {requests.length > 0 && (
        <div className="px-3 pt-3">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider px-1 mb-1">
            Requests ({requests.length})
          </p>
          {requests.map((req) => (
            <RequestRow key={req.id} req={req} />
          ))}
        </div>
      )}

      {/* Incoming room invitations */}
      {roomInvites.length > 0 && (
        <div className="px-3 pt-3">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider px-1 mb-1">
            Room invites ({roomInvites.length})
          </p>
          {roomInvites.map((inv) => (
            <RoomInviteRow key={inv.id} invite={inv} />
          ))}
        </div>
      )}

      {/* Scrollable content area */}
      <div className="flex-1 overflow-y-auto px-3 pt-3 space-y-4">
        {/* Contacts */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <button
              type="button"
              onClick={() => setContactsCollapsed((v) => !v)}
              aria-expanded={!contactsCollapsed}
              aria-controls="sidebar-contacts"
              className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wider px-1 hover:text-gray-700"
            >
              <Caret collapsed={contactsCollapsed} />
              Contacts
            </button>
            <button
              onClick={() => setShowAddFriend(true)}
              className="text-xs text-blue-600 hover:text-blue-800 px-1"
              title="Add friend"
            >
              + Add
            </button>
          </div>

          {!contactsCollapsed && (
            <div id="sidebar-contacts">
              {friendsError ? (
                <p className="text-xs text-gray-400 px-2 py-1">Could not load contacts</p>
              ) : friends.length === 0 ? (
                <p className="text-xs text-gray-400 px-2 py-1">No contacts yet</p>
              ) : (
                friends.map((f) => <ContactRow key={f.id} friendship={f} />)
              )}
            </div>
          )}
        </div>

        {/* Rooms */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <button
              type="button"
              onClick={() => setRoomsCollapsed((v) => !v)}
              aria-expanded={!roomsCollapsed}
              aria-controls="sidebar-rooms"
              className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wider px-1 hover:text-gray-700"
            >
              <Caret collapsed={roomsCollapsed} />
              Rooms
            </button>
            <button
              onClick={() => setShowCreateRoom((v) => !v)}
              className="text-xs text-blue-600 hover:text-blue-800 px-1"
              title="Create room"
            >
              + New
            </button>
          </div>

          {!roomsCollapsed && (
            <div id="sidebar-rooms">
              {showCreateRoom && <CreateRoomForm onClose={() => setShowCreateRoom(false)} />}

              {roomsError ? (
                <p className="text-xs text-gray-400 px-2 py-1">Could not load rooms</p>
              ) : rooms.length === 0 ? (
                <p className="text-xs text-gray-400 px-2 py-1">No rooms yet</p>
              ) : (
                rooms.map((room) => (
                  <RoomRow
                    key={room.id}
                    room={room}
                    isActive={room.id === activeRoomId}
                    onClick={() => handleRoomClick(room.id)}
                  />
                ))
              )}

              <Link
                to="/rooms"
                className="mt-2 block text-xs text-blue-600 hover:text-blue-800 px-3 py-1"
              >
                Discover rooms →
              </Link>
            </div>
          )}
        </div>
      </div>

      {showAddFriend && <AddFriendModal onClose={() => setShowAddFriend(false)} />}
    </aside>
  );
}
