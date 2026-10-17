import { test, expect } from "@playwright/test";
import { stringify } from "yaml";
const config = {
  version: 1,
  profile: "Hybrid review fixture",
  providers: {
    laya: {
      label: "Laya visual decisions",
      adapter: "laya-vision",
      model: "thaitea/laya-vision",
      base_url_env: "LAYA_BASE_URL",
      api_key_secret: "LAYA_API_KEY",
      trust: "approved_sensitive",
      capabilities: ["image_understanding", "visual_decision"],
    },
    nvidia: {
      label: "NVIDIA detection gateway",
      adapter: "detection-http",
      model: "configured-detector",
      base_url_env: "NVIDIA_DETECTION_BASE_URL",
      trust: "approved_sensitive",
      capabilities: ["object_detection", "bounding_boxes"],
    },
  },
  features: {
    "live.camera1.scene": {
      strategy: "parallel",
      providers: ["laya", "nvidia"],
      enabled: true,
      result_policy: "all",
      fusion: "spatial_semantic",
    },
  },
};
async function studio(page: import("@playwright/test").Page) {
  await page.route("**/api/config", (r) =>
    r.fulfill({
      json: {
        config_version: 1,
        yaml: stringify(config),
        config,
        history: [1],
        writable: true,
      },
    }),
  );
  await page.route("**/api/config/profiles", (r) =>
    r.fulfill({ json: { "Hybrid parallel": stringify(config) } }),
  );
  await page.goto("/models");
  await page.getByRole("button", { name: "Load current config" }).click();
  await expect(
    page.getByText("Laya visual decisions", { exact: true }),
  ).toBeVisible();
}
for (const size of [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "mobile", width: 390, height: 844 },
])
  test(`native Live and Models ${size.name}`, async ({ page }) => {
    await page.setViewportSize(size);
    await studio(page);
    await expect(page).toHaveScreenshot(`models-${size.name}.png`, {
      fullPage: true,
    });
    await page.goto("/live");
    await expect(
      page.getByRole("heading", { name: "Live Visual Mentor" }),
    ).toBeVisible();
    await expect(page).toHaveScreenshot(`live-${size.name}.png`, {
      fullPage: true,
    });
  });
test("import edits draft, validate gates apply, route form updates YAML", async ({
  page,
}) => {
  let applied = 0;
  await studio(page);
  await page.route("**/api/config/validate", (r) =>
    r.fulfill({ json: { valid: true, changed_sections: ["profile"] } }),
  );
  await page.route("**/api/config/apply", (r) => {
    applied++;
    return r.fulfill({ json: { config_version: 2 } });
  });
  await page
    .getByLabel("Import YAML", { exact: true })
    .setInputFiles({
      name: "profile.yml",
      mimeType: "application/yaml",
      buffer: Buffer.from(stringify({ ...config, profile: "Imported draft" })),
    });
  await expect(page.getByLabel("Routing YAML")).toContainText("Imported draft");
  expect(applied).toBe(0);
  await expect(
    page.getByRole("button", { name: "Apply profile atomically" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Validate & preview diff" }).click();
  await expect(
    page.getByRole("button", { name: "Apply profile atomically" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Apply profile atomically" }).click();
  expect(applied).toBe(1);
  await page.getByText("Route builder", { exact: true }).click();
  await page.getByLabel("Route strategy").selectOption("fallback");
  await page.getByRole("checkbox", { name: "laya", exact: true }).check();
  await page.getByRole("button", { name: "Update route draft" }).click();
  await expect(
    page.getByRole("button", { name: "Apply profile atomically" }),
  ).toBeDisabled();
});
