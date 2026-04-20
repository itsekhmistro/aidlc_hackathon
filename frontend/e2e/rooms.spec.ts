import { test, expect } from "@playwright/test";

async function registerAndLogin(page: any, ts: number) {
  await page.request.post("http://localhost:8000/api/auth/register", {
    data: { username: `r${ts}`, email: `r${ts}@test.com`, password: "Password123!" },
  });
  await page.goto("/login");
  await page.getByPlaceholder("you@example.com").fill(`r${ts}@test.com`);
  await page.getByPlaceholder("••••••••").fill("Password123!");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/chat(\/|$)/);
  // Wait for sidebar to fully load
  await page.waitForSelector("text=Rooms");
}

test.describe("Rooms", () => {
  test("create a room and see it in sidebar", async ({ page }) => {
    const ts = Date.now();
    await registerAndLogin(page, ts);
    // Find and click "+ New" button for rooms (using title attribute)
    await page.getByTitle("Create room").click();
    // Fill room name
    await page.getByPlaceholder("Room name").fill(`room-${ts}`);
    await page.getByRole("button", { name: /create/i }).click();
    await expect(page.getByText(`room-${ts}`)).toBeVisible({ timeout: 10000 });
  });

  test("click a room and see message thread", async ({ page }) => {
    const ts = Date.now();
    await registerAndLogin(page, ts);

    // Create room via the UI (so it uses the browser's session)
    await page.getByTitle("Create room").click();
    await page.getByPlaceholder("Room name").fill(`chat-${ts}`);
    await page.getByRole("button", { name: /create/i }).click();
    // Wait for the room to appear in sidebar and click it
    const roomLink = page.getByText(`chat-${ts}`);
    await expect(roomLink).toBeVisible({ timeout: 10000 });
    await roomLink.click();
    // Should see the message input for that room
    await expect(page.getByPlaceholder("Type a message… (Enter to send)")).toBeVisible();
  });
});
