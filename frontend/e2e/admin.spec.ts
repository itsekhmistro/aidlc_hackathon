import { test, expect } from "@playwright/test";

/**
 * TASK-10 — Admin & Moderation UI
 *
 * Owner creates a public room, invites a second user, the second user joins,
 * then the owner opens Manage Room → Members tab → bans the member. The
 * member disappears from Members and appears in the Banned tab. Unban from
 * Banned tab restores them to Members.
 */
test.describe("Admin & Moderation UI", () => {
  test("owner can ban and unban a member via Manage Room", async ({
    browser,
  }) => {
    const ts = Date.now();
    const owner = `adm${ts}`;
    const member = `mem${ts}`;
    const emailOwner = `${owner}@test.com`;
    const emailMember = `${member}@test.com`;
    const password = "Password123!";
    const roomName = `admroom-${ts}`;

    const ctxOwner = await browser.newContext();
    const ctxMember = await browser.newContext();

    // --- Register both users + create room via API ---
    for (const [ctx, username, email] of [
      [ctxOwner, owner, emailOwner],
      [ctxMember, member, emailMember],
    ] as const) {
      const r = await ctx.request.post(
        "http://localhost:8000/api/auth/register",
        { data: { username, email, password } },
      );
      expect(r.ok()).toBeTruthy();
    }

    const createResp = await ctxOwner.request.post(
      "http://localhost:8000/api/rooms",
      { data: { name: roomName, visibility: "public" } },
    );
    expect(createResp.ok()).toBeTruthy();
    const room = await createResp.json();
    const roomId: string = room.id;

    const joinResp = await ctxMember.request.post(
      `http://localhost:8000/api/rooms/${roomId}/join`,
    );
    expect(joinResp.ok()).toBeTruthy();

    // --- Login owner and navigate into the room ---
    const page = await ctxOwner.newPage();
    await page.goto("/login");
    await page.getByPlaceholder("you@example.com").fill(emailOwner);
    await page.getByPlaceholder("••••••••").fill(password);
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/chat(\/|$)/);
    await page.goto(`/chat/rooms/${roomId}`);
    await expect(
      page.getByPlaceholder("Type a message… (Enter to send)"),
    ).toBeVisible();

    // --- Right sidebar shows the Manage button for the owner ---
    const rightSidebar = page
      .getByRole("complementary")
      .filter({ hasText: /^Members \(\d+\)/ });
    await expect(rightSidebar).toBeVisible();
    await expect(
      rightSidebar.getByText(member, { exact: true }),
    ).toBeVisible();

    await rightSidebar.getByRole("button", { name: "Manage" }).click();

    // --- Members tab is the default view — ban the member ---
    const membersPanel = page.getByRole("tabpanel", { name: "Members" });
    await expect(membersPanel.getByText(member, { exact: true })).toBeVisible();
    await membersPanel.getByRole("button", { name: "Ban" }).click();

    // Confirm ban in the ConfirmModal (heading "Ban member").
    const confirmDialog = page
      .locator("div")
      .filter({ hasText: /^Ban member/ })
      .last();
    await confirmDialog.getByRole("button", { name: "Ban" }).click();

    // Member disappears from the Members tab list.
    await expect(membersPanel.getByText(member, { exact: true })).toBeHidden({
      timeout: 8000,
    });

    // --- Switch to Banned tab and verify the user appears there ---
    await page.getByRole("tab", { name: "Banned" }).click();
    const bannedPanel = page.getByRole("tabpanel", { name: "Banned" });
    await expect(bannedPanel.getByText(member, { exact: true })).toBeVisible({
      timeout: 8000,
    });

    // --- Unban — list becomes empty ---
    await bannedPanel.getByRole("button", { name: "Unban" }).click();
    await expect(bannedPanel.getByText(/No banned users/i)).toBeVisible({
      timeout: 8000,
    });

    await ctxOwner.close();
    await ctxMember.close();
  });
});
