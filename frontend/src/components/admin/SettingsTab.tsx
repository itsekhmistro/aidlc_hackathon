import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDeleteRoom, useUpdateRoom } from "../../hooks/useAdmin";
import type { RoomPublic, RoomVisibility } from "../../lib/types";

interface Props {
  room: RoomPublic;
  canEdit: boolean;
  onClose: () => void;
}

export default function SettingsTab({ room, canEdit, onClose }: Props) {
  const navigate = useNavigate();
  const update = useUpdateRoom();
  const deleteRoom = useDeleteRoom();

  const [name, setName] = useState(room.name);
  const [description, setDescription] = useState(room.description ?? "");
  const [visibility, setVisibility] = useState<RoomVisibility>(room.visibility);
  const [confirmInput, setConfirmInput] = useState("");
  const [showDelete, setShowDelete] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    update.mutate({
      roomId: room.id,
      patch: { name, description: description || null, visibility },
    });
  };

  const handleDelete = () => {
    deleteRoom.mutate(room.id, {
      onSuccess: () => {
        onClose();
        navigate("/chat", { replace: true });
      },
    });
  };

  return (
    <div className="space-y-4">
      <form onSubmit={handleSave} className="space-y-3">
        <div className="space-y-1">
          <label className="text-xs font-medium text-gray-600">Room name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={!canEdit}
            className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm disabled:bg-gray-50 disabled:text-gray-500"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-gray-600">Description</label>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={!canEdit}
            className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm disabled:bg-gray-50 disabled:text-gray-500"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-gray-600">Visibility</label>
          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-1">
              <input
                type="radio"
                name="visibility"
                value="public"
                checked={visibility === "public"}
                onChange={() => setVisibility("public")}
                disabled={!canEdit}
              />
              Public
            </label>
            <label className="flex items-center gap-1">
              <input
                type="radio"
                name="visibility"
                value="private"
                checked={visibility === "private"}
                onChange={() => setVisibility("private")}
                disabled={!canEdit}
              />
              Private
            </label>
          </div>
        </div>
        {update.isError && (
          <p className="text-xs text-red-600">{(update.error as Error).message}</p>
        )}
        {canEdit && (
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={update.isPending}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {update.isPending ? "Saving…" : "Save changes"}
            </button>
          </div>
        )}
      </form>

      {canEdit && (
        <div className="pt-4 border-t border-gray-200">
          {!showDelete ? (
            <button
              type="button"
              onClick={() => setShowDelete(true)}
              className="px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded"
            >
              Delete room
            </button>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-gray-700">
                Type the room name <strong>{room.name}</strong> to confirm deletion.
              </p>
              <input
                value={confirmInput}
                onChange={(e) => setConfirmInput(e.target.value)}
                placeholder={room.name}
                aria-label="Confirm room name"
                className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm"
              />
              {deleteRoom.isError && (
                <p className="text-xs text-red-600">
                  {(deleteRoom.error as Error).message}
                </p>
              )}
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => {
                    setShowDelete(false);
                    setConfirmInput("");
                  }}
                  className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={confirmInput !== room.name || deleteRoom.isPending}
                  className="px-3 py-1.5 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                >
                  {deleteRoom.isPending ? "Deleting…" : "Delete room"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
