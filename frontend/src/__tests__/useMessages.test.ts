import React from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi, describe, it, expect, beforeEach } from "vitest";
import { useMessages, useSendMessage } from "../hooks/useMessages";
import { api } from "../lib/api";
import type { MessagePage, MessagePublic } from "../lib/types";

vi.mock("../lib/api");
const mockApi = vi.mocked(api);

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

const mockMessage: MessagePublic = {
  id: "msg-1",
  room_id: "room-1",
  author_id: "user-1",
  author_username: "alice",
  content: "Hello!",
  reply_to_id: null,
  reply_preview: null,
  attachments: [],
  created_at: "2026-04-20T10:00:00Z",
  edited_at: null,
  deleted: false,
};

const mockPage: MessagePage = {
  messages: [mockMessage],
  has_more: false,
  next_cursor: null,
};

describe("useMessages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not fetch when roomId is null (query disabled)", () => {
    const wrapper = makeWrapper();
    const { result } = renderHook(() => useMessages(null), { wrapper });
    expect(result.current.isFetchingNextPage).toBe(false);
    expect(result.current.data).toBeUndefined();
    expect(mockApi.get).not.toHaveBeenCalled();
  });

  it("fetches /api/rooms/{roomId}/messages when roomId is provided", async () => {
    mockApi.get = vi.fn().mockResolvedValueOnce(mockPage);
    const wrapper = makeWrapper();
    const { result } = renderHook(() => useMessages("room-1"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi.get).toHaveBeenCalledWith("/api/rooms/room-1/messages");
    const pages = result.current.data?.pages;
    expect(pages).toHaveLength(1);
    expect(pages?.[0].messages).toHaveLength(1);
    expect(pages?.[0].messages[0].content).toBe("Hello!");
  });

  it("passes cursor as before param for subsequent pages", async () => {
    const pageWithMore: MessagePage = {
      messages: [mockMessage],
      has_more: true,
      next_cursor: "cursor-abc",
    };
    mockApi.get = vi.fn().mockResolvedValueOnce(pageWithMore);
    const wrapper = makeWrapper();
    renderHook(() => useMessages("room-2"), { wrapper });

    await waitFor(() => {
      expect(mockApi.get).toHaveBeenCalledWith("/api/rooms/room-2/messages");
    });
  });
});

describe("useSendMessage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls api.post with the correct path and content", async () => {
    mockApi.post = vi.fn().mockResolvedValueOnce(mockMessage);
    mockApi.get = vi.fn().mockResolvedValue(mockPage);
    const wrapper = makeWrapper();
    const { result } = renderHook(() => useSendMessage("room-1"), { wrapper });

    result.current.mutate("Hello World");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi.post).toHaveBeenCalledWith("/api/rooms/room-1/messages", {
      content: "Hello World",
    });
  });
});
