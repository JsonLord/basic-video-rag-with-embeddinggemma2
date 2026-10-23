import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

test("durable streaming tools and A2A research preserve two camera previews and reconnect", async ({
  page,
}) => {
  test.skip(
    !process.env.VM_RECORDING_FULLSTACK,
    "Requires the isolated local v3 fixture with synthetic OpenAI/A2A.",
  );
  test.setTimeout(90000);
  const credential = "v3-synthetic-fixture-user-token-000000";
  expect(
    (
      await page.request.post("/api/access", {
        headers: { Authorization: `Bearer ${credential}` },
      })
    ).ok(),
  ).toBe(true);
  const upload = await page.request.post(
    "/api/ingest?filename=conversation-synthetic-fixture",
    {
      headers: {
        Authorization: `Bearer ${credential}`,
        "Content-Type": "video/mp4",
      },
      data: readFileSync("public/sample/video.mp4"),
    },
  );
  expect(upload.ok()).toBe(true);
  const job = await upload.json();
  let suppliedTranscript = false;
  await expect
    .poll(
      async () => {
        const response = await page.request.get("/api/jobs", {
          headers: { Authorization: `Bearer ${credential}` },
        });
        const state = (
          (await response.json()) as {
            id: string;
            status: string;
            error?: string;
          }[]
        ).find((item) => item.id === job.id);
        if (
          state?.status === "blocked" &&
          state.error === "transcript_required_video_has_no_audio" &&
          !suppliedTranscript
        ) {
          suppliedTranscript = true;
          const retry = await page.request.post(`/api/jobs/${job.id}`, {
            headers: { Authorization: `Bearer ${credential}` },
            data: {
              action: "retry",
              transcript:
                "Clear the workbench and check equipment before assembly.",
            },
          });
          expect(retry.ok()).toBe(true);
        }
        return state?.status;
      },
      { timeout: 60000 },
    )
    .toBe("complete");
  await page.addInitScript(
    (key) => sessionStorage.setItem("vm-user-token", key),
    credential,
  );
  const created = await page.request.post("/api/mentor/conversations", {
    headers: { Authorization: `Bearer ${credential}` },
    data: { title: "Browser research qualification" },
  });
  expect(created.ok()).toBe(true);
  const conversationId = (await created.json()).id;
  await page.goto("/live");
  await expect(page.getByLabel("Conversation history")).toHaveValue(
    conversationId,
  );
  for (const camera of ["camera1", "camera2"]) {
    await page
      .getByRole("button", { name: "Start preview", exact: true })
      .nth(camera === "camera1" ? 0 : 1)
      .click();
    await expect
      .poll(() =>
        page
          .getByLabel(`${camera} preview`, { exact: true })
          .evaluate((v) => (v as HTMLVideoElement).videoWidth),
      )
      .toBeGreaterThan(0);
  }
  await page
    .getByRole("button", { name: "Authorize analysis session" })
    .click();
  await page
    .getByRole("button", { name: "Push to talk (send up to 15 seconds)" })
    .click();
  await page.waitForTimeout(1000); // Real bounded microphone capture from a simulated device.
  await page.getByRole("button", { name: "Stop and send audio" }).click();
  await page
    .getByRole("button", { name: "Use speech transcript in message" })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Message to Mentor" }),
  ).toHaveValue(/Synthetic recording evidence/);
  const previewIds = await page
    .locator("video")
    .evaluateAll((vs) =>
      vs.map(
        (v) => ((v as HTMLVideoElement).srcObject as MediaStream | null)?.id,
      ),
    );
  await page
    .getByRole("textbox", { name: "Message to Mentor" })
    .fill("Find workbench evidence and research assembly safety.");
  await page.getByLabel("Allow the approved research agent").check();
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(page.getByLabel("Conversation transcript")).toContainText(
    "Research is running independently",
    { timeout: 15000 },
  );
  await expect(page.getByLabel("Research jobs")).toContainText("completed", {
    timeout: 15000,
  });
  await expect(
    page.getByRole("link", { name: "Safety guide", exact: true }),
  ).toHaveAttribute("href", "https://docs.example/safety");
  expect(
    await page
      .locator("video")
      .evaluateAll((vs) =>
        vs.map(
          (v) => ((v as HTMLVideoElement).srcObject as MediaStream | null)?.id,
        ),
      ),
  ).toEqual(previewIds);
  expect(
    await page
      .locator("video")
      .evaluateAll((vs) =>
        vs.every((v) =>
          ((v as HTMLVideoElement).srcObject as MediaStream | null)
            ?.getVideoTracks()
            .every((t) => t.readyState === "live"),
        ),
      ),
  ).toBe(true);
  await page
    .getByRole("button", { name: "Incorporate completed research" })
    .click();
  await expect(page.getByLabel("Conversation transcript")).toContainText(
    "Updated from completed research",
    { timeout: 15000 },
  );
  await page
    .getByText("Tool execution and provenance", { exact: true })
    .first()
    .click();
  await expect(page.getByLabel("Conversation transcript")).toContainText(
    "retrieve_video_evidence",
  );
  // The shared fixture library can contain other indexed recordings with tied
  // synthetic embeddings. Verify the actual retrieved citation and its playback.
  const citation = page
    .getByLabel("Conversation transcript")
    .getByRole("button", { name: / · [0-9.]+s$/ })
    .first();
  await expect(citation).toBeVisible();
  await citation.click();
  await expect
    .poll(() =>
      page
        .locator(".fixed video")
        .evaluate((v) => (v as HTMLVideoElement).readyState),
    )
    .toBeGreaterThanOrEqual(1);
  await page.getByRole("button", { name: "Close", exact: true }).click();
  const selected = await page.getByLabel("Conversation history").inputValue();
  await page.reload();
  await expect(page.getByLabel("Conversation history")).toHaveValue(selected);
  await expect(page.getByLabel("Conversation transcript")).toContainText(
    "Updated from completed research",
    { timeout: 15000 },
  );
  await expect(page.getByLabel("Research jobs")).toContainText("completed");
  await page.getByRole("button", { name: "Delete conversation" }).click();
  await expect(page.getByLabel("Conversation history")).toHaveValue("");
});
