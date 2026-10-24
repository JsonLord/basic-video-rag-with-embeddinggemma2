import { expect, test } from "@playwright/test";

test("automatic framing selects highest confidence once, keeps camera identities and recovers on loss", async ({
  page,
}) => {
  let reverse = false,
    missing = false;
  await page.route("**/api/providers", (route) =>
    route.fulfill({
      json: {
        config_version: 1,
        providers: {
          gateway: { destination: "nvidia-gateway-fixture.invalid" },
        },
        features: {
          "live.camera1.scene": { enabled: true, providers: ["gateway"] },
          "live.camera2.scene": { enabled: true, providers: ["gateway"] },
        },
      },
    }),
  );
  await page.route("**/api/live/sessions", (route) =>
    route.fulfill({
      json: { session_id: "gate06-framing-session", config_version: 1 },
    }),
  );
  await page.route("**/api/live/sessions/gate06-framing-session", (route) =>
    route.fulfill({ json: { deleted: true } }),
  );
  await page.route(
    "**/api/live/sessions/gate06-framing-session/frames",
    (route) => {
      const body = route.request().postDataJSON();
      const boxes = [
        {
          detection_id: "first",
          object_id: "upstream-a",
          source: "synthetic-gateway",
          label: "tool-a",
          confidence: reverse ? 0.5 : 0.95,
          bbox_xyxy: [0.1, 0.1, 0.3, 0.3],
        },
        {
          detection_id: "second",
          object_id: "upstream-b",
          source: "synthetic-gateway",
          label: "tool-b",
          confidence: reverse ? 0.99 : 0.7,
          bbox_xyxy: [0.6, 0.4, 0.8, 0.7],
        },
      ];
      return route.fulfill({
        json: {
          ...body,
          session_id: "gate06-framing-session",
          source_width: 640,
          source_height: 480,
          observed_at: new Date().toISOString(),
          detections: missing ? [] : reverse ? boxes.reverse() : boxes,
          decisions: [],
          provider_results: [
            { provider: "gateway", status: "ok", latency_ms: 1 },
          ],
          warnings: [],
        },
      });
    },
  );
  await page.goto("/live");
  await page
    .getByRole("button", { name: "Authorize analysis session", exact: true })
    .click();
  for (const [index, camera] of ["camera1", "camera2"].entries()) {
    await page
      .getByRole("button", { name: "Start preview", exact: true })
      .nth(index)
      .click();
    await expect
      .poll(() =>
        page
          .getByLabel(`${camera} preview`, { exact: true })
          .evaluate((v) => (v as HTMLVideoElement).videoWidth),
      )
      .toBeGreaterThan(0);
    await page.getByLabel(`${camera} FPS`, { exact: true }).fill("0.1");
    await page
      .getByLabel(`${camera} framing smoothing`, { exact: true })
      .fill("0");
    await page
      .getByLabel(`${camera} lost timeout`, { exact: true })
      .fill("1000");
    await page.getByLabel(`${camera} send frames`, { exact: true }).check();
    await page
      .getByRole("button", { name: "Analyze now", exact: true })
      .nth(index)
      .click();
    await page
      .getByLabel(`${camera} framing mode`, { exact: true })
      .selectOption("auto");
    await expect
      .poll(() =>
        page
          .getByLabel(`${camera} framed preview`, { exact: true })
          .getAttribute("data-target"),
      )
      .toBe(`${camera}-track-1`);
  }
  reverse = true;
  for (let index = 0; index < 2; index++)
    await page
      .getByRole("button", { name: "Analyze now", exact: true })
      .nth(index)
      .click();
  await expect(
    page.getByLabel("camera1 framed preview", { exact: true }),
  ).toHaveAttribute("data-target", "camera1-track-1");
  await expect(
    page.getByLabel("camera2 framed preview", { exact: true }),
  ).toHaveAttribute("data-target", "camera2-track-1");
  missing = true;
  for (let index = 0; index < 2; index++)
    await page
      .getByRole("button", { name: "Analyze now", exact: true })
      .nth(index)
      .click();
  await expect(
    page.getByLabel("camera1 framed preview", { exact: true }),
  ).toHaveAttribute("data-target", "full-frame");
  await expect(
    page.getByLabel("camera2 framed preview", { exact: true }),
  ).toHaveAttribute("data-target", "full-frame");
});
