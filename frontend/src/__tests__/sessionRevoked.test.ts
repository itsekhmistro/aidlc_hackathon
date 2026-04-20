import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { handleSessionRevoked } from "../lib/sessionRevoked";

vi.mock("../lib/api");
const mockApi = vi.mocked(api);

describe("handleSessionRevoked", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("kicks the tab to /login when /api/auth/me returns 401", async () => {
    mockApi.get = vi.fn().mockRejectedValue(new Error("HTTP 401"));

    const qc = new QueryClient();
    qc.setQueryData(["me"], { id: "u-1", username: "alice" });
    const navigate = vi.fn();

    await handleSessionRevoked(qc, navigate);

    expect(navigate).toHaveBeenCalledWith("/login", { replace: true });
    expect(qc.getQueryData(["me"])).toBeNull();
  });

  it("only refreshes the sessions list when another tab was revoked", async () => {
    mockApi.get = vi.fn().mockResolvedValue({ id: "u-1", username: "alice" });

    const qc = new QueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const navigate = vi.fn();

    await handleSessionRevoked(qc, navigate);

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["sessions"] });
    expect(navigate).not.toHaveBeenCalled();
  });
});
