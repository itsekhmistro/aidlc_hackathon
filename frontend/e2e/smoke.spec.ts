import { test, expect, type Page, type ConsoleMessage } from "@playwright/test";

/**
 * Attach console/pageerror listeners to a page and return a drainer that
 * fails if any uncaught JS error or console.error was emitted while the
 * listener was active.
 *
 * We intentionally IGNORE network-related console errors (e.g. 401 Unauthorized
 * emitted by the browser itself for failed fetch responses) because app code
 * is allowed to make requests that fail and catch them in React Query.
 */
function trackErrors(page: Page) {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];

  const onConsole = (msg: ConsoleMessage) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    // The browser logs "Failed to load resource: the server responded with a status of…"
    // for every non-2xx fetch. Those are not uncaught JS errors.
    if (/Failed to load resource/i.test(text)) return;
    if (/status of 40\d/i.test(text)) return;
    consoleErrors.push(text);
  };
  const onPageError = (err: Error) => {
    pageErrors.push(err.message);
  };

  page.on("console", onConsole);
  page.on("pageerror", onPageError);

  return {
    consoleErrors,
    pageErrors,
    dispose() {
      page.off("console", onConsole);
      page.off("pageerror", onPageError);
    },
  };
}

async function registerAndLogin(page: Page, ts: number) {
  const username = `sm${ts}`;
  const email = `${username}@test.com`;
  const password = "Password123!";
  await page.request.post("http://localhost:8000/api/auth/register", {
    data: { username, email, password },
  });
  await page.goto("/login");
  await page.getByPlaceholder("you@example.com").fill(email);
  await page.getByPlaceholder("••••••••").fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/chat(\/|$)/);
  await page.waitForSelector("text=Rooms");
  return { username, email };
}

test.describe("Smoke — primary routes render without errors", () => {
  test("visit /chat, /rooms, /sessions, /profile — no uncaught errors", async ({
    page,
  }) => {
    const ts = Date.now();
    const { username, email } = await registerAndLogin(page, ts);

    const tracker = trackErrors(page);

    // /chat
    await page.goto("/chat");
    await expect(page.getByText("Rooms", { exact: true })).toBeVisible();

    // /rooms — discovery page
    await page.goto("/rooms");
    await expect(
      page.getByRole("heading", { name: /discover rooms/i }),
    ).toBeVisible({ timeout: 5000 });
    await expect(page.getByPlaceholder(/search rooms/i)).toBeVisible();

    // /sessions — the user just logged in, so there should be >= 1 session row,
    // and exactly ONE "Current session" pill.
    await page.goto("/sessions");
    await expect(
      page.getByRole("heading", { name: /active sessions/i }),
    ).toBeVisible({ timeout: 5000 });
    const currentPill = page.getByText("Current session", { exact: true });
    await expect(currentPill).toHaveCount(1, { timeout: 5000 });

    // /profile — username and email rendered
    await page.goto("/profile");
    await expect(
      page.getByRole("heading", { name: /profile/i }),
    ).toBeVisible({ timeout: 5000 });
    const main = page.getByRole("main");
    await expect(main.getByText(username, { exact: true })).toBeVisible();
    await expect(main.getByText(email, { exact: true })).toBeVisible();

    // Drain & assert: nothing should have been caught
    tracker.dispose();
    expect(
      tracker.pageErrors,
      `Uncaught page errors: ${tracker.pageErrors.join("\n")}`,
    ).toEqual([]);
    expect(
      tracker.consoleErrors,
      `Console errors: ${tracker.consoleErrors.join("\n")}`,
    ).toEqual([]);
  });
});
