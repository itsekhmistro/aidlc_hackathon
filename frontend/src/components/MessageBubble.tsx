import { useEffect, useRef, useState } from "react";
import type { MessagePublic } from "../lib/types";

interface Props {
  message: MessagePublic;
  isOwn: boolean;
  onReply?: (message: MessagePublic) => void;
  onEdit?: (message: MessagePublic, newContent: string) => void;
  onDelete?: (message: MessagePublic) => void;
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b}B`;
  if (b < 1_048_576) return `${(b / 1024).toFixed(1)}KB`;
  return `${(b / 1_048_576).toFixed(1)}MB`;
}

export default function MessageBubble({ message, isOwn, onReply, onEdit, onDelete }: Props) {
  const [mode, setMode] = useState<"view" | "edit" | "confirm-delete">("view");
  const [draft, setDraft] = useState(message.content);
  const editRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (mode === "edit") {
      editRef.current?.focus();
      // Place cursor at end
      const len = editRef.current?.value.length ?? 0;
      editRef.current?.setSelectionRange(len, len);
    }
  }, [mode]);

  if (message.deleted) {
    return (
      <div className={`flex ${isOwn ? "justify-end" : "justify-start"} mb-1`}>
        <span className="text-xs text-gray-400 italic px-3 py-1">Message deleted</span>
      </div>
    );
  }

  const saveEdit = () => {
    const trimmed = draft.trim();
    if (!trimmed || trimmed === message.content) {
      setMode("view");
      setDraft(message.content);
      return;
    }
    onEdit?.(message, trimmed);
    setMode("view");
  };

  const cancelEdit = () => {
    setDraft(message.content);
    setMode("view");
  };

  const handleEditKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      saveEdit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancelEdit();
    }
  };

  return (
    <div className={`group flex ${isOwn ? "justify-end" : "justify-start"} mb-1 items-end gap-1`}>
      {/* Action icons for isOwn messages appear to the LEFT of bubble */}
      {isOwn && mode === "view" && (
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity text-xs text-gray-500 pb-0.5">
          <button
            type="button"
            onClick={() => onReply?.(message)}
            className="hover:text-gray-800"
            aria-label="Reply"
            title="Reply"
          >
            ↩
          </button>
          <button
            type="button"
            onClick={() => {
              setDraft(message.content);
              setMode("edit");
            }}
            className="hover:text-gray-800"
            aria-label="Edit"
            title="Edit"
          >
            ✏️
          </button>
          <button
            type="button"
            onClick={() => setMode("confirm-delete")}
            className="hover:text-red-600"
            aria-label="Delete"
            title="Delete"
          >
            🗑️
          </button>
        </div>
      )}

      {!isOwn && (
        <span className="text-xs text-gray-400 self-end mr-1 mb-0.5 shrink-0">
          {message.author_username}
        </span>
      )}

      <div
        className={`max-w-xs lg:max-w-md px-3 py-2 rounded-2xl text-sm ${
          isOwn ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-900"
        }`}
      >
        {message.reply_preview && (
          <div
            data-testid="reply-preview"
            className={`mb-1 pl-2 border-l-2 text-xs truncate ${
              isOwn ? "border-blue-200 text-blue-100" : "border-gray-400 text-gray-500"
            }`}
          >
            ↩ {message.reply_preview}
          </div>
        )}

        {mode === "edit" ? (
          <div className="flex flex-col gap-1">
            <textarea
              ref={editRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleEditKeyDown}
              rows={2}
              className="resize-none rounded border border-gray-300 bg-white text-gray-900 text-sm px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
              aria-label="Edit message"
            />
            <div className="flex gap-2 justify-end text-xs">
              <button
                type="button"
                onClick={cancelEdit}
                className={`${isOwn ? "text-blue-100 hover:text-white" : "text-gray-500 hover:text-gray-800"}`}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={saveEdit}
                className={`font-semibold ${isOwn ? "text-white" : "text-blue-600 hover:text-blue-800"}`}
              >
                Save
              </button>
            </div>
          </div>
        ) : (
          <p className="break-words whitespace-pre-wrap">{message.content}</p>
        )}

        {message.attachments.length > 0 && mode !== "edit" && (
          <div className="mt-1 space-y-1">
            {message.attachments.map((att) => {
              const href = `/api/attachments/${att.id}`;
              const isImage = att.mime_type.startsWith("image/");
              if (isImage) {
                return (
                  <a
                    key={att.id}
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                    className="block"
                    aria-label={`Open image ${att.original_filename}`}
                  >
                    <img
                      src={href}
                      alt={att.original_filename}
                      loading="lazy"
                      className="max-w-full max-h-64 rounded border border-black/10 object-contain bg-white/5"
                    />
                    <span
                      className={`block mt-0.5 text-xs truncate ${isOwn ? "text-blue-100" : "text-gray-500"}`}
                    >
                      {att.original_filename} ({formatBytes(att.size_bytes)})
                    </span>
                  </a>
                );
              }
              return (
                <a
                  key={att.id}
                  href={href}
                  target="_blank"
                  rel="noreferrer"
                  className={`flex items-center gap-1 text-xs underline ${isOwn ? "text-blue-100 hover:text-white" : "text-blue-600 hover:text-blue-800"}`}
                >
                  📎 {att.original_filename} ({formatBytes(att.size_bytes)})
                </a>
              );
            })}
          </div>
        )}
        {message.edited_at && mode !== "edit" && (
          <span className={`text-xs ${isOwn ? "text-blue-200" : "text-gray-400"}`}> (edited)</span>
        )}

        {mode === "confirm-delete" && (
          <div
            className={`mt-1 flex items-center gap-2 text-xs ${isOwn ? "text-blue-100" : "text-gray-600"}`}
          >
            <span>Delete?</span>
            <button
              type="button"
              onClick={() => {
                onDelete?.(message);
                setMode("view");
              }}
              className={`font-semibold ${isOwn ? "hover:text-white" : "text-red-600 hover:text-red-800"}`}
              aria-label="Confirm delete"
            >
              y
            </button>
            <span>/</span>
            <button
              type="button"
              onClick={() => setMode("view")}
              className={`${isOwn ? "hover:text-white" : "hover:text-gray-800"}`}
              aria-label="Cancel delete"
            >
              n
            </button>
          </div>
        )}
      </div>

      {/* Reply-only icon for non-own messages, appears to the RIGHT */}
      {!isOwn && mode === "view" && (
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity text-xs text-gray-500 pb-0.5">
          <button
            type="button"
            onClick={() => onReply?.(message)}
            className="hover:text-gray-800"
            aria-label="Reply"
            title="Reply"
          >
            ↩
          </button>
        </div>
      )}
    </div>
  );
}
