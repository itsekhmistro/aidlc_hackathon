import { useState, useRef } from "react";
import { api } from "../lib/api";
import type { AttachmentPublic } from "../lib/types";

interface Props {
  roomId: string;
  onSend: (content: string, attachmentIds: string[]) => void;
  disabled?: boolean;
}

interface PendingFile {
  localId: string;
  name: string;
  attachmentId?: string;
  error?: string;
}

export default function MessageInput({ roomId, onSend, disabled }: Props) {
  const [value, setValue] = useState("");
  const [pending, setPending] = useState<PendingFile[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadFiles = (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    fileArray.forEach((file) => {
      const localId = crypto.randomUUID?.() ?? Math.random().toString(36).slice(2);
      setPending((prev) => [...prev, { localId, name: file.name }]);

      const formData = new FormData();
      formData.append("file", file);

      api
        .upload<AttachmentPublic>(`/api/attachments/${roomId}`, formData)
        .then((att) => {
          setPending((prev) =>
            prev.map((p) =>
              p.localId === localId ? { ...p, attachmentId: att.id } : p
            )
          );
        })
        .catch((err: unknown) => {
          const message = err instanceof Error ? err.message : "Upload failed";
          setPending((prev) =>
            prev.map((p) =>
              p.localId === localId ? { ...p, error: message } : p
            )
          );
        });
    });
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const files = e.clipboardData.files;
    if (files.length > 0) {
      e.preventDefault();
      uploadFiles(files);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      uploadFiles(e.target.files);
      e.target.value = "";
    }
  };

  const handleSend = () => {
    const trimmed = value.trim();
    const completedIds = pending
      .filter((p) => p.attachmentId)
      .map((p) => p.attachmentId!);

    if (!trimmed && completedIds.length === 0) return;

    onSend(trimmed, completedIds);
    setValue("");
    setPending([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const canSend =
    !disabled && (value.trim().length > 0 || pending.some((p) => p.attachmentId));

  return (
    <div className="border-t">
      {pending.length > 0 && (
        <div className="flex flex-wrap gap-1 px-3 pb-1 pt-2">
          {pending.map((p) => (
            <span
              key={p.localId}
              className="flex items-center gap-1 text-xs bg-gray-100 rounded px-2 py-0.5"
            >
              {!p.attachmentId && !p.error && (
                <span className="animate-spin">⏳</span>
              )}
              {p.error && <span className="text-red-500">!</span>}
              <span className="truncate max-w-[8rem]">{p.name}</span>
              <button
                onClick={() =>
                  setPending((prev) => prev.filter((x) => x.localId !== p.localId))
                }
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="flex items-end gap-2 p-3">
        <input
          type="file"
          multiple
          ref={fileInputRef}
          className="hidden"
          onChange={handleFileChange}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          className="text-gray-400 hover:text-gray-600 disabled:opacity-50 pb-1.5"
          title="Attach files"
        >
          📎
        </button>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          disabled={disabled}
          placeholder="Type a message… (Enter to send)"
          rows={1}
          className="flex-1 resize-none rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          style={{ minHeight: "2.5rem", maxHeight: "8rem" }}
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={!canSend}
          className="pb-1.5 text-blue-500 hover:text-blue-700 disabled:opacity-30"
          title="Send"
        >
          ➤
        </button>
      </div>
    </div>
  );
}
