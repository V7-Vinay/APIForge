import { expect, test, type APIRequestContext } from "@playwright/test";

const apiBase = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

async function seedUserAndWorkspace(request: APIRequestContext) {
  const suffix = Math.random().toString(36).slice(2, 10);
  const email = `e2e_${suffix}@example.com`;
  const password = "Password123!";

  const registration = await request.post(`${apiBase}/auth/register`, {
    data: { name: "E2E User", email, password },
  });
  expect(registration.status()).toBe(201);

  const login = await request.post(`${apiBase}/auth/login`, {
    data: { email, password },
  });
  expect(login.status()).toBe(200);
  const token = (await login.json()).access_token as string;
  const headers = { Authorization: `Bearer ${token}` };

  const workspace = await request.post(`${apiBase}/workspaces`, {
    headers,
    data: {
      name: "E2E Workspace",
      slug: `e2e-${suffix}`,
    },
  });
  expect(workspace.status()).toBe(201);

  return { email, password };
}

test("authenticated user can open APIForge workspace UI", async ({ page, request }) => {
  const { email, password } = await seedUserAndWorkspace(request);

  await page.goto("/");
  await expect(page.getByText("Your API workspace starts here.")).toBeVisible();

  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();

  await expect(page.getByText("APIForge").first()).toBeVisible();
  await expect(page.getByPlaceholder("Search collections, folders, requests…")).toBeVisible();
  await expect(page.getByRole("button", { name: "Docs" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Audit" })).toBeVisible();
});
