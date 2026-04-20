import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import RegisterPage from "../pages/RegisterPage";

vi.mock("../hooks/useAuth", () => ({
  useRegister: vi.fn(),
}));

import { useRegister } from "../hooks/useAuth";

function renderRegisterPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("RegisterPage", () => {
  const mockMutateAsync = vi.fn();

  beforeEach(() => {
    vi.mocked(useRegister).mockReturnValue({
      mutateAsync: mockMutateAsync,
      isPending: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useRegister>);
    mockMutateAsync.mockReset();
  });

  it("renders all fields", () => {
    renderRegisterPage();
    expect(screen.getByPlaceholderText("johndoe")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("you@example.com")).toBeInTheDocument();
    expect(screen.getAllByPlaceholderText("••••••••")).toHaveLength(2);
    expect(screen.getByRole("button", { name: /create account/i })).toBeInTheDocument();
  });

  it("shows validation error when passwords don't match", async () => {
    renderRegisterPage();
    await userEvent.type(screen.getByPlaceholderText("johndoe"), "alice");
    await userEvent.type(screen.getByPlaceholderText("you@example.com"), "alice@test.com");
    const passwords = screen.getAllByPlaceholderText("••••••••");
    await userEvent.type(passwords[0], "password123");
    await userEvent.type(passwords[1], "differentpass");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => {
      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
    });
  });

  it("shows error for too-short password", async () => {
    renderRegisterPage();
    await userEvent.type(screen.getByPlaceholderText("johndoe"), "alice");
    await userEvent.type(screen.getByPlaceholderText("you@example.com"), "alice@test.com");
    const passwords = screen.getAllByPlaceholderText("••••••••");
    await userEvent.type(passwords[0], "short");
    await userEvent.type(passwords[1], "short");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => {
      expect(screen.getByText(/min 8 characters/i)).toBeInTheDocument();
    });
  });

  it("calls mutateAsync with correct payload on valid submit", async () => {
    mockMutateAsync.mockResolvedValue({ id: "1", username: "alice" });
    renderRegisterPage();
    await userEvent.type(screen.getByPlaceholderText("johndoe"), "alice");
    await userEvent.type(screen.getByPlaceholderText("you@example.com"), "alice@test.com");
    const passwords = screen.getAllByPlaceholderText("••••••••");
    await userEvent.type(passwords[0], "password123");
    await userEvent.type(passwords[1], "password123");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        username: "alice",
        email: "alice@test.com",
        password: "password123",
      });
    });
  });

  it("displays server error inline", async () => {
    mockMutateAsync.mockRejectedValue(new Error("Username already taken"));
    renderRegisterPage();
    await userEvent.type(screen.getByPlaceholderText("johndoe"), "alice");
    await userEvent.type(screen.getByPlaceholderText("you@example.com"), "alice@test.com");
    const passwords = screen.getAllByPlaceholderText("••••••••");
    await userEvent.type(passwords[0], "password123");
    await userEvent.type(passwords[1], "password123");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => {
      expect(screen.getByText("Username already taken")).toBeInTheDocument();
    });
  });
});
