import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useCurrentUser, useLogout } from "../hooks/useAuth";

export default function TopNav() {
  const { data: me } = useCurrentUser();
  const logout = useLogout();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const initial = me?.username?.charAt(0).toUpperCase() ?? "?";

  const handleLogout = async () => {
    setOpen(false);
    await logout.mutateAsync();
    navigate("/login");
  };

  return (
    <header className="h-12 bg-white border-b border-gray-200 flex items-center justify-between px-4 shrink-0">
      <Link to="/chat" className="font-semibold text-gray-900 text-sm">
        Chat
      </Link>
      <div className="relative" ref={ref}>
        <button
          onClick={() => setOpen((v) => !v)}
          aria-label="User menu"
          aria-haspopup="menu"
          aria-expanded={open}
          className="flex items-center gap-2 px-2 py-1 rounded hover:bg-gray-100"
        >
          <span className="w-7 h-7 rounded-full bg-blue-500 text-white text-xs font-semibold flex items-center justify-center">
            {initial}
          </span>
          <span className="text-sm text-gray-800">{me?.username ?? ""}</span>
        </button>
        {open && (
          <div
            role="menu"
            className="absolute right-0 top-10 z-20 bg-white border border-gray-200 rounded-md shadow-lg py-1 w-44"
          >
            <Link
              to="/profile"
              onClick={() => setOpen(false)}
              className="block px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
              role="menuitem"
            >
              Profile
            </Link>
            <Link
              to="/sessions"
              onClick={() => setOpen(false)}
              className="block px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
              role="menuitem"
            >
              Sessions
            </Link>
            <button
              onClick={handleLogout}
              disabled={logout.isPending}
              className="w-full text-left px-3 py-1.5 text-sm text-red-600 hover:bg-gray-50 disabled:opacity-50"
              role="menuitem"
            >
              {logout.isPending ? "Signing out…" : "Sign out"}
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
