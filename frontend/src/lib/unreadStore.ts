import { useSyncExternalStore } from "react";

const store = new Map<string, number>();
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((l) => l());
}

export function setUnreadCounts(counts: Record<string, number>): void {
  for (const [id, count] of Object.entries(counts)) {
    store.set(id, count);
  }
  notify();
}

export function incrementUnread(roomId: string): void {
  store.set(roomId, (store.get(roomId) ?? 0) + 1);
  notify();
}

export function clearUnread(roomId: string): void {
  store.set(roomId, 0);
  notify();
}

export function useUnreadCount(roomId: string): number {
  return useSyncExternalStore(
    (cb) => { listeners.add(cb); return () => { listeners.delete(cb); }; },
    () => store.get(roomId) ?? 0,
  );
}

export function useTotalUnread(): number {
  return useSyncExternalStore(
    (cb) => { listeners.add(cb); return () => { listeners.delete(cb); }; },
    () => {
      let total = 0;
      for (const n of store.values()) total += n;
      return total;
    },
  );
}
