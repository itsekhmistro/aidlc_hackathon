import { useEffect, useRef } from "react";
import type { ClientEvent } from "../lib/types";

const IDLE_MS = 60_000;
const ACTIVITY_EVENTS = ["mousemove", "keydown", "mousedown", "touchstart", "scroll"] as const;

export function useActivityTracker(
  tabId: string,
  sendMessage: (e: ClientEvent) => void,
  enabled: boolean,
): void {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isAfkRef = useRef(false);

  useEffect(() => {
    if (!enabled) return;

    function goAfk() {
      if (!isAfkRef.current) {
        isAfkRef.current = true;
        sendMessage({ type: "presence.heartbeat", tab_id: tabId, status: "afk" });
      }
    }

    function onActivity() {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (isAfkRef.current) {
        isAfkRef.current = false;
        sendMessage({ type: "presence.heartbeat", tab_id: tabId, status: "online" });
      }
      timerRef.current = setTimeout(goAfk, IDLE_MS);
    }

    ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, onActivity, { passive: true }));
    timerRef.current = setTimeout(goAfk, IDLE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, onActivity));
    };
  }, [enabled, tabId, sendMessage]);
}
