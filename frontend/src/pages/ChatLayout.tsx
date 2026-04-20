import { useState } from "react";
import MessageThread from "../components/MessageThread";
import { PresenceDot } from "../components/PresenceDot";
import { useCurrentUser, useLogout } from "../hooks/useAuth";
import {
  useAcceptFriendRequest,
  useBanUser,
  useFriendRequests,
  useFriends,
  useRemoveFriend,
  useSendFriendRequest,
} from "../hooks/useFriends";
import { useCreateRoom, useMyRooms } from "../hooks/useRooms";
import type { FriendshipPublic, RoomPublic, RoomVisibility } from "../lib/types";
import { usePresence } from "../lib/presenceStore";

// ── Contact row ────────────────────────────────────────────────────────────────

function ContactRow({ friendship }: { friendship: FriendshipPublic }) {
  const { data: me } = useCurrentUser();
  const removeFriend = useRemoveFriend();
  const banUser = useBanUser();
  const [showMenu, setShowMenu] = useState(false);
  const [showBanConfirm, setShowBanConfirm] = useState(false);

  const otherId =
    friendship.requester_id === me?.id ? friendship.addressee_id : friendship.requester_id;
  const otherName =
    friendship.requester_id === me?.id ? friendship.addressee_username : friendship.requester_username;
  const presence = usePresence(otherId);

  const handleBan = async () => {
    await banUser.mutateAsync(otherId);
    setShowBanConfirm(false);
  };

  return (
    <div className="relative">
      <div
        className="flex items-center gap-2 px-3 py-2 rounded-md hover:bg-gray-100 cursor-pointer group"
        onClick={() => setShowMenu(false)}
      >
        <PresenceDot status={presence} />
        <span className="text-sm text-gray-800 flex-1 truncate">{otherName}</span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            setShowMenu((v) => !v);
          }}
          className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-gray-600 text-xs px-1"
        >
          ···
        </button>
      </div>

      {showMenu && (
        <div className="absolute right-0 top-8 z-10 bg-white border border-gray-200 rounded-md shadow-lg py-1 w-40">
          <button className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50">
            Send message
          </button>
          <button
            onClick={() => { removeFriend.mutate(friendship.id); setShowMenu(false); }}
            className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 text-gray-700"
          >
            Remove friend
          </button>
          <button
            onClick={() => { setShowBanConfirm(true); setShowMenu(false); }}
            className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 text-red-600"
          >
            Ban user
          </button>
        </div>
      )}

      {showBanConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 w-80 space-y-4">
            <h3 className="font-semibold text-gray-900">Ban {otherName}?</h3>
            <p className="text-sm text-gray-600">
              They will no longer be able to contact you. Existing history remains visible.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowBanConfirm(false)}
                className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={handleBan}
                disabled={banUser.isPending}
                className="px-3 py-1.5 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
              >
                {banUser.isPending ? "Banning…" : "Ban"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Friend request row ─────────────────────────────────────────────────────────

function RequestRow({ req }: { req: FriendshipPublic }) {
  const accept = useAcceptFriendRequest();
  const decline = useRemoveFriend();

  return (
    <div className="flex items-center gap-2 px-3 py-2">
      <span className="text-sm text-gray-700 flex-1 truncate">
        <span className="font-medium">{req.requester_username}</span>
        {req.message && (
          <span className="text-gray-400 ml-1 italic text-xs">"{req.message}"</span>
        )}
      </span>
      <button
        onClick={() => accept.mutate(req.id)}
        disabled={accept.isPending}
        className="text-xs px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
      >
        ✓
      </button>
      <button
        onClick={() => decline.mutate(req.id)}
        disabled={decline.isPending}
        className="text-xs px-2 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
      >
        ✕
      </button>
    </div>
  );
}

// ── Add friend modal ───────────────────────────────────────────────────────────

function AddFriendModal({ onClose }: { onClose: () => void }) {
  const send = useSendFriendRequest();
  const [username, setUsername] = useState("");
  const [message, setMessage] = useState("");
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await send.mutateAsync({ username: username.trim(), message: message.trim() || undefined });
    setDone(true);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-xl p-6 w-80 space-y-4">
        <h3 className="font-semibold text-gray-900">Add friend</h3>
        {done ? (
          <div className="space-y-3">
            <p className="text-sm text-green-600">Friend request sent!</p>
            <button
              onClick={onClose}
              className="w-full px-3 py-1.5 text-sm bg-gray-100 rounded hover:bg-gray-200"
            >
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-3">
            {send.isError && (
              <p className="text-xs text-red-600">{(send.error as Error).message}</p>
            )}
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-600">Username</label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="johndoe"
                autoFocus
                required
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-600">Message (optional)</label>
              <input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Hey, let's chat!"
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={send.isPending || !username.trim()}
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {send.isPending ? "Sending…" : "Send request"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

// ── Room row ───────────────────────────────────────────────────────────────────

function RoomRow({
  room,
  isActive,
  onClick,
}: {
  room: RoomPublic;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${
        isActive
          ? "bg-blue-100 text-blue-800 font-medium"
          : "text-gray-700 hover:bg-gray-100"
      }`}
    >
      <span className="text-gray-400">#</span>
      <span className="flex-1 truncate">{room.name}</span>
      {room.is_personal && (
        <span className="text-xs text-gray-400">personal</span>
      )}
    </button>
  );
}

// ── Create room form ───────────────────────────────────────────────────────────

function CreateRoomForm({ onClose }: { onClose: () => void }) {
  const createRoom = useCreateRoom();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [visibility, setVisibility] = useState<RoomVisibility>("public");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    await createRoom.mutateAsync({
      name: name.trim(),
      description: description.trim() || null,
      visibility,
    });
    onClose();
  };

  return (
    <form onSubmit={handleSubmit} className="px-3 pb-2 space-y-2">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Room name"
        autoFocus
        required
        className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <input
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Description (optional)"
        className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <select
        value={visibility}
        onChange={(e) => setVisibility(e.target.value as RoomVisibility)}
        className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <option value="public">Public</option>
        <option value="private">Private</option>
      </select>
      {createRoom.isError && (
        <p className="text-xs text-red-600">{(createRoom.error as Error).message}</p>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={createRoom.isPending || !name.trim()}
          className="flex-1 text-xs bg-blue-600 text-white rounded py-1 hover:bg-blue-700 disabled:opacity-50"
        >
          {createRoom.isPending ? "Creating…" : "Create"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="flex-1 text-xs bg-gray-100 text-gray-700 rounded py-1 hover:bg-gray-200"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

// ── Sidebar ────────────────────────────────────────────────────────────────────

interface SidebarProps {
  activeRoomId: string | null;
  onRoomSelect: (roomId: string) => void;
}

function Sidebar({ activeRoomId, onRoomSelect }: SidebarProps) {
  const { data: me } = useCurrentUser();
  const logout = useLogout();
  const { data: friends = [], isError: friendsError } = useFriends();
  const { data: requests = [] } = useFriendRequests();
  const { data: rooms = [], isError: roomsError } = useMyRooms();
  const [showAddFriend, setShowAddFriend] = useState(false);
  const [showCreateRoom, setShowCreateRoom] = useState(false);

  return (
    <aside className="w-64 bg-white border-r border-gray-200 flex flex-col h-screen">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <span className="font-semibold text-gray-900 text-sm">{me?.username}</span>
        <button
          onClick={() => logout.mutate()}
          className="text-xs text-gray-400 hover:text-gray-600"
        >
          sign out
        </button>
      </div>

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

      {/* Scrollable content area */}
      <div className="flex-1 overflow-y-auto px-3 pt-3 space-y-4">
        {/* Contacts */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider px-1">
              Contacts
            </p>
            <button
              onClick={() => setShowAddFriend(true)}
              className="text-xs text-blue-600 hover:text-blue-800 px-1"
              title="Add friend"
            >
              + Add
            </button>
          </div>

          {friendsError ? (
            <p className="text-xs text-gray-400 px-2 py-1">Could not load contacts</p>
          ) : friends.length === 0 ? (
            <p className="text-xs text-gray-400 px-2 py-1">No contacts yet</p>
          ) : (
            friends.map((f) => <ContactRow key={f.id} friendship={f} />)
          )}
        </div>

        {/* Rooms */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider px-1">
              Rooms
            </p>
            <button
              onClick={() => setShowCreateRoom((v) => !v)}
              className="text-xs text-blue-600 hover:text-blue-800 px-1"
              title="Create room"
            >
              + New
            </button>
          </div>

          {showCreateRoom && (
            <CreateRoomForm onClose={() => setShowCreateRoom(false)} />
          )}

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
                onClick={() => onRoomSelect(room.id)}
              />
            ))
          )}
        </div>
      </div>

      {showAddFriend && <AddFriendModal onClose={() => setShowAddFriend(false)} />}
    </aside>
  );
}

// ── Chat layout ────────────────────────────────────────────────────────────────

export default function ChatLayout({ children }: { children?: React.ReactNode }) {
  const { data: me } = useCurrentUser();
  const { data: rooms = [] } = useMyRooms();
  const [activeRoomId, setActiveRoomId] = useState<string | null>(null);

  const activeRoom = rooms.find((r) => r.id === activeRoomId) ?? null;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar activeRoomId={activeRoomId} onRoomSelect={setActiveRoomId} />
      <main className="flex-1 overflow-hidden">
        {activeRoom && me ? (
          <MessageThread room={activeRoom} currentUserId={me.id} />
        ) : children ? (
          <div className="overflow-auto h-full">{children}</div>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            Select a room to start chatting
          </div>
        )}
      </main>
    </div>
  );
}
