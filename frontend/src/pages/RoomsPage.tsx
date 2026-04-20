import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useJoinRoom, useMyRooms, usePublicRooms } from "../hooks/useRooms";
import type { RoomPublic } from "../lib/types";

function RoomCard({
  room,
  isMember,
  onJoin,
  onOpen,
  joinPending,
}: {
  room: RoomPublic;
  isMember: boolean;
  onJoin: () => void;
  onOpen: () => void;
  joinPending: boolean;
}) {
  return (
    <div className="border border-gray-200 rounded-md p-4 flex items-start gap-3">
      <div className="flex-1 min-w-0">
        <p className="font-medium text-gray-900 text-sm truncate"># {room.name}</p>
        {room.description && (
          <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{room.description}</p>
        )}
        <p className="text-xs text-gray-400 mt-1">{room.member_count} member(s)</p>
      </div>
      {isMember ? (
        <button
          onClick={onOpen}
          className="text-xs px-3 py-1.5 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
        >
          Open
        </button>
      ) : (
        <button
          onClick={onJoin}
          disabled={joinPending}
          className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {joinPending ? "Joining…" : "Join"}
        </button>
      )}
    </div>
  );
}

export default function RoomsPage() {
  const [search, setSearch] = useState("");
  const { data: rooms = [], isLoading, isError } = usePublicRooms(search || undefined);
  const { data: myRooms = [] } = useMyRooms();
  const joinRoom = useJoinRoom();
  const navigate = useNavigate();

  const myRoomIds = new Set(myRooms.map((r) => r.id));

  const handleJoin = async (roomId: string) => {
    await joinRoom.mutateAsync(roomId);
    navigate(`/chat/rooms/${roomId}`);
  };

  return (
    <div className="max-w-2xl mx-auto p-6 h-full overflow-y-auto">
      <h1 className="text-xl font-semibold text-gray-900 mb-4">Discover rooms</h1>
      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search rooms…"
        aria-label="Search rooms"
        className="w-full border border-gray-300 rounded px-3 py-2 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500"
      />

      {isLoading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : isError ? (
        <p className="text-sm text-gray-400">Could not load rooms</p>
      ) : rooms.length === 0 ? (
        <p className="text-sm text-gray-400">No rooms match your search.</p>
      ) : (
        <div className="space-y-2">
          {rooms.map((room) => (
            <RoomCard
              key={room.id}
              room={room}
              isMember={myRoomIds.has(room.id)}
              onJoin={() => handleJoin(room.id)}
              onOpen={() => navigate(`/chat/rooms/${room.id}`)}
              joinPending={joinRoom.isPending && joinRoom.variables === room.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
