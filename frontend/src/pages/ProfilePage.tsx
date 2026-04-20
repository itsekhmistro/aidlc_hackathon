import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useCurrentUser } from "../hooks/useAuth";
import { api } from "../lib/api";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function ChangePasswordForm() {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const change = useMutation({
    mutationFn: (body: { old_password: string; new_password: string }) =>
      api.patch<void>("/api/auth/password-change", body),
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setDone(false);
    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    try {
      await change.mutateAsync({ old_password: oldPassword, new_password: newPassword });
      setDone(true);
      setOldPassword("");
      setNewPassword("");
      setConfirm("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not change password");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3 border border-gray-200 rounded-md p-4">
      <h2 className="text-sm font-semibold text-gray-900">Change password</h2>
      {error && <p className="text-xs text-red-600">{error}</p>}
      {done && <p className="text-xs text-green-600">Password changed.</p>}
      <div className="space-y-1">
        <label className="text-xs font-medium text-gray-600">Current password</label>
        <input
          type="password"
          value={oldPassword}
          onChange={(e) => setOldPassword(e.target.value)}
          required
          className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div className="space-y-1">
        <label className="text-xs font-medium text-gray-600">New password</label>
        <input
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
          className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div className="space-y-1">
        <label className="text-xs font-medium text-gray-600">Confirm new password</label>
        <input
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <button
        type="submit"
        disabled={change.isPending}
        className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
      >
        {change.isPending ? "Saving…" : "Change password"}
      </button>
    </form>
  );
}

function DeleteAccountSection() {
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const qc = useQueryClient();
  const navigate = useNavigate();

  const del = useMutation({
    mutationFn: () => api.delete<void>("/api/auth/account"),
    onSuccess: () => {
      qc.clear();
      navigate("/login");
    },
    onError: (e: unknown) => {
      setError(e instanceof Error ? e.message : "Could not delete account");
    },
  });

  return (
    <div className="space-y-3 border border-red-200 bg-red-50 rounded-md p-4">
      <h2 className="text-sm font-semibold text-red-700">Delete account</h2>
      <p className="text-xs text-red-600">
        This permanently deletes your account, all your rooms, and all your messages. This cannot be undone.
      </p>
      {error && <p className="text-xs text-red-700">{error}</p>}
      {confirming ? (
        <div className="flex gap-2">
          <button
            onClick={() => del.mutate()}
            disabled={del.isPending}
            className="text-xs px-3 py-1.5 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
          >
            {del.isPending ? "Deleting…" : "Yes, delete my account"}
          </button>
          <button
            onClick={() => setConfirming(false)}
            className="text-xs px-3 py-1.5 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          onClick={() => setConfirming(true)}
          className="text-xs px-3 py-1.5 bg-red-600 text-white rounded hover:bg-red-700"
        >
          Delete account
        </button>
      )}
    </div>
  );
}

export default function ProfilePage() {
  const { data: me } = useCurrentUser();

  if (!me) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-sm">
        Loading…
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-6 h-full overflow-y-auto space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">Profile</h1>
      <div className="border border-gray-200 rounded-md p-4 space-y-2">
        <div>
          <p className="text-xs text-gray-500">Username</p>
          <p className="text-sm text-gray-900">{me.username}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Email</p>
          <p className="text-sm text-gray-900">{me.email}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Joined</p>
          <p className="text-sm text-gray-900">{formatDate(me.created_at)}</p>
        </div>
      </div>
      <ChangePasswordForm />
      <DeleteAccountSection />
    </div>
  );
}
