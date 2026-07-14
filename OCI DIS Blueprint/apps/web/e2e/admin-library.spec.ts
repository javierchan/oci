/* Visual geometry coverage for the Library governance cards. */

import { expect, test } from "@playwright/test";

test("aligns every Library card action on the same baseline", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.goto("/admin");

  await expect(page.getByRole("heading", { name: "Library", exact: true })).toBeVisible();
  const actions = page.getByTestId("library-card-action");
  await expect(actions).toHaveCount(5);
  const actionTops = await actions.evaluateAll((elements) =>
    elements.map((element) => Math.round(element.getBoundingClientRect().top)),
  );

  expect(new Set(actionTops).size).toBe(1);
});
