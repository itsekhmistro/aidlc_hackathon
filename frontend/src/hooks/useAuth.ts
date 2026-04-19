import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { UserPublic } from "../lib/types";

const TOKEN_KEY = "access_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function useCurrentUser() {
  return useQuery<UserPublic>({
    queryKey: ["me"],
    queryFn: async () => {
      const token = getToken();
      const res = await fetch("/api/v1/users/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Unauthorized");
      return res.json() as Promise<UserPublic>;
    },
    enabled: !!getToken(),
    retry: false,
    staleTime: 1000 * 60 * 5,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ email, password }: { email: string; password: string }) => {
      const body = new URLSearchParams({ username: email, password });
      const res = await fetch("/api/v1/login/access-token", {
        method: "POST",
        body,
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      if (!res.ok) throw new Error("Invalid credentials");
      return res.json() as Promise<{ access_token: string; token_type: string }>;
    },
    onSuccess: (data) => {
      setToken(data.access_token);
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return () => {
    removeToken();
    queryClient.clear();
  };
}
