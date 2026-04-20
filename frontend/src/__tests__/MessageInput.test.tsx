import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import MessageInput from "../components/MessageInput";

describe("MessageInput", () => {
  it("renders textarea with the correct placeholder", () => {
    render(<MessageInput onSend={vi.fn()} />);
    expect(
      screen.getByPlaceholderText("Type a message… (Enter to send)")
    ).toBeInTheDocument();
  });

  it("Enter key calls onSend with trimmed content and clears input", async () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} />);
    const textarea = screen.getByPlaceholderText("Type a message… (Enter to send)");

    await userEvent.type(textarea, "  Hello World  ");
    await userEvent.keyboard("{Enter}");

    expect(onSend).toHaveBeenCalledOnce();
    expect(onSend).toHaveBeenCalledWith("Hello World");
    // Input should be cleared after sending
    expect(textarea).toHaveValue("");
  });

  it("Shift+Enter does NOT call onSend (just adds newline)", async () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} />);
    const textarea = screen.getByPlaceholderText("Type a message… (Enter to send)");

    await userEvent.type(textarea, "Line one");
    await userEvent.keyboard("{Shift>}{Enter}{/Shift}");

    expect(onSend).not.toHaveBeenCalled();
  });

  it("Enter with empty/whitespace-only content does NOT call onSend", async () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} />);
    const textarea = screen.getByPlaceholderText("Type a message… (Enter to send)");

    // Press Enter with empty input
    await userEvent.click(textarea);
    await userEvent.keyboard("{Enter}");
    expect(onSend).not.toHaveBeenCalled();

    // Type only whitespace and press Enter
    await userEvent.type(textarea, "   ");
    await userEvent.keyboard("{Enter}");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("disabled prop disables the textarea", () => {
    render(<MessageInput onSend={vi.fn()} disabled={true} />);
    const textarea = screen.getByPlaceholderText("Type a message… (Enter to send)");
    expect(textarea).toBeDisabled();
  });

  it("textarea is enabled by default (no disabled prop)", () => {
    render(<MessageInput onSend={vi.fn()} />);
    const textarea = screen.getByPlaceholderText("Type a message… (Enter to send)");
    expect(textarea).not.toBeDisabled();
  });
});
