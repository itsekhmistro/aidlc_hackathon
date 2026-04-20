import { test, expect } from "@playwright/test";

test.describe("Unread badges", () => {
  test("badge appears for recipient and clears on room open", async ({
    browser,
  }) => {
    const ts = Date.now();
    const userA = `una${ts}`;
    const userB = `unb${ts}`;
    const emailA = `${userA}@test.com`;
    const emailB = `${userB}@test.com`;
    const password = "Password123!";

    const ctxA = await browser.newContext();
    const ctxB = await browser.newContext();

    // Register both via raw API (no cookies set yet — that's fine, happens at login)
    await ctxA.request.post("http://localhost:8000/api/auth/register", {
      data: { username: userA, email: emailA, password },
    });
    await ctxB.request.post("http://localhost:8000/api/auth/register", {
      data: { username: userB, email: emailB, password },
    });

    const pageA = await ctxA.newPage();
    const pageB = await ctxB.newPage();

    // Login A
    await pageA.goto("/login");
    await pageA.getByPlaceholder("you@example.com").fill(emailA);
    await pageA.getByPlaceholder("••••••••").fill(password);
    await pageA.getByRole("button", { name: /sign in/i }).click();
    await expect(pageA).toHaveURL(/\/chat(\/|$)/);
    await pageA.waitForSelector("text=Rooms");

    // A creates a public room through the API to get the roomId back
    const roomName = `unr-${ts}`;
    const roomResp = await pageA.request.post(
      "http://localhost:8000/api/rooms",
      {
        data: {
          name: roomName,
          description: "",
          visibility: "public",
        },
      },
    );
    expect(roomResp.ok()).toBeTruthy();
    const room = await roomResp.json();
    const roomId: string = room.id;

    // Reload A so useMyRooms picks up the new room in A's sidebar
    await pageA.goto("/chat");
    await expect(pageA.getByText(roomName)).toBeVisible({ timeout: 10000 });

    // Login B
    await pageB.goto("/login");
    await pageB.getByPlaceholder("you@example.com").fill(emailB);
    await pageB.getByPlaceholder("••••••••").fill(password);
    await pageB.getByRole("button", { name: /sign in/i }).click();
    await expect(pageB).toHaveURL(/\/chat(\/|$)/);
    await pageB.waitForSelector("text=Rooms");

    // B joins the room
    const joinResp = await pageB.request.post(
      `http://localhost:8000/api/rooms/${roomId}/join`,
    );
    expect(joinResp.ok()).toBeTruthy();

    // Reload B to show the room in the sidebar, but stay off the room page
    await pageB.goto("/chat");
    await expect(pageB.getByText(roomName)).toBeVisible({ timeout: 10000 });

    // A opens the room in the UI (so A is on the room and its unread is cleared for A),
    // then sends a message.
    await pageA.getByRole("button").filter({ hasText: roomName }).click();
    await expect(
      pageA.getByPlaceholder("Type a message… (Enter to send)"),
    ).toBeVisible();
    await pageA
      .getByPlaceholder("Type a message… (Enter to send)")
      .fill(`ping ${ts}`);
    await pageA
      .getByPlaceholder("Type a message… (Enter to send)")
      .press("Enter");

    // B (still on /chat) should see a blue badge with a numeric count on the room row
    const roomRow = pageB.getByRole("button").filter({ hasText: roomName });
    const badge = roomRow.locator("span.bg-blue-500");
    await expect(badge).toBeVisible({ timeout: 10000 });
    await expect(badge).toHaveText(/\d+/);

    // B clicks the room row → badge disappears
    await roomRow.click();
    await expect(
      pageB.getByPlaceholder("Type a message… (Enter to send)"),
    ).toBeVisible();
    await expect(badge).toHaveCount(0, { timeout: 5000 });

    await ctxA.close();
    await ctxB.close();
  });
});
