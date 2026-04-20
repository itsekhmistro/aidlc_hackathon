import { useState } from "react";
import { useSendFriendRequest } from "../hooks/useFriends";

export default function AddFriendModal({ onClose }: { onClose: () => void }) {
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
