import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import TopNav from "../components/TopNav";

vi.mock("../hooks/useAuth", () => ({
  useCurrentUser: vi.fn(),
  useLogout: vi.fn(),
}));

import { useCurrentUser, useLogout } from "../hooks/useAuth";

function renderTopNav() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <TopNav />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("TopNav", () => {
  const mockMutateAsync = vi.fn();

  beforeEach(() => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: {
        id: "user-1",
        username: "alice",
        email: "alice@example.com",
        created_at: "2026-04-20T10:00:00Z",
      },
    } as unknown as ReturnType<typeof useCurrentUser>);
    vi.mocked(useLogout).mockReturnValue({
      mutateAsync: mockMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useLogout>);
    mockMutateAsync.mockReset();
    mockMutateAsync.mockResolvedValue(undefined);
  });

  it("shows the brand link and username", () => {
    renderTopNav();
    expect(screen.getByText("Chat")).toBeInTheDocument();
    expect(screen.getByText("alice")).toBeInTheDocument();
  });

  it("shows the user's initial in the avatar", () => {
    renderTopNav();
    expect(screen.getByText("A")).toBeInTheDocument();
  });

  it("does not show the dropdown by default", () => {
    renderTopNav();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("opens the dropdown menu when the user button is clicked", async () => {
    renderTopNav();
    await userEvent.click(screen.getByRole("button", { name: /user menu/i }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
  });

  it("dropdown contains links to Profile and Sessions", async () => {
    renderTopNav();
    await userEvent.click(screen.getByRole("button", { name: /user menu/i }));
    const profileLink = screen.getByRole("menuitem", { name: /profile/i });
    const sessionsLink = screen.getByRole("menuitem", { name: /sessions/i });
    expect(profileLink).toHaveAttribute("href", "/profile");
    expect(sessionsLink).toHaveAttribute("href", "/sessions");
  });

  it("dropdown has a Sign out button that fires the logout mutation", async () => {
    renderTopNav();
    await userEvent.click(screen.getByRole("button", { name: /user menu/i }));
    await userEvent.click(screen.getByRole("menuitem", { name: /sign out/i }));
    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledTimes(1);
    });
  });

  it("brand link navigates to /chat", () => {
    renderTopNav();
    const brand = screen.getByText("Chat").closest("a");
    expect(brand).toHaveAttribute("href", "/chat");
  });
});
