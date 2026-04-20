import { test, expect, type Page } from "@playwright/test";

async function registerAndLogin(page: Page, ts: number, tag = "rep") {
  const username = `${tag}${ts}`;
  await page.request.post("http://localhost:8000/api/auth/register", {
    data: {
      username,
      email: `${username}@test.com`,
      password: "Password123!",
    },
  });
  await page.goto("/login");
  await page.getByPlaceholder("you@example.com").fill(`${username}@test.com`);
  await page.getByPlaceholder("••••••••").fill("Password123!");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/chat(\/|$)/);
  await page.waitForSelector("text=Rooms");
  return username;
}

test.describe("Reply round-trip", () => {
  test("reply-preview bubble renders after round-trip", async ({ page }) => {
    const ts = Date.now();
    await registerAndLogin(page, ts);

    // Create a room and open it.
    await page.getByTitle("Create room").click();
    await page.getByPlaceholder("Room name").fill(`reply-${ts}`);
    await page.getByRole("button", { name: /create/i }).click();
    const roomLink = page.getByText(`reply-${ts}`);
    await expect(roomLink).toBeVisible({ timeout: 10000 });
    await roomLink.click();

    const input = page.getByPlaceholder("Type a message… (Enter to send)");
    await expect(input).toBeVisible();

    // Send the ground-truth message that will be replied to.
    const originalText = `original-${ts}`;
    await input.fill(originalText);
    await input.press("Enter");
    await expect(page.getByText(originalText)).toBeVisible({ timeout: 5000 });

    // Click the ↩ Reply button on the ground-truth bubble. It's own message,
    // so Reply appears alongside Edit/Delete; we pick the first (there is only
    // one so far, but scoping to the bubble that contains the original text
    // is still more robust than "any Reply button on the page").
    const bubble = page
      .locator("div.group")
      .filter({ hasText: originalText })
      .first();
    await bubble.getByRole("button", { name: "Reply" }).click();

    // The reply strip above the input should echo the original content.
    const replyStrip = page.getByTestId("reply-strip");
    await expect(replyStrip).toBeVisible();
    await expect(replyStrip).toContainText(originalText);

    // Send the reply.
    const replyText = `answer-${ts}`;
    await input.fill(replyText);
    await input.press("Enter");

    // Round-trip assertion: a new bubble renders with both the reply body
    // and a `data-testid="reply-preview"` element containing the original
    // message's content — proving the server returned a reply_preview and
    // the client rendered it back into the thread.
    const replyBubble = page
      .locator("div.group")
      .filter({ hasText: replyText })
      .last();
    await expect(replyBubble).toBeVisible({ timeout: 5000 });
    const preview = replyBubble.getByTestId("reply-preview");
    await expect(preview).toBeVisible();
    await expect(preview).toContainText(originalText);
  });
});
