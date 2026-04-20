import { useSyncExternalStore } from "react";
import type { PresenceStatus } from "./types";

const store = new Map<string, PresenceStatus>();
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((l) => l());
}

export function setPresence(userId: string, status: PresenceStatus): void {
  store.set(userId, status);
  notify();
}

export function setBulkPresence(entries: Array<{ user_id: string; status: PresenceStatus }>): void {
  entries.forEach(({ user_id, status }) => store.set(user_id, status));
  notify();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): Map<string, PresenceStatus> {
  return store;
}

export function usePresence(userId: string): PresenceStatus {
  const map = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  return map.get(userId) ?? "offline";
}
