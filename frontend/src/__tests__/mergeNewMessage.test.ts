import { QueryClient, type InfiniteData } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { mergeNewMessage } from "../hooks/useMessages";
import type { MessagePage, MessagePublic } from "../lib/types";

function makeMessage(overrides: Partial<MessagePublic> = {}): MessagePublic {
  return {
    id: "msg-new",
    room_id: "room-1",
    author_id: "user-1",
    author_username: "alice",
    content: "hello",
    reply_to_id: null,
    reply_preview: null,
    attachments: [],
    created_at: "2026-04-21T10:00:00Z",
    edited_at: null,
    deleted: false,
    ...overrides,
  };
}

function seed(qc: QueryClient, roomId: string, data: InfiniteData<MessagePage>) {
  qc.setQueryData(["messages", roomId], data);
}

describe("mergeNewMessage", () => {
  it("prepends the message to page[0] and preserves other pages", () => {
    const qc = new QueryClient();
    seed(qc, "room-1", {
      pages: [
        { messages: [makeMessage({ id: "m2" })], has_more: true, next_cursor: "cur" },
        { messages: [makeMessage({ id: "m1" })], has_more: false, next_cursor: null },
      ],
      pageParams: [undefined, "cur"],
    });

    const mutated = mergeNewMessage(qc, "room-1", makeMessage({ id: "m3" }));
    expect(mutated).toBe(true);

    const data = qc.getQueryData<InfiniteData<MessagePage>>(["messages", "room-1"]);
    expect(data?.pages[0].messages.map((m) => m.id)).toEqual(["m3", "m2"]);
    expect(data?.pages[0].has_more).toBe(true);
    expect(data?.pages[0].next_cursor).toBe("cur");
    expect(data?.pages[1].messages.map((m) => m.id)).toEqual(["m1"]);
  });

  it("is idempotent — a duplicate id is a no-op", () => {
    const qc = new QueryClient();
    seed(qc, "room-1", {
      pages: [
        { messages: [makeMessage({ id: "m1" })], has_more: false, next_cursor: null },
      ],
      pageParams: [undefined],
    });

    const mutated = mergeNewMessage(qc, "room-1", makeMessage({ id: "m1", content: "altered" }));
    expect(mutated).toBe(false);
    const data = qc.getQueryData<InfiniteData<MessagePage>>(["messages", "room-1"]);
    expect(data?.pages[0].messages).toHaveLength(1);
    // Original content is preserved — no overwrite on duplicate.
    expect(data?.pages[0].messages[0].content).toBe("hello");
  });

  it("skips when the room's cache has not been populated", () => {
    const qc = new QueryClient();
    const mutated = mergeNewMessage(qc, "room-never-opened", makeMessage());
    expect(mutated).toBe(false);
    expect(qc.getQueryData(["messages", "room-never-opened"])).toBeUndefined();
  });

  it("skips when pages array is empty (edge case)", () => {
    const qc = new QueryClient();
    seed(qc, "room-1", { pages: [], pageParams: [] });
    const mutated = mergeNewMessage(qc, "room-1", makeMessage());
    expect(mutated).toBe(false);
  });
});
