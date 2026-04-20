import type { MessagePublic } from "../lib/types";

interface Props {
  message: MessagePublic;
  isOwn: boolean;
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b}B`;
  if (b < 1_048_576) return `${(b / 1024).toFixed(1)}KB`;
  return `${(b / 1_048_576).toFixed(1)}MB`;
}

export default function MessageBubble({ message, isOwn }: Props) {
  if (message.deleted) {
    return (
      <div className={`flex ${isOwn ? "justify-end" : "justify-start"} mb-1`}>
        <span className="text-xs text-gray-400 italic px-3 py-1">Message deleted</span>
      </div>
    );
  }
  return (
    <div className={`flex ${isOwn ? "justify-end" : "justify-start"} mb-1`}>
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
        <p className="break-words">{message.content}</p>
        {message.attachments.length > 0 && (
          <div className="mt-1 space-y-0.5">
            {message.attachments.map((att) => (
              <a
                key={att.id}
                href={`/api/attachments/${att.id}`}
                target="_blank"
                rel="noreferrer"
                className={`flex items-center gap-1 text-xs underline ${isOwn ? "text-blue-100 hover:text-white" : "text-blue-600 hover:text-blue-800"}`}
              >
                📎 {att.original_filename} ({formatBytes(att.size_bytes)})
              </a>
            ))}
          </div>
        )}
        {message.edited_at && (
          <span className={`text-xs ${isOwn ? "text-blue-200" : "text-gray-400"}`}> (edited)</span>
        )}
      </div>
    </div>
  );
}
