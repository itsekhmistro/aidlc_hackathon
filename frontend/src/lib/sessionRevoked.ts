import type { QueryClient } from "@tanstack/react-query";
import type { NavigateFunction } from "react-router-dom";
import { api } from "./api";

// Any tab of this user can receive `session.revoked`. We probe /api/auth/me to
// learn whether *this* tab was the revoked one: 401 → kick to /login; 200 →
// some other tab was revoked, just refresh the sessions list.
export function handleSessionRevoked(
  qc: QueryClient,
  navigate: NavigateFunction,
): Promise<void> {
  return api
    .get("/api/auth/me")
    .then(() => {
      qc.invalidateQueries({ queryKey: ["sessions"] });
    })
    .catch(() => {
      qc.setQueryData(["me"], null);
      navigate("/login", { replace: true });
    });
}
