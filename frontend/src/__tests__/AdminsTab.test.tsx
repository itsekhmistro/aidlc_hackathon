import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminsTab from "../components/admin/AdminsTab";
import { api } from "../lib/api";
import type { MemberRole, RoomMemberPublic } from "../lib/types";

vi.mock("../lib/api");
const mockApi = vi.mocked(api);

function member(overrides: Partial<RoomMemberPublic> = {}): RoomMemberPublic {
  return {
    user_id: "u-1",
    username: "alice",
    role: "member",
    presence_status: "online",
    joined_at: "2026-04-20T10:00:00Z",
    ...overrides,
  };
}

function renderTab(
  members: RoomMemberPublic[],
  myRole: MemberRole = "owner",
) {
  mockApi.get = vi.fn().mockResolvedValue(members);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AdminsTab roomId="room-1" myRole={myRole} />
    </QueryClientProvider>,
  );
}

describe("AdminsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.delete = vi.fn().mockResolvedValue(undefined);
  });

  it("lists the owner with the 'cannot remove' label and each admin", async () => {
    renderTab([
      member({ user_id: "u-1", username: "alice", role: "owner" }),
      member({ user_id: "u-2", username: "dave", role: "admin" }),
      member({ user_id: "u-3", username: "eve", role: "member" }),
    ]);

    await waitFor(() =>
      expect(screen.getByText(/Current admins:/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/alice, dave/)).toBeInTheDocument();
    expect(screen.getByText("Owner — cannot remove admin")).toBeInTheDocument();
    expect(screen.getByText("dave")).toBeInTheDocument();
    expect(screen.queryByText("eve")).toBeNull();
    expect(
      screen.getByRole("button", { name: "Remove admin" }),
    ).toBeInTheDocument();
  });

  it("shows the empty-state copy when no admins exist beyond the owner", async () => {
    renderTab([
      member({ user_id: "u-1", username: "alice", role: "owner" }),
      member({ user_id: "u-3", username: "eve", role: "member" }),
    ]);

    await waitFor(() =>
      expect(
        screen.getByText("No admins beyond the owner."),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: "Remove admin" }),
    ).toBeNull();
  });

  it("Remove admin DELETEs /admin for the selected user", async () => {
    const user = userEvent.setup();
    renderTab([
      member({ user_id: "u-1", username: "alice", role: "owner" }),
      member({ user_id: "u-2", username: "dave", role: "admin" }),
    ]);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Remove admin" }),
      ).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: "Remove admin" }));
    await waitFor(() =>
      expect(mockApi.delete).toHaveBeenCalledWith(
        "/api/rooms/room-1/members/u-2/admin",
      ),
    );
  });

  it("non-owner viewers see no Remove admin button", async () => {
    renderTab(
      [
        member({ user_id: "u-1", username: "alice", role: "owner" }),
        member({ user_id: "u-2", username: "dave", role: "admin" }),
      ],
      "admin",
    );

    await waitFor(() => expect(screen.getByText("dave")).toBeInTheDocument());
    expect(
      screen.queryByRole("button", { name: "Remove admin" }),
    ).toBeNull();
  });
});
