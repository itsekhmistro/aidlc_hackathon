import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PresenceDot } from "../components/PresenceDot";

describe("PresenceDot", () => {
  it("renders with title 'online'", () => {
    render(<PresenceDot status="online" />);
    expect(screen.getByTitle("online")).toBeInTheDocument();
  });

  it("renders with title 'afk'", () => {
    render(<PresenceDot status="afk" />);
    expect(screen.getByTitle("afk")).toBeInTheDocument();
  });

  it("renders with title 'offline'", () => {
    render(<PresenceDot status="offline" />);
    expect(screen.getByTitle("offline")).toBeInTheDocument();
  });

  it("applies green class for online", () => {
    const { container } = render(<PresenceDot status="online" />);
    expect(container.firstChild).toHaveClass("bg-green-500");
  });

  it("applies yellow class for afk", () => {
    const { container } = render(<PresenceDot status="afk" />);
    expect(container.firstChild).toHaveClass("bg-yellow-400");
  });

  it("applies gray class for offline", () => {
    const { container } = render(<PresenceDot status="offline" />);
    expect(container.firstChild).toHaveClass("bg-gray-300");
  });

  it("accepts optional className prop", () => {
    const { container } = render(<PresenceDot status="online" className="ml-2" />);
    expect(container.firstChild).toHaveClass("ml-2");
  });
});
