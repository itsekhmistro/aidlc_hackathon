import { test, expect } from "@playwright/test";

async function registerAndLogin(page: any, ts: number, tag = "a") {
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

test.describe("Attachments", () => {
  test("upload a text file and see it rendered in the bubble", async ({ page }) => {
    const ts = Date.now();
    await registerAndLogin(page, ts, "att");

    // Create a room via UI
    await page.getByTitle("Create room").click();
    await page.getByPlaceholder("Room name").fill(`att-${ts}`);
    await page.getByRole("button", { name: /create/i }).click();

    // Open the room
    const roomLink = page.getByText(`att-${ts}`);
    await expect(roomLink).toBeVisible({ timeout: 10000 });
    await roomLink.click();
    await expect(
      page.getByPlaceholder("Type a message… (Enter to send)"),
    ).toBeVisible();

    // Upload via hidden input
    const body = Buffer.from("hello attachment");
    await page.setInputFiles('input[type="file"]', {
      name: "demo.txt",
      mimeType: "text/plain",
      buffer: body,
    });

    // Wait for the pending chip to lose its spinner (upload complete).
    // The chip span still contains "demo.txt" but no longer the ⏳ glyph.
    const pendingChip = page
      .locator("span")
      .filter({ hasText: "demo.txt" })
      .first();
    await expect(pendingChip).toBeVisible({ timeout: 5000 });
    await expect(pendingChip.locator(".animate-spin")).toHaveCount(0, {
      timeout: 10000,
    });

    // Type the message and send
    await page
      .getByPlaceholder("Type a message… (Enter to send)")
      .fill("see file");
    await page
      .getByPlaceholder("Type a message… (Enter to send)")
      .press("Enter");

    // Expect the bubble to contain the attachment link with filename and size
    const link = page.getByRole("link", { name: /demo\.txt/ });
    await expect(link).toBeVisible({ timeout: 5000 });
    await expect(link).toContainText("demo.txt");
    await expect(link).toContainText("16B");
    const href = await link.getAttribute("href");
    expect(href).toMatch(/\/api\/attachments\//);
  });
});
