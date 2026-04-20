import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import {
  clearUnread,
  incrementUnread,
  setUnreadCounts,
  useUnreadCount,
} from "../lib/unreadStore";

describe("unreadStore", () => {
  beforeEach(() => {
    // Reset state by clearing any room ids the tests touch
    setUnreadCounts({
      "room-a": 0,
      "room-b": 0,
      "room-c": 0,
      "room-d": 0,
    });
  });

  describe("useUnreadCount", () => {
    it("returns 0 for an unknown room id", () => {
      const { result } = renderHook(() => useUnreadCount("unknown-room"));
      expect(result.current).toBe(0);
    });

    it("returns the count set via setUnreadCounts", () => {
      const { result } = renderHook(() => useUnreadCount("room-a"));
      act(() => {
        setUnreadCounts({ "room-a": 7 });
      });
      expect(result.current).toBe(7);
    });

    it("re-renders when the count changes", () => {
      const { result } = renderHook(() => useUnreadCount("room-b"));
      expect(result.current).toBe(0);
      act(() => {
        incrementUnread("room-b");
      });
      expect(result.current).toBe(1);
      act(() => {
        incrementUnread("room-b");
      });
      expect(result.current).toBe(2);
      act(() => {
        clearUnread("room-b");
      });
      expect(result.current).toBe(0);
    });
  });

  describe("incrementUnread", () => {
    it("starts at 1 when the room has no entry", () => {
      const { result } = renderHook(() => useUnreadCount("fresh-room"));
      act(() => {
        incrementUnread("fresh-room");
      });
      expect(result.current).toBe(1);
    });

    it("adds 1 to the existing count", () => {
      const { result } = renderHook(() => useUnreadCount("room-c"));
      act(() => {
        setUnreadCounts({ "room-c": 4 });
      });
      expect(result.current).toBe(4);
      act(() => {
        incrementUnread("room-c");
      });
      expect(result.current).toBe(5);
    });
  });

  describe("clearUnread", () => {
    it("resets the count to 0", () => {
      const { result } = renderHook(() => useUnreadCount("room-d"));
      act(() => {
        setUnreadCounts({ "room-d": 12 });
      });
      expect(result.current).toBe(12);
      act(() => {
        clearUnread("room-d");
      });
      expect(result.current).toBe(0);
    });
  });

  describe("setUnreadCounts", () => {
    it("merges new counts with existing state (does not drop unrelated rooms)", () => {
      const roomA = renderHook(() => useUnreadCount("room-a"));
      const roomB = renderHook(() => useUnreadCount("room-b"));

      act(() => {
        setUnreadCounts({ "room-a": 3 });
      });
      expect(roomA.result.current).toBe(3);

      act(() => {
        setUnreadCounts({ "room-b": 5 });
      });
      expect(roomA.result.current).toBe(3);
      expect(roomB.result.current).toBe(5);
    });

    it("handles empty payload without throwing or altering state", () => {
      const { result } = renderHook(() => useUnreadCount("room-a"));
      act(() => {
        setUnreadCounts({ "room-a": 9 });
      });
      expect(result.current).toBe(9);
      act(() => {
        setUnreadCounts({});
      });
      expect(result.current).toBe(9);
    });
  });

  it("isolates counts per room id", () => {
    const a = renderHook(() => useUnreadCount("room-a"));
    const b = renderHook(() => useUnreadCount("room-b"));
    act(() => {
      incrementUnread("room-a");
      incrementUnread("room-a");
      incrementUnread("room-b");
    });
    expect(a.result.current).toBe(2);
    expect(b.result.current).toBe(1);
  });
});
