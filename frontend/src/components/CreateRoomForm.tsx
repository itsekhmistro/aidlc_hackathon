import { useState } from "react";
import { useCreateRoom } from "../hooks/useRooms";
import type { RoomVisibility } from "../lib/types";

export default function CreateRoomForm({ onClose }: { onClose: () => void }) {
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
