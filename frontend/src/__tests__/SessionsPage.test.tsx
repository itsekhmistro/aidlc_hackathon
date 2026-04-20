import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import SessionsPage from "../pages/SessionsPage";
import { api } from "../lib/api";
import type { SessionPublic } from "../lib/types";

vi.mock("../lib/api");
const mockApi = vi.mocked(api);

function renderSessionsPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SessionsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function session(overrides: Partial<SessionPublic>): SessionPublic {
  return {
    id: "s-1",
    user_agent: "Mozilla/5.0 Chrome",
    ip_address: "1.2.3.4",
    created_at: "2026-04-20T10:00:00Z",
    last_seen_at: "2026-04-20T12:00:00Z",
    ...overrides,
  };
}

describe("SessionsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches sessions from /api/sessions", async () => {
    mockApi.get = vi.fn().mockResolvedValue([session({})]);
    renderSessionsPage();
    await waitFor(() => {
      expect(mockApi.get).toHaveBeenCalledWith("/api/sessions");
    });
  });

  it("lists each session with user_agent and ip_address", async () => {
    mockApi.get = vi.fn().mockResolvedValue([
      session({ id: "s-1", user_agent: "Chrome", ip_address: "1.1.1.1" }),
      session({ id: "s-2", user_agent: "Firefox", ip_address: "2.2.2.2" }),
    ]);
    renderSessionsPage();
    await waitFor(() => {
      expect(screen.getByText("Chrome")).toBeInTheDocument();
      expect(screen.getByText("Firefox")).toBeInTheDocument();
      expect(screen.getByText(/1\.1\.1\.1/)).toBeInTheDocument();
      expect(screen.getByText(/2\.2\.2\.2/)).toBeInTheDocument();
    });
  });

  it("revoke button calls DELETE /api/sessions/:id", async () => {
    mockApi.get = vi.fn().mockResolvedValue([session({ id: "s-42" })]);
    mockApi.delete = vi.fn().mockResolvedValue(undefined);
    renderSessionsPage();
    const revokeBtn = await screen.findByRole("button", { name: /revoke/i });
    await userEvent.click(revokeBtn);
    await waitFor(() => {
      expect(mockApi.delete).toHaveBeenCalledWith("/api/sessions/s-42");
    });
  });

  it("shows empty-state when there are no sessions", async () => {
    mockApi.get = vi.fn().mockResolvedValue([]);
    renderSessionsPage();
    await waitFor(() => {
      expect(screen.getByText(/No active sessions/i)).toBeInTheDocument();
    });
  });

  it("renders fallback for missing user_agent", async () => {
    mockApi.get = vi.fn().mockResolvedValue([session({ user_agent: null })]);
    renderSessionsPage();
    await waitFor(() => {
      expect(screen.getByText(/Unknown device/i)).toBeInTheDocument();
    });
  });
});
