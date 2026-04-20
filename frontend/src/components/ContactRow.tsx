import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PresenceDot } from "./PresenceDot";
import { useCurrentUser } from "../hooks/useAuth";
import { useBanUser, useRemoveFriend } from "../hooks/useFriends";
import { usePersonalRoom } from "../hooks/useRooms";
import type { FriendshipPublic } from "../lib/types";
import { usePresence } from "../lib/presenceStore";

export default function ContactRow({ friendship }: { friendship: FriendshipPublic }) {
  const { data: me } = useCurrentUser();
  const removeFriend = useRemoveFriend();
  const banUser = useBanUser();
  const personalRoom = usePersonalRoom();
  const navigate = useNavigate();
  const [showMenu, setShowMenu] = useState(false);
  const [showBanConfirm, setShowBanConfirm] = useState(false);

  const otherId =
    friendship.requester_id === me?.id ? friendship.addressee_id : friendship.requester_id;
  const otherName =
    friendship.requester_id === me?.id
      ? friendship.addressee_username
      : friendship.requester_username;
  const presence = usePresence(otherId);

  const handleSendMessage = async () => {
    setShowMenu(false);
    // Resolve/ensure personal room exists, then navigate by userId.
    await personalRoom.mutateAsync(otherId);
    navigate(`/chat/dm/${otherId}`);
  };

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
          <button
            onClick={handleSendMessage}
            disabled={personalRoom.isPending}
            className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            {personalRoom.isPending ? "Opening…" : "Send message"}
          </button>
          <button
            onClick={() => {
              removeFriend.mutate(friendship.id);
              setShowMenu(false);
            }}
            className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 text-gray-700"
          >
            Remove friend
          </button>
          <button
            onClick={() => {
              setShowBanConfirm(true);
              setShowMenu(false);
            }}
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
