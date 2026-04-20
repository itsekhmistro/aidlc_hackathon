import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import MessageBubble from "../components/MessageBubble";
import type { MessagePublic } from "../lib/types";

function makeMessage(overrides: Partial<MessagePublic> = {}): MessagePublic {
  return {
    id: "msg-1",
    room_id: "room-1",
    author_id: "user-1",
    author_username: "alice",
    content: "Hello there",
    reply_to_id: null,
    reply_preview: null,
    attachments: [],
    created_at: "2026-04-20T10:00:00Z",
    edited_at: null,
    deleted: false,
    ...overrides,
  };
}

describe("MessageBubble", () => {
  it("renders own message with blue background class", () => {
    const { container } = render(
      <MessageBubble message={makeMessage()} isOwn={true} />
    );
    // The bubble div should have bg-blue-500 class
    const bubble = container.querySelector(".bg-blue-500");
    expect(bubble).toBeTruthy();
  });

  it("renders other person's message with gray background", () => {
    const { container } = render(
      <MessageBubble message={makeMessage()} isOwn={false} />
    );
    const bubble = container.querySelector(".bg-gray-100");
    expect(bubble).toBeTruthy();
  });

  it("renders the message content", () => {
    render(<MessageBubble message={makeMessage({ content: "My message text" })} isOwn={false} />);
    expect(screen.getByText("My message text")).toBeInTheDocument();
  });

  it("renders deleted message as italic 'Message deleted' text", () => {
    render(
      <MessageBubble
        message={makeMessage({ deleted: true, content: "" })}
        isOwn={false}
      />
    );
    const el = screen.getByText("Message deleted");
    expect(el).toBeInTheDocument();
    expect(el).toHaveClass("italic");
  });

  it("does not show message content for deleted messages", () => {
    render(
      <MessageBubble
        message={makeMessage({ deleted: true, content: "Secret" })}
        isOwn={false}
      />
    );
    expect(screen.queryByText("Secret")).not.toBeInTheDocument();
  });

  it("renders edited indicator when edited_at is non-null", () => {
    render(
      <MessageBubble
        message={makeMessage({ edited_at: "2026-04-20T11:00:00Z" })}
        isOwn={false}
      />
    );
    expect(screen.getByText("(edited)")).toBeInTheDocument();
  });

  it("does not render edited indicator for non-edited messages", () => {
    render(
      <MessageBubble message={makeMessage({ edited_at: null })} isOwn={false} />
    );
    expect(screen.queryByText("(edited)")).not.toBeInTheDocument();
  });

  it("shows author username for other person's messages", () => {
    render(
      <MessageBubble
        message={makeMessage({ author_username: "bob" })}
        isOwn={false}
      />
    );
    expect(screen.getByText("bob")).toBeInTheDocument();
  });

  it("does not show author username for own messages", () => {
    render(
      <MessageBubble
        message={makeMessage({ author_username: "alice" })}
        isOwn={true}
      />
    );
    // For own messages, username is not rendered
    expect(screen.queryByText("alice")).not.toBeInTheDocument();
  });
});
