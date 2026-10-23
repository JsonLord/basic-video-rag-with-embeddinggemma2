import { test, expect } from "@playwright/test";

test("native browser recording imports through real HTTP, FFmpeg, SQLite, index and original Library", async ({
  page,
}) => {
  test.skip(
    !process.env.VM_RECORDING_FULLSTACK,
    "Requires the explicitly isolated v3_fixture_server; inference is mocked, HTTP/media/index are real.",
  );
  const credential = "v3-synthetic-fixture-user-token-000000";
  await page.goto("/live");
  await page.getByLabel("Session token", { exact: true }).fill(credential);
  await Promise.all([
    page.waitForEvent("load"),
    page
      .getByRole("button", { name: "Connect private library", exact: true })
      .click(),
  ]);
  await expect
    .poll(() => page.evaluate(() => sessionStorage.getItem("vm-user-token")))
    .toBe(credential);
  await page
    .getByRole("button", { name: "Start preview", exact: true })
    .first()
    .click();
  await expect
    .poll(
      () =>
        page
          .getByLabel("camera1 preview", { exact: true })
          .evaluate((v) => (v as HTMLVideoElement).videoWidth),
      { timeout: 15000 },
    )
    .toBeGreaterThan(0);
  await page.getByLabel("camera1 recording consent", { exact: true }).check();
  await page.getByLabel("camera1 microphone consent", { exact: true }).check();
  await page
    .getByRole("button", { name: "Record camera1", exact: true })
    .click();
  await expect(
    page.getByLabel("camera1 recording state", { exact: true }),
  ).toContainText("recording");
  await page.waitForTimeout(1800); // Real native encoding and fake-device microphone audio.
  await page
    .getByRole("button", { name: "Stop recording camera1", exact: true })
    .click();
  await expect(
    page.getByLabel("camera1 recording replay", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("camera1 import consent", { exact: true }).check();
  await page
    .getByRole("button", { name: "Import camera1 to Video RAG", exact: true })
    .click();
  await expect(
    page.getByLabel("camera1 recording job", { exact: true }),
  ).toContainText("complete", { timeout: 60000 });
  await page.getByRole("link", { name: "Library", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Library", exact: true }),
  ).toBeVisible();
  const clip = page.getByText(/^camera1-.*\.webm$/).first();
  await expect(clip).toBeVisible();
  await clip.click();
  await expect(page).toHaveURL(/\/videos\/upload-/);
  await expect(page.locator("video:visible")).toHaveCount(1);
  await expect
    .poll(
      () =>
        page
          .locator("video:visible")
          .evaluate((v) => (v as HTMLVideoElement).readyState),
      { timeout: 15000 },
    )
    .toBeGreaterThanOrEqual(1);
  const search = await page.request.get(
    "/api/search?q=workbench&view=text&dim=3",
    { headers: { Authorization: `Bearer ${credential}` } },
  );
  expect(search.status()).toBe(200);
  expect((await search.json()).hits[0].text).toContain(
    "Synthetic recording evidence",
  );
});
