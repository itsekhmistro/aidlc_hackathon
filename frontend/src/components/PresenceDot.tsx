import type { PresenceStatus } from "../lib/types";

const STATUS_CLASSES: Record<PresenceStatus, string> = {
  online: "bg-green-500",
  afk: "bg-yellow-400",
  offline: "bg-gray-300",
};

export function PresenceDot({ status, className = "" }: { status: PresenceStatus; className?: string }) {
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full flex-shrink-0 ${STATUS_CLASSES[status]} ${className}`}
      title={status}
    />
  );
}
