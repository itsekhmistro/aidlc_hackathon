import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { UserPublic } from "../lib/types";

export function useCurrentUser() {
  return useQuery<UserPublic>({
    queryKey: ["me"],
    queryFn: () => api.get<UserPublic>("/api/auth/me"),
    retry: false,
    staleTime: 1000 * 60 * 5,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ email, password, persistent }: { email: string; password: string; persistent: boolean }) =>
      api.post<UserPublic>("/api/auth/login", { email, password, persistent }),
    onSuccess: (user) => {
      queryClient.setQueryData(["me"], user);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/api/auth/logout"),
    onSuccess: () => {
      queryClient.clear();
    },
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ username, email, password }: { username: string; email: string; password: string }) =>
      api.post<UserPublic>("/api/auth/register", { username, email, password }),
    onSuccess: (user) => {
      queryClient.setQueryData(["me"], user);
    },
  });
}
