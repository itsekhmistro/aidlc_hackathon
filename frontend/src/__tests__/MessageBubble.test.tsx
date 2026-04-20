import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
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

  it("own-message bubble exposes Edit, Delete, and Reply action buttons", () => {
    render(
      <MessageBubble
        message={makeMessage()}
        isOwn={true}
        onReply={vi.fn()}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />
    );
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reply" })).toBeInTheDocument();
  });

  it("non-own-message bubble exposes only Reply action", () => {
    render(
      <MessageBubble
        message={makeMessage()}
        isOwn={false}
        onReply={vi.fn()}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />
    );
    expect(screen.getByRole("button", { name: "Reply" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });

  it("deleted message exposes no action buttons", () => {
    render(
      <MessageBubble
        message={makeMessage({ deleted: true })}
        isOwn={true}
        onReply={vi.fn()}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />
    );
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reply" })).not.toBeInTheDocument();
  });

  it("renders image attachments as inline <img> linked to the download URL", () => {
    const msg = makeMessage({
      attachments: [
        {
          id: "att-1",
          original_filename: "photo.png",
          mime_type: "image/png",
          size_bytes: 2048,
          comment: null,
          created_at: "2026-04-20T10:00:00Z",
        },
      ],
    });
    render(<MessageBubble message={msg} isOwn={false} />);
    const img = screen.getByRole("img", { name: "photo.png" });
    expect(img).toBeInTheDocument();
    expect(img.getAttribute("src")).toBe("/api/attachments/att-1");
    // Parent anchor points to the same file so click-through opens the full image
    const link = screen.getByRole("link", { name: /open image photo\.png/i });
    expect(link.getAttribute("href")).toBe("/api/attachments/att-1");
    // Filename + size caption is still rendered for accessibility
    expect(screen.getByText(/photo\.png/)).toBeInTheDocument();
    expect(screen.getByText(/2\.0KB/)).toBeInTheDocument();
  });

  it("renders non-image attachments as a text link (no <img>)", () => {
    const msg = makeMessage({
      attachments: [
        {
          id: "att-2",
          original_filename: "spec.pdf",
          mime_type: "application/pdf",
          size_bytes: 10_240,
          comment: null,
          created_at: "2026-04-20T10:00:00Z",
        },
      ],
    });
    render(<MessageBubble message={msg} isOwn={false} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    const link = screen.getByRole("link", { name: /spec\.pdf/ });
    expect(link.getAttribute("href")).toBe("/api/attachments/att-2");
  });

  it("clicking Edit reveals a textarea; editing + Save calls onEdit with new content", async () => {
    const onEdit = vi.fn();
    const msg = makeMessage({ content: "original text" });
    render(
      <MessageBubble
        message={msg}
        isOwn={true}
        onReply={vi.fn()}
        onEdit={onEdit}
        onDelete={vi.fn()}
      />
    );

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));

    const textarea = screen.getByRole("textbox", { name: "Edit message" });
    expect(textarea).toBeInTheDocument();
    expect(textarea).toHaveValue("original text");

    await userEvent.clear(textarea);
    await userEvent.type(textarea, "updated text");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onEdit).toHaveBeenCalledOnce();
    expect(onEdit).toHaveBeenCalledWith(msg, "updated text");
  });
});
