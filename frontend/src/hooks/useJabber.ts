import { useQuery } from "@tanstack/react-query";
import { getJabberFederation, getJabberStatus } from "../lib/api";
import type { JabberFederation, JabberStatus } from "../lib/types";
import { useCurrentUser } from "./useAuth";

const POLL_INTERVAL_MS = 10_000;

export function useJabberStatus() {
  const { data: me } = useCurrentUser();
  return useQuery<JabberStatus>({
    queryKey: ["jabber", "status"],
    queryFn: getJabberStatus,
    refetchInterval: POLL_INTERVAL_MS,
    refetchOnWindowFocus: false,
    retry: false,
    enabled: me?.is_admin === true,
  });
}

export function useJabberFederation() {
  const { data: me } = useCurrentUser();
  return useQuery<JabberFederation>({
    queryKey: ["jabber", "federation"],
    queryFn: getJabberFederation,
    refetchInterval: POLL_INTERVAL_MS,
    refetchOnWindowFocus: false,
    retry: false,
    enabled: me?.is_admin === true,
  });
}
