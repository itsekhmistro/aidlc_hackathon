import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { SessionPublic } from "../lib/types";

export function useSessions() {
  return useQuery<SessionPublic[]>({
    queryKey: ["sessions"],
    queryFn: () => api.get<SessionPublic[]>("/api/sessions"),
    retry: false,
  });
}

export function useRevokeSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => api.delete<void>(`/api/sessions/${sessionId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
}
