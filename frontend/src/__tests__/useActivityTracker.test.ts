import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useActivityTracker } from "../hooks/useActivityTracker";
import type { ClientEvent } from "../lib/types";

describe("useActivityTracker", () => {
  const tabId = "test-tab";
  let sendMessage: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useFakeTimers();
    sendMessage = vi.fn();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("does nothing when disabled", () => {
    renderHook(() => useActivityTracker(tabId, sendMessage as (e: ClientEvent) => void, false));
    act(() => { vi.advanceTimersByTime(65_000); });
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("sends afk heartbeat after 60s of inactivity", () => {
    renderHook(() => useActivityTracker(tabId, sendMessage as (e: ClientEvent) => void, true));
    act(() => { vi.advanceTimersByTime(61_000); });
    expect(sendMessage).toHaveBeenCalledWith({
      type: "presence.heartbeat",
      tab_id: tabId,
      status: "afk",
    });
  });

  it("resets timer and sends online after activity post-AFK", () => {
    renderHook(() => useActivityTracker(tabId, sendMessage as (e: ClientEvent) => void, true));
    // Go AFK
    act(() => { vi.advanceTimersByTime(61_000); });
    expect(sendMessage).toHaveBeenCalledWith(expect.objectContaining({ status: "afk" }));

    // Simulate user activity
    act(() => {
      window.dispatchEvent(new MouseEvent("mousemove"));
    });
    expect(sendMessage).toHaveBeenCalledWith({
      type: "presence.heartbeat",
      tab_id: tabId,
      status: "online",
    });
  });

  it("does not send duplicate afk if already afk", () => {
    renderHook(() => useActivityTracker(tabId, sendMessage as (e: ClientEvent) => void, true));
    act(() => { vi.advanceTimersByTime(61_000); });
    act(() => { vi.advanceTimersByTime(61_000); });
    const afkCalls = sendMessage.mock.calls.filter(
      ([e]) => (e as ClientEvent).type === "presence.heartbeat" && (e as { status: string }).status === "afk"
    );
    expect(afkCalls).toHaveLength(1);
  });

  it("listens to all required DOM events", () => {
    const addSpy = vi.spyOn(window, "addEventListener");
    renderHook(() => useActivityTracker(tabId, sendMessage as (e: ClientEvent) => void, true));
    const events = addSpy.mock.calls.map(([e]) => e);
    expect(events).toContain("mousemove");
    expect(events).toContain("keydown");
    expect(events).toContain("mousedown");
    expect(events).toContain("touchstart");
    expect(events).toContain("scroll");
  });

  it("cleans up event listeners on unmount", () => {
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const { unmount } = renderHook(() =>
      useActivityTracker(tabId, sendMessage as (e: ClientEvent) => void, true)
    );
    unmount();
    expect(removeSpy).toHaveBeenCalled();
  });
});
