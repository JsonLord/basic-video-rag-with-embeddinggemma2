import { test, expect } from "@playwright/test";
import { parse, stringify } from "yaml";

test("HF defaults, explicit migration, provider/profile switching, validation and CAS apply", async ({
  page,
}) => {
  const legacy = {
    version: 1,
    profile: "historical-v1",
    providers: {},
    features: {},
  };
  const qwen = {
    adapter: "openai-conversation",
    model: "qwen-fixture",
    model_env: "OPENAI_COMPATIBLE_MODEL",
    base_url_env: "OPENAI_COMPATIBLE_URL",
    api_key_secret: "OPENAI_COMPATIBLE_API_KEY",
    capability_version: 1,
    capabilities: ["conversation", "reasoning"],
    trust: "public_only",
  };
  const v2 = {
    ...legacy,
    version: 2,
    profile: "HF draft",
    migrated_from: 1,
    providers: { qwen },
    features: {
      "mentor.conversation": { providers: ["qwen"], enabled: false },
    },
  };
  const nvidia = {
    version: 2,
    profile: "NVIDIA Precision",
    providers: {
      detector: {
        adapter: "detection-http",
        model: "fixture-detector",
        base_url_env: "DETECTOR_URL",
        capabilities: ["object_detection", "bounding_boxes"],
        capability_version: 1,
        trust: "approved_sensitive",
      },
    },
    features: {
      "live.camera1.detection": { providers: ["detector"], enabled: false },
    },
  };
  let applied = 0,
    revision = 7,
    current: typeof legacy | typeof v2 | typeof nvidia = legacy;
  await page.route("**/api/config", (r) =>
    r.fulfill({
      json: {
        config_version: revision,
        history_revision: revision,
        schema_version: current.version,
        config: current,
        yaml: stringify(current),
        history: [1, 7],
        writable: true,
        environment_defaults: {
          status: "configured",
          live_status: "not_checked",
          providers: {
            "hf-conversation": {
              destination: "models.example",
              model: "qwen-fixture",
              credential_present: true,
              capability_version: 1,
              trust: "public_only",
            },
          },
        },
      },
    }),
  );
  await page.route("**/api/config/profiles", (r) =>
    r.fulfill({
      json: {
        "NVIDIA Precision": stringify(nvidia),
        "Laya Fast": stringify({ ...nvidia, profile: "Laya Fast" }),
      },
    }),
  );
  await page.route("**/api/config/migrate", (r) => {
    expect(parse(r.request().postDataJSON().yaml).version).toBe(1);
    expect(r.request().postDataJSON().include_environment_defaults).toBe(true);
    return r.fulfill({
      json: { yaml: stringify(v2), schema_version: 2, persisted: false },
    });
  });
  await page.route("**/api/config/validate", (r) =>
    r.fulfill({
      json: {
        valid: true,
        changed_sections: ["version", "providers", "features"],
      },
    }),
  );
  await page.route("**/api/config/apply", (r) => {
    const body = r.request().postDataJSON();
    expect(body.expected_version).toBe(7);
    expect(parse(body.yaml).version).toBe(2);
    current = parse(body.yaml);
    applied++;
    revision++;
    return r.fulfill({ json: { config_version: revision, schema_version: 2 } });
  });
  await page.goto("/models");
  await page
    .getByRole("button", { name: "Load current config", exact: true })
    .click();
  await expect(
    page.getByText(/historical-v1 · schema 1 · history revision 7/),
  ).toBeVisible();
  const defaults = page.getByLabel("Hugging Face runtime defaults", {
    exact: true,
  });
  await expect(defaults).toContainText("models.example");
  await expect(defaults).toContainText("credential available: true");
  await expect(defaults).toContainText("not_checked");
  await page
    .getByRole("button", { name: "Use HF defaults in draft", exact: true })
    .click();
  await expect
    .poll(
      async () =>
        parse(await page.getByLabel("Routing YAML").inputValue()).version,
    )
    .toBe(2);
  await expect(page.getByLabel("Provider cards")).toContainText(
    "OPENAI_COMPATIBLE_API_KEY",
  );
  expect(applied).toBe(0);
  await page.getByText("Route builder", { exact: true }).click();
  for (const role of [
    "mentor.conversation",
    "live.camera1.detection",
    "live.camera2.decisions",
    "research.dispatch",
  ])
    await expect(
      page.locator(`#feature-roles option[value="${role}"]`),
    ).toHaveCount(1);
  await page
    .getByLabel("Example profile", { exact: true })
    .selectOption("NVIDIA Precision");
  await expect(page.getByLabel("Provider cards")).toContainText(
    "fixture-detector",
  );
  await page
    .getByRole("button", { name: "Validate & preview diff", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Apply profile atomically", exact: true })
    .click();
  expect(applied).toBe(1);
  await page
    .getByRole("button", { name: "Load current config", exact: true })
    .click();
  await expect(
    page.getByText(/NVIDIA Precision · schema 2 · history revision 8/),
  ).toBeVisible();
});

test("invalid environment settings remain explicit configuration errors, never successful health", async ({
  page,
}) => {
  const config = {
    version: 1,
    profile: "unconfigured",
    providers: {},
    features: {},
  };
  await page.route("**/api/config", (r) =>
    r.fulfill({
      json: {
        config_version: 1,
        config,
        yaml: stringify(config),
        history: [1],
        writable: true,
        environment_defaults: {
          status: "configuration_error",
          error: "environment_configuration_invalid",
          providers: {},
          live_status: "not_checked",
        },
      },
    }),
  );
  await page.route("**/api/config/profiles", (r) => r.fulfill({ json: {} }));
  await page.goto("/models");
  await page
    .getByRole("button", { name: "Load current config", exact: true })
    .click();
  await expect(page.getByLabel("Hugging Face runtime defaults")).toContainText(
    "environment_configuration_invalid",
  );
  await expect(page.getByLabel("Hugging Face runtime defaults")).toContainText(
    "not_checked",
  );
});
