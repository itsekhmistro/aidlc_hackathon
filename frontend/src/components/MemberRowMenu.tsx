import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useFriends, useSendFriendRequest } from "../hooks/useFriends";
import { usePersonalRoom } from "../hooks/useRooms";
import { useBanMember, useGrantAdmin, useRemoveAdmin } from "../hooks/useAdmin";
import ConfirmModal from "./ConfirmModal";
import type { MemberRole, RoomMemberPublic } from "../lib/types";

interface Props {
  roomId: string;
  roomName: string;
  member: RoomMemberPublic;
  myRole: MemberRole;
  meId: string;
}

export default function MemberRowMenu({
  roomId,
  roomName,
  member,
  myRole,
  meId,
}: Props) {
  const [open, setOpen] = useState(false);
  const [confirmBan, setConfirmBan] = useState(false);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  const navigate = useNavigate();
  const { data: friends = [] } = useFriends();
  const personalRoom = usePersonalRoom();
  const sendFriendRequest = useSendFriendRequest();
  const grantAdmin = useGrantAdmin();
  const removeAdmin = useRemoveAdmin();
  const banMember = useBanMember();

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!wrapperRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const isSelf = member.user_id === meId;
  if (isSelf) return null;

  const isFriend = friends.some(
    (f) =>
      f.status === "accepted" &&
      (f.requester_id === member.user_id || f.addressee_id === member.user_id),
  );
  const canActOn =
    member.role !== "owner" &&
    (myRole === "owner" || (myRole === "admin" && member.role === "member"));

  const handleSendMessage = async () => {
    setOpen(false);
    try {
      await personalRoom.mutateAsync(member.user_id);
      navigate(`/chat/dm/${member.user_id}`);
    } catch {
      // personal-rooms endpoint may 403 if friendship missing; surface nothing.
    }
  };

  const handleSendFriendRequest = () => {
    setOpen(false);
    sendFriendRequest.mutate({ username: member.username });
  };

  const handleGrantAdmin = () => {
    setOpen(false);
    grantAdmin.mutate({ roomId, userId: member.user_id });
  };

  const handleRemoveAdmin = () => {
    setOpen(false);
    removeAdmin.mutate({ roomId, userId: member.user_id });
  };

  return (
    <div ref={wrapperRef} className="relative">
      <button
        type="button"
        aria-label={`Actions for ${member.username}`}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-gray-600 text-xs px-1 focus:opacity-100"
      >
        ···
      </button>

      {open && (
        <div className="absolute right-0 top-6 z-20 bg-white border border-gray-200 rounded-md shadow-lg py-1 w-44">
          <button
            type="button"
            onClick={handleSendMessage}
            disabled={personalRoom.isPending}
            className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            {personalRoom.isPending ? "Opening…" : "Send message"}
          </button>
          {!isFriend && (
            <button
              type="button"
              onClick={handleSendFriendRequest}
              disabled={sendFriendRequest.isPending}
              className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              Send friend request
            </button>
          )}
          {myRole === "owner" && member.role === "member" && (
            <button
              type="button"
              onClick={handleGrantAdmin}
              className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50"
            >
              Make admin
            </button>
          )}
          {myRole === "owner" && member.role === "admin" && (
            <button
              type="button"
              onClick={handleRemoveAdmin}
              className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50"
            >
              Remove admin
            </button>
          )}
          {canActOn && (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                setConfirmBan(true);
              }}
              className="w-full text-left px-3 py-1.5 text-sm text-red-600 hover:bg-red-50"
            >
              Ban from room
            </button>
          )}
        </div>
      )}

      {confirmBan && (
        <ConfirmModal
          title="Ban member"
          body={`Ban ${member.username} from #${roomName}? They will not be able to rejoin.`}
          confirmLabel="Ban"
          danger
          pending={banMember.isPending}
          onCancel={() => setConfirmBan(false)}
          onConfirm={() => {
            banMember.mutate(
              { roomId, userId: member.user_id },
              { onSuccess: () => setConfirmBan(false) },
            );
          }}
        />
      )}
    </div>
  );
}
