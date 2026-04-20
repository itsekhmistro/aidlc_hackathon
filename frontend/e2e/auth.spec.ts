import { test, expect } from "@playwright/test";

test.describe("Auth flows", () => {
  test("register and redirect to chat", async ({ page }) => {
    const ts = Date.now();
    await page.goto("/register");
    await page.getByPlaceholder("johndoe").fill(`user${ts}`);
    await page.getByPlaceholder("you@example.com").fill(`user${ts}@test.com`);
    // first ●●●●●●●● is the password field, second is confirm
    const passwordFields = page.getByPlaceholder("••••••••");
    await passwordFields.first().fill("Password123!");
    await passwordFields.nth(1).fill("Password123!");
    await page.getByRole("button", { name: /create account/i }).click();
    await expect(page).toHaveURL(/\/chat(\/|$)/);
  });

  test("login with valid credentials redirects to chat", async ({ page }) => {
    const ts = Date.now();
    await page.request.post("http://localhost:8000/api/auth/register", {
      data: { username: `u${ts}`, email: `u${ts}@test.com`, password: "Password123!" },
    });
    await page.goto("/login");
    await page.getByPlaceholder("you@example.com").fill(`u${ts}@test.com`);
    await page.getByPlaceholder("••••••••").fill("Password123!");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/chat(\/|$)/);
  });

  test("login with wrong password shows error", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("you@example.com").fill("nobody@test.com");
    await page.getByPlaceholder("••••••••").fill("wrongpassword");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page.getByText(/incorrect|invalid|unauthorized/i)).toBeVisible();
  });
});
