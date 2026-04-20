import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import LoginPage from "../pages/LoginPage";

vi.mock("../hooks/useAuth", () => ({
  useLogin: vi.fn(),
}));

import { useLogin } from "../hooks/useAuth";

function renderLoginPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("LoginPage", () => {
  const mockMutateAsync = vi.fn();

  beforeEach(() => {
    vi.mocked(useLogin).mockReturnValue({
      mutateAsync: mockMutateAsync,
      isPending: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useLogin>);
    mockMutateAsync.mockReset();
  });

  it("renders email, password, persistent checkbox and submit button", () => {
    renderLoginPage();
    expect(screen.getByPlaceholderText("you@example.com")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("••••••••")).toBeInTheDocument();
    expect(screen.getByText("Keep me signed in")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("shows links to register and forgot-password pages", () => {
    renderLoginPage();
    expect(screen.getByRole("link", { name: /register/i })).toHaveAttribute("href", "/register");
    expect(screen.getByRole("link", { name: /forgot password/i })).toHaveAttribute("href", "/forgot-password");
  });

  it("disables submit button while the form is submitting", async () => {
    // Never-resolving promise keeps isSubmitting=true long enough to assert
    let resolveSubmit!: () => void;
    mockMutateAsync.mockReturnValue(new Promise((res) => { resolveSubmit = () => res({}); }));
    renderLoginPage();
    await userEvent.type(screen.getByPlaceholderText("you@example.com"), "alice@test.com");
    await userEvent.type(screen.getByPlaceholderText("••••••••"), "password123");
    // Don't await — fire the click but don't wait for resolution
    const click = userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /signing in/i })).toBeDisabled();
    });
    resolveSubmit();
    await click;
  });

  it("shows validation error for empty email", async () => {
    renderLoginPage();
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => {
      expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
    });
  });

  it("shows validation error for missing password", async () => {
    renderLoginPage();
    await userEvent.type(screen.getByPlaceholderText("you@example.com"), "test@example.com");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => {
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });
  });

  it("calls mutateAsync with email, password, and persistent=false by default", async () => {
    mockMutateAsync.mockResolvedValue({ id: "1", username: "alice" });
    renderLoginPage();
    await userEvent.type(screen.getByPlaceholderText("you@example.com"), "alice@test.com");
    await userEvent.type(screen.getByPlaceholderText("••••••••"), "password123");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        email: "alice@test.com",
        password: "password123",
        persistent: false,
      });
    });
  });

  it("calls mutateAsync with persistent=true when checkbox checked", async () => {
    mockMutateAsync.mockResolvedValue({ id: "1", username: "alice" });
    renderLoginPage();
    await userEvent.type(screen.getByPlaceholderText("you@example.com"), "alice@test.com");
    await userEvent.type(screen.getByPlaceholderText("••••••••"), "password123");
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ persistent: true })
      );
    });
  });

  it("displays server error message on failure", async () => {
    mockMutateAsync.mockRejectedValue(new Error("Incorrect email or password"));
    renderLoginPage();
    await userEvent.type(screen.getByPlaceholderText("you@example.com"), "alice@test.com");
    await userEvent.type(screen.getByPlaceholderText("••••••••"), "wrongpass");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => {
      expect(screen.getByText("Incorrect email or password")).toBeInTheDocument();
    });
  });
});
