import fs from "fs";
import path from "path";

import { expect, test } from "@playwright/test";

const seed = JSON.parse(
  fs.readFileSync(path.join(process.cwd(), "e2e", ".seed.json"), "utf8"),
);

test("local app can browse seeded tasks and save caption defaults", async ({ page }) => {
  await page.goto("/list");
  await expect(page.getByText(seed.completedSourceTitle)).toBeVisible();

  await page.goto(`/tasks/${seed.completedTaskId}`);
  await expect(page.getByText("This is a seeded clip")).toBeVisible();

  await page.goto("/settings");
  await page.getByRole("button", { name: /save caption defaults/i }).click();
  await expect(page.getByText(/preferences saved/i)).toBeVisible();
});

test("local administration page is open", async ({ page }) => {
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: /local administration/i })).toBeVisible();
  await expect(page.getByText(/user administration was removed/i)).toBeVisible();
});
