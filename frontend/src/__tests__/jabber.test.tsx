import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../hooks/useAuth", () => ({
  useCurrentUser: vi.fn(),
  useLogout: vi.fn(),
}));
vi.mock("../lib/api");

import JabberDashboard from "../pages/admin/JabberDashboard";
import TopNav from "../components/TopNav";
import { useCurrentUser, useLogout } from "../hooks/useAuth";
import { getJabberFederation, getJabberStatus } from "../lib/api";
import type { JabberStatus, UserPublic } from "../lib/types";

const mockGetJabberStatus = vi.mocked(getJabberStatus);
const mockGetJabberFederation = vi.mocked(getJabberFederation);

// Keep unused federation mock referenced so TS/ESLint don't flag it — and so
// future tests that cover JabberFederation can drop in without re-importing.
void mockGetJabberFederation;

function adminUser(overrides: Partial<UserPublic> = {}): UserPublic {
  return {
    id: "user-admin",
    username: "ivan",
    email: "ivan@example.com",
    created_at: "2026-04-20T10:00:00Z",
    is_admin: true,
    ...overrides,
  };
}

function regularUser(overrides: Partial<UserPublic> = {}): UserPublic {
  return {
    id: "user-1",
    username: "alice",
    email: "alice@example.com",
    created_at: "2026-04-20T10:00:00Z",
    is_admin: false,
    ...overrides,
  };
}

function newQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

// ─── JabberDashboard ─────────────────────────────────────────────────────────

describe("JabberDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders metric cards and session rows from mocked status", async () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: adminUser(),
      isLoading: false,
    } as unknown as ReturnType<typeof useCurrentUser>);

    const status: JabberStatus = {
      server_host: "server-a.local",
      uptime_seconds: 8041,
      connected_clients: 47,
      s2s_links_active: 2,
      sessions: [
        { jid: "alice@server-a.local", client: "Gajim 1.8", ip: "192.168.1.5", connected_seconds: 840 },
        { jid: "bob@server-a.local", client: "Pidgin", ip: "192.168.1.6", connected_seconds: 7201 },
      ],
    };
    mockGetJabberStatus.mockResolvedValue(status);

    render(
      <QueryClientProvider client={newQueryClient()}>
        <MemoryRouter>
          <JabberDashboard />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("server-a.local")).toBeInTheDocument();
    });
    expect(mockGetJabberStatus).toHaveBeenCalled();
    expect(screen.getByText("47")).toBeInTheDocument(); // connected_clients
    expect(screen.getByText("2")).toBeInTheDocument(); // s2s_links_active
    // Sessions table rows
    expect(screen.getByText("alice@server-a.local")).toBeInTheDocument();
    expect(screen.getByText("bob@server-a.local")).toBeInTheDocument();
    expect(screen.getByText("Gajim 1.8")).toBeInTheDocument();
    expect(screen.getByText("Pidgin")).toBeInTheDocument();
  });

  it("redirects non-admin users away from /admin/jabber", async () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: regularUser(),
      isLoading: false,
    } as unknown as ReturnType<typeof useCurrentUser>);
    mockGetJabberStatus.mockResolvedValue({
      server_host: "",
      uptime_seconds: 0,
      connected_clients: 0,
      s2s_links_active: 0,
      sessions: [],
    });

    render(
      <QueryClientProvider client={newQueryClient()}>
        <MemoryRouter>
          <JabberDashboard />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // Non-admins never trigger the status fetch — the hook's `enabled` guard
    // short-circuits before it runs.
    expect(mockGetJabberStatus).not.toHaveBeenCalled();
    // The page returns <Navigate /> — server_host should never render
    expect(screen.queryByText("server-a.local")).not.toBeInTheDocument();
  });
});

// ─── TopNav admin gating ─────────────────────────────────────────────────────

describe("TopNav — Jabber Admin gating", () => {
  const mockMutateAsync = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useLogout).mockReturnValue({
      mutateAsync: mockMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useLogout>);
  });

  function renderNav() {
    return render(
      <QueryClientProvider client={newQueryClient()}>
        <MemoryRouter>
          <TopNav />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it("hides the Jabber Admin entry when is_admin is false", async () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: regularUser(),
    } as unknown as ReturnType<typeof useCurrentUser>);

    renderNav();
    await userEvent.click(screen.getByRole("button", { name: /user menu/i }));
    expect(screen.queryByRole("menuitem", { name: /jabber admin/i })).toBeNull();
    expect(screen.queryByRole("menuitem", { name: /^federation$/i })).toBeNull();
  });

  it("shows the Jabber Admin entry when is_admin is true", async () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: adminUser(),
    } as unknown as ReturnType<typeof useCurrentUser>);

    renderNav();
    await userEvent.click(screen.getByRole("button", { name: /user menu/i }));
    const link = screen.getByRole("menuitem", { name: /jabber admin/i });
    expect(link).toHaveAttribute("href", "/admin/jabber");
    const fed = screen.getByRole("menuitem", { name: /^federation$/i });
    expect(fed).toHaveAttribute("href", "/admin/jabber/federation");
  });
});
