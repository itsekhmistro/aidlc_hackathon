import { test, expect } from "@playwright/test";

test.describe("DM flow", () => {
  test("send message from contact menu redirects to /chat/rooms/:roomId", async ({
    browser,
  }) => {
    const ts = Date.now();
    const userA = `dma${ts}`;
    const userB = `dmb${ts}`;
    const emailA = `${userA}@test.com`;
    const emailB = `${userB}@test.com`;
    const password = "Password123!";

    const ctxA = await browser.newContext();
    const ctxB = await browser.newContext();

    await ctxA.request.post("http://localhost:8000/api/auth/register", {
      data: { username: userA, email: emailA, password },
    });
    await ctxB.request.post("http://localhost:8000/api/auth/register", {
      data: { username: userB, email: emailB, password },
    });

    const pageA = await ctxA.newPage();
    const pageB = await ctxB.newPage();

    // Login A via UI
    await pageA.goto("/login");
    await pageA.getByPlaceholder("you@example.com").fill(emailA);
    await pageA.getByPlaceholder("••••••••").fill(password);
    await pageA.getByRole("button", { name: /sign in/i }).click();
    await expect(pageA).toHaveURL(/\/chat(\/|$)/);
    await pageA.waitForSelector("text=Rooms");

    // A sends friend request to B via API (POST /api/friends/request with { username })
    const reqResp = await pageA.request.post(
      "http://localhost:8000/api/friends/request",
      { data: { username: userB } },
    );
    expect(reqResp.ok()).toBeTruthy();

    // Login B via UI
    await pageB.goto("/login");
    await pageB.getByPlaceholder("you@example.com").fill(emailB);
    await pageB.getByPlaceholder("••••••••").fill(password);
    await pageB.getByRole("button", { name: /sign in/i }).click();
    await expect(pageB).toHaveURL(/\/chat(\/|$)/);
    await pageB.waitForSelector("text=Rooms");

    // B sees incoming request and clicks ✓ to accept it
    await expect(pageB.getByText(userA)).toBeVisible({ timeout: 10000 });
    await pageB.getByRole("button", { name: "✓" }).click();

    // Back in A's page: reload so the newly-accepted friendship shows in the contacts list
    await pageA.reload();
    await pageA.waitForSelector("text=Rooms");
    const contactRow = pageA
      .locator("div")
      .filter({ has: pageA.getByText(userB, { exact: true }) })
      .first();
    await expect(contactRow.getByText(userB, { exact: true })).toBeVisible({
      timeout: 10000,
    });

    // Hover triggers the ··· button to become visible, but it's always in the DOM.
    // Click the contact's "···" menu button (scoped to that row).
    await contactRow.hover();
    await contactRow.getByRole("button", { name: "···" }).click();
    await pageA.getByRole("button", { name: /send message/i }).click();

    // URL should end up at /chat/rooms/<uuid> via the DM→room redirect
    await expect(pageA).toHaveURL(/\/chat\/rooms\/[0-9a-f-]{36}$/, {
      timeout: 5000,
    });

    const finalUrl = pageA.url();

    // Reload → URL must stay at /chat/rooms/:roomId (replace:true verified —
    // no bounce back to /chat/dm/:userId)
    await pageA.reload();
    await expect(pageA).toHaveURL(/\/chat\/rooms\/[0-9a-f-]{36}$/, {
      timeout: 5000,
    });
    expect(pageA.url()).toBe(finalUrl);

    await ctxA.close();
    await ctxB.close();
  });
});
