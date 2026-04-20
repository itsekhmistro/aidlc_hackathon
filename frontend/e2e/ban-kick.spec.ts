import { test, expect } from "@playwright/test";

/**
 * W1.4 — Ban-kick flow
 *
 * When user A bans user B while B is viewing a DM-personal-room with A
 * (URL `/chat/rooms/:roomId` where A appears in the cached room-members
 * query), the `user.banned` WS event delivered by the backend must cause
 * App.tsx's WS handler to navigate B away to `/chat`.
 *
 * We use ONE real browser page (B's victim view) and only `page.request`
 * for A's side — register, friend-request, and ban are all admin/API
 * actions that don't need an A-side UI.
 */
test.describe("Ban-kick flow", () => {
  test("B is auto-navigated to /chat when A bans B during an active DM-room", async ({
    browser,
  }) => {
    const ts = Date.now();
    const userA = `bka${ts}`;
    const userB = `bkb${ts}`;
    const emailA = `${userA}@test.com`;
    const emailB = `${userB}@test.com`;
    const password = "Password123!";

    // Separate request contexts so A's session cookie doesn't collide with B's.
    const ctxA = await browser.newContext();
    const ctxB = await browser.newContext();

    // --- Register both users via API ---
    const regAResp = await ctxA.request.post(
      "http://localhost:8000/api/auth/register",
      { data: { username: userA, email: emailA, password } },
    );
    expect(regAResp.ok()).toBeTruthy();

    const regBResp = await ctxB.request.post(
      "http://localhost:8000/api/auth/register",
      { data: { username: userB, email: emailB, password } },
    );
    expect(regBResp.ok()).toBeTruthy();
    const userBPublic = await regBResp.json();
    const userBId: string = userBPublic.id;
    expect(userBId).toMatch(/^[0-9a-f-]{36}$/);

    // --- A → friend request to B (verified path: POST /api/friends/request) ---
    const reqResp = await ctxA.request.post(
      "http://localhost:8000/api/friends/request",
      { data: { username: userB } },
    );
    expect(reqResp.ok()).toBeTruthy();
    const friendship = await reqResp.json();
    const friendshipId: string = friendship.id;

    // --- B accepts (verified: PATCH /api/friends/{id}/accept) ---
    const acceptResp = await ctxB.request.patch(
      `http://localhost:8000/api/friends/${friendshipId}/accept`,
    );
    expect(acceptResp.ok()).toBeTruthy();

    // --- Login B in a real browser page ---
    const pageB = await ctxB.newPage();
    await pageB.goto("/login");
    await pageB.getByPlaceholder("you@example.com").fill(emailB);
    await pageB.getByPlaceholder("••••••••").fill(password);
    await pageB.getByRole("button", { name: /sign in/i }).click();
    await expect(pageB).toHaveURL(/\/chat(\/|$)/);
    await pageB.waitForSelector("text=Rooms");

    // --- B opens A's contact menu and clicks "Send message" ---
    const contactRow = pageB
      .locator("div")
      .filter({ has: pageB.getByText(userA, { exact: true }) })
      .first();
    await expect(contactRow.getByText(userA, { exact: true })).toBeVisible({
      timeout: 10000,
    });
    await contactRow.hover();
    await contactRow.getByRole("button", { name: "···" }).click();
    await pageB.getByRole("button", { name: /send message/i }).click();

    // DM redirect lands B on the stable `/chat/rooms/:roomId` URL.
    await expect(pageB).toHaveURL(/\/chat\/rooms\/[0-9a-f-]{36}$/, {
      timeout: 10000,
    });

    // Wait for the right sidebar to populate with A's username — that proves
    // the room-members query is cached, which is what App.tsx's `user.banned`
    // handler reads to decide whether to kick B out of the room.
    // Two `complementary` asides exist (left=Contacts, right=Members); scope
    // by the unique "Members (N)" header.
    const rightSidebar = pageB
      .getByRole("complementary")
      .filter({ hasText: /^Members \(\d+\)/ });
    await expect(rightSidebar).toBeVisible({ timeout: 10000 });
    await expect(rightSidebar.getByText(userA, { exact: true })).toBeVisible({
      timeout: 10000,
    });

    // --- A bans B (verified backend path: POST /api/bans) ---
    const banResp = await ctxA.request.post(
      "http://localhost:8000/api/bans",
      { data: { banned_id: userBId } },
    );
    expect(banResp.ok()).toBeTruthy();

    // Within ~5s the backend's `user.banned` WS event reaches B and App.tsx
    // navigates B to `/chat`. (Use a slightly looser 8s ceiling to absorb
    // CI/parallel-worker contention without losing the kick-time assertion.)
    await expect(pageB).toHaveURL(/\/chat$/, { timeout: 8000 });

    await ctxA.close();
    await ctxB.close();
  });
});
