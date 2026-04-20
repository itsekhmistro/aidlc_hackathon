import { useAcceptFriendRequest, useRemoveFriend } from "../hooks/useFriends";
import type { FriendshipPublic } from "../lib/types";

export default function RequestRow({ req }: { req: FriendshipPublic }) {
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
