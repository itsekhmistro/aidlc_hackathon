import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MemberRowMenu from "../components/MemberRowMenu";
import { api } from "../lib/api";
import type { FriendshipPublic, RoomMemberPublic } from "../lib/types";

vi.mock("../lib/api");
const mockApi = vi.mocked(api);

const navigateMock = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return { ...actual, useNavigate: () => navigateMock };
});

function member(overrides: Partial<RoomMemberPublic> = {}): RoomMemberPublic {
  return {
    user_id: "u-2",
    username: "bob",
    role: "member",
    presence_status: "online",
    joined_at: "2026-04-20T10:00:00Z",
    ...overrides,
  };
}

function renderMenu(props: Partial<React.ComponentProps<typeof MemberRowMenu>> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const defaults: React.ComponentProps<typeof MemberRowMenu> = {
    roomId: "room-1",
    roomName: "general",
    member: member(),
    myRole: "member",
    meId: "u-1",
  };
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <MemberRowMenu {...defaults} {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function stubFriends(friends: FriendshipPublic[] = []) {
  mockApi.get = vi.fn(async (path: string) => {
    if (path === "/api/friends") return friends as unknown as never;
    return [] as unknown as never;
  });
}

describe("MemberRowMenu", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    navigateMock.mockReset();
    stubFriends();
    mockApi.post = vi.fn().mockResolvedValue(undefined);
    mockApi.delete = vi.fn().mockResolvedValue(undefined);
  });

  it("renders null when the member is the current user", () => {
    const { container } = renderMenu({ member: member({ user_id: "u-1" }) });
    expect(container).toBeEmptyDOMElement();
  });

  it("opens the menu and exposes Send message + Send friend request for a member peer", async () => {
    const user = userEvent.setup();
    renderMenu();
    await user.click(screen.getByRole("button", { name: /actions for bob/i }));
    expect(screen.getByRole("button", { name: "Send message" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Send friend request" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Make admin" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Ban from room" })).toBeNull();
  });

  it("hides Send friend request when the peer is already an accepted friend", async () => {
    const user = userEvent.setup();
    stubFriends([
      {
        id: "f-1",
        requester_id: "u-1",
        requester_username: "me",
        addressee_id: "u-2",
        addressee_username: "bob",
        status: "accepted",
        message: null,
        created_at: "",
        updated_at: "",
      },
    ]);
    renderMenu();
    // Wait for useFriends query to resolve.
    await waitFor(() => expect(mockApi.get).toHaveBeenCalledWith("/api/friends"));
    await user.click(screen.getByRole("button", { name: /actions for bob/i }));
    expect(screen.queryByRole("button", { name: "Send friend request" })).toBeNull();
    expect(screen.getByRole("button", { name: "Send message" })).toBeVisible();
  });

  it("owner sees Make admin + Ban for a member peer", async () => {
    const user = userEvent.setup();
    renderMenu({ myRole: "owner" });
    await user.click(screen.getByRole("button", { name: /actions for bob/i }));
    expect(screen.getByRole("button", { name: "Make admin" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Ban from room" })).toBeVisible();
  });

  it("owner sees Remove admin instead of Make admin for an admin peer", async () => {
    const user = userEvent.setup();
    renderMenu({ myRole: "owner", member: member({ role: "admin" }) });
    await user.click(screen.getByRole("button", { name: /actions for bob/i }));
    expect(screen.getByRole("button", { name: "Remove admin" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Make admin" })).toBeNull();
    expect(screen.getByRole("button", { name: "Ban from room" })).toBeVisible();
  });

  it("admin sees Ban but not Make/Remove admin for a member peer", async () => {
    const user = userEvent.setup();
    renderMenu({ myRole: "admin" });
    await user.click(screen.getByRole("button", { name: /actions for bob/i }));
    expect(screen.queryByRole("button", { name: "Make admin" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Remove admin" })).toBeNull();
    expect(screen.getByRole("button", { name: "Ban from room" })).toBeVisible();
  });

  it("hides all admin actions when the peer is the room owner", async () => {
    const user = userEvent.setup();
    renderMenu({ myRole: "owner", member: member({ role: "owner" }) });
    await user.click(screen.getByRole("button", { name: /actions for bob/i }));
    expect(screen.queryByRole("button", { name: "Make admin" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Remove admin" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Ban from room" })).toBeNull();
  });

  it("Send message resolves the personal room and navigates to the DM", async () => {
    const user = userEvent.setup();
    mockApi.get = vi.fn(async (path: string) => {
      if (path === "/api/friends") return [] as unknown as never;
      if (path === "/api/personal-rooms/u-2")
        return {
          id: "pr-1",
          name: "__dm__:u-1:u-2",
          display_name: "bob",
          description: null,
          visibility: "private",
          owner_id: "u-1",
          is_personal: true,
          created_at: "",
          member_count: 2,
        } as unknown as never;
      return [] as unknown as never;
    });
    renderMenu();
    await user.click(screen.getByRole("button", { name: /actions for bob/i }));
    await user.click(screen.getByRole("button", { name: "Send message" }));
    await waitFor(() =>
      expect(navigateMock).toHaveBeenCalledWith("/chat/dm/u-2"),
    );
  });

  it("Send friend request POSTs to /api/friends/request with the target username", async () => {
    const user = userEvent.setup();
    renderMenu();
    await user.click(screen.getByRole("button", { name: /actions for bob/i }));
    await user.click(screen.getByRole("button", { name: "Send friend request" }));
    await waitFor(() =>
      expect(mockApi.post).toHaveBeenCalledWith("/api/friends/request", {
        username: "bob",
      }),
    );
  });

  it("Ban opens a confirm modal and DELETEs only after confirm", async () => {
    const user = userEvent.setup();
    renderMenu({ myRole: "owner" });
    await user.click(screen.getByRole("button", { name: /actions for bob/i }));
    await user.click(screen.getByRole("button", { name: "Ban from room" }));
    expect(screen.getByText("Ban member")).toBeVisible();
    expect(mockApi.delete).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Ban" }));
    await waitFor(() =>
      expect(mockApi.delete).toHaveBeenCalledWith("/api/rooms/room-1/members/u-2"),
    );
  });

  it("admin cannot act on another admin peer (Ban hidden)", async () => {
    const user = userEvent.setup();
    renderMenu({ myRole: "admin", member: member({ role: "admin" }) });
    await user.click(screen.getByRole("button", { name: /actions for bob/i }));
    expect(screen.queryByRole("button", { name: "Ban from room" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Make admin" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Remove admin" })).toBeNull();
  });

  it("still shows Send friend request when the peer has only a pending friendship", async () => {
    const user = userEvent.setup();
    stubFriends([
      {
        id: "f-1",
        requester_id: "u-1",
        requester_username: "me",
        addressee_id: "u-2",
        addressee_username: "bob",
        status: "pending",
        message: null,
        created_at: "",
        updated_at: "",
      },
    ]);
    renderMenu();
    await waitFor(() => expect(mockApi.get).toHaveBeenCalledWith("/api/friends"));
    await user.click(screen.getByRole("button", { name: /actions for bob/i }));
    expect(
      screen.getByRole("button", { name: "Send friend request" }),
    ).toBeVisible();
  });

  it("Make admin POSTs to /admin for an owner viewer and a member peer", async () => {
    const user = userEvent.setup();
    renderMenu({ myRole: "owner" });
    await user.click(screen.getByRole("button", { name: /actions for bob/i }));
    await user.click(screen.getByRole("button", { name: "Make admin" }));
    await waitFor(() =>
      expect(mockApi.post).toHaveBeenCalledWith(
        "/api/rooms/room-1/members/u-2/admin",
      ),
    );
  });

  it("Remove admin DELETEs /admin for an owner viewer and an admin peer", async () => {
    const user = userEvent.setup();
    renderMenu({ myRole: "owner", member: member({ role: "admin" }) });
    await user.click(screen.getByRole("button", { name: /actions for bob/i }));
    await user.click(screen.getByRole("button", { name: "Remove admin" }));
    await waitFor(() =>
      expect(mockApi.delete).toHaveBeenCalledWith(
        "/api/rooms/room-1/members/u-2/admin",
      ),
    );
  });

  it("Cancel in the ban confirm modal does not issue a DELETE", async () => {
    const user = userEvent.setup();
    renderMenu({ myRole: "owner" });
    await user.click(screen.getByRole("button", { name: /actions for bob/i }));
    await user.click(screen.getByRole("button", { name: "Ban from room" }));
    expect(screen.getByText("Ban member")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText("Ban member")).toBeNull();
    expect(mockApi.delete).not.toHaveBeenCalled();
  });

  it("closes the menu when the user clicks outside the wrapper", async () => {
    const user = userEvent.setup();
    renderMenu();
    await user.click(screen.getByRole("button", { name: /actions for bob/i }));
    expect(screen.getByRole("button", { name: "Send message" })).toBeVisible();
    // Simulate a mousedown outside the menu wrapper (the registered listener).
    document.body.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Send message" })).toBeNull(),
    );
  });
});
