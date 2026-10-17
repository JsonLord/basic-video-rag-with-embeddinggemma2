import { test, expect } from "@playwright/test";
import { corpus, videos } from "./corpus";
const sizes = [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "laptop", width: 1280, height: 900 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "mobile", width: 390, height: 844 },
];
for (const size of sizes) {
  test(`original UI ${size.name}`, async ({ page }) => {
    await page.setViewportSize(size);
    await corpus(page);
    for (const [name, path] of [
      ["library", "/"],
      ["search", "/search?q=bench"],
      ["ask", "/ask"],
      ["experiments", "/experiments"],
      ["architecture", "/architecture"],
      ["video", "/videos/sample-1"],
    ]) {
      await page.goto(path);
      await expect(page.locator("h1").first()).toBeVisible();
      if (name === "library")
        await expect(page.getByText(videos[0].title)).toBeVisible();
      if (name === "search")
        await expect(
          page
            .getByText(
              "Clear the workbench and check equipment before starting.",
            )
            .first(),
        ).toBeVisible();
      await page.evaluate(async () => {
        await document.fonts.ready;
        for (const v of document.querySelectorAll("video")) {
          v.pause();
          v.currentTime = 0;
        }
      });
      await expect(page).toHaveScreenshot(`${name}-${size.name}.png`, {
        fullPage: true,
        animations: "disabled",
        mask: [page.locator("video")],
      });
    }
  });
}
test("clip and citation interactions", async ({ page }) => {
  await corpus(page);
  await page.goto("/ask");
  await page.getByRole("button", { name: "How should I prepare?" }).click();
  await page.getByRole("button", { name: "1", exact: true }).click();
  await expect(page.locator("video")).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await expect(page.locator("video")).toHaveCount(0);
  await page.goto("/videos/sample-1");
  await expect(
    page.getByRole("heading", { name: "Transcript", exact: true }),
  ).toBeVisible();
  await expect(page.locator("video")).toHaveAttribute(
    "src",
    "/sample/video.mp4",
  );
});
