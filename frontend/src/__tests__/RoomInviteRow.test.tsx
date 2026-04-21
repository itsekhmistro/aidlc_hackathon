import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RoomInviteRow from "../components/RoomInviteRow";
import { api } from "../lib/api";
import type { RoomInvitationPublic } from "../lib/types";

vi.mock("../lib/api");
const mockApi = vi.mocked(api);

function invite(overrides: Partial<RoomInvitationPublic> = {}): RoomInvitationPublic {
  return {
    id: "inv-1",
    room_id: "room-1",
    room_name: "secret-room",
    invited_by_id: "u-1",
    invited_by_username: "alice",
    invited_user_id: "u-2",
    invited_username: "bob",
    created_at: "2026-04-21T10:00:00Z",
    accepted_at: null,
    ...overrides,
  };
}

function renderRow(i: RoomInvitationPublic) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    qc,
    ...render(
      <QueryClientProvider client={qc}>
        <RoomInviteRow invite={i} />
      </QueryClientProvider>,
    ),
  };
}

describe("RoomInviteRow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.post = vi.fn().mockResolvedValue(undefined);
  });

  it("shows inviter username and room name", () => {
    renderRow(invite());
    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.getByText("#secret-room")).toBeInTheDocument();
    expect(screen.getByText(/invited you to/i)).toBeInTheDocument();
  });

  it("calls accept endpoint when the checkmark is clicked", async () => {
    const user = userEvent.setup();
    renderRow(invite());

    await user.click(screen.getByRole("button", { name: /accept invitation to secret-room/i }));

    await waitFor(() => {
      expect(mockApi.post).toHaveBeenCalledWith("/api/rooms/invitations/inv-1/accept");
    });
  });

  it("calls decline endpoint when the X is clicked", async () => {
    const user = userEvent.setup();
    renderRow(invite());

    await user.click(screen.getByRole("button", { name: /decline invitation to secret-room/i }));

    await waitFor(() => {
      expect(mockApi.post).toHaveBeenCalledWith("/api/rooms/invitations/inv-1/decline");
    });
  });

  it("accepts and declines a differently-named room by id", async () => {
    const user = userEvent.setup();
    renderRow(invite({ id: "inv-99", room_name: "team-core" }));

    await user.click(screen.getByRole("button", { name: /accept invitation to team-core/i }));

    await waitFor(() => {
      expect(mockApi.post).toHaveBeenCalledWith("/api/rooms/invitations/inv-99/accept");
    });
  });
});
