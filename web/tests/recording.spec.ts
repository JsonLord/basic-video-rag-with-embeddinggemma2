import { test, expect, Page } from "@playwright/test";
async function previews(page: Page) {
  await page.goto("/live");
  await page.bringToFront();
  for (const i of [0, 1]) {
    await page
      .getByRole("button", { name: "Start preview", exact: true })
      .nth(i)
      .click();
    await expect
      .poll(
        () =>
          page
            .getByLabel(`camera${i + 1} preview`, { exact: true })
            .evaluate((v) => (v as HTMLVideoElement).videoWidth),
        { timeout: 15000 },
      )
      .toBeGreaterThan(0);
  }
}

test("real dual simulated-camera encoding, independent lifecycle, replay/download/delete and explicit import", async ({
  page,
}) => {
  let uploads = 0;
  await page.route("**/api/ingest?*", async (r) => {
    uploads++;
    expect(r.request().headers().authorization).toBe(
      "Bearer local-fixture-token",
    );
    expect(r.request().postDataBuffer()!.length).toBeGreaterThan(100);
    await r.fulfill({
      json: {
        id: "recorded-job",
        video_id: "recorded-video",
        status: "queued",
      },
    });
  });
  await page.route("**/api/jobs", (r) =>
    r.fulfill({
      json: [
        {
          id: "recorded-job",
          video_id: "recorded-video",
          status: "complete",
          stage: "searchable",
        },
      ],
    }),
  );
  await page.addInitScript(() => {
    sessionStorage.setItem("vm-user-token", "local-fixture-token");
    const captured: MediaStreamTrack[] = [],
      created: string[] = [],
      revoked: string[] = [];
    Object.assign(window, {
      recordedTracks: captured,
      createdRecordingUrls: created,
      revokedRecordingUrls: revoked,
    });
    const Original = MediaRecorder;
    Object.defineProperty(window, "MediaRecorder", {
      value: class extends Original {
        constructor(stream: MediaStream, options?: MediaRecorderOptions) {
          super(stream, options);
          captured.push(...stream.getTracks());
        }
      },
    });
    const create = URL.createObjectURL.bind(URL),
      revoke = URL.revokeObjectURL.bind(URL);
    URL.createObjectURL = (blob) => {
      const url = create(blob);
      created.push(url);
      return url;
    };
    URL.revokeObjectURL = (url) => {
      revoked.push(url);
      revoke(url);
    };
  });
  await previews(page);
  await expect(
    page.getByRole("button", { name: "Record camera1", exact: true }),
  ).toBeDisabled();
  for (const slot of ["camera1", "camera2"]) {
    await page.getByLabel(`${slot} recording consent`, { exact: true }).check();
    await page
      .getByRole("button", { name: `Record ${slot}`, exact: true })
      .click();
    await expect(
      page.getByLabel(`${slot} recording state`, { exact: true }),
    ).toContainText("recording");
  }
  await page.waitForTimeout(1200); // Actual codec must emit media, not a mocked recorder.
  await page
    .getByRole("button", { name: "Pause recording camera1", exact: true })
    .click();
  await expect(
    page.getByLabel("camera1 recording state", { exact: true }),
  ).toContainText("paused");
  await expect(
    page.getByLabel("camera2 recording state", { exact: true }),
  ).toContainText("recording");
  await page
    .getByRole("button", { name: "Resume recording camera1", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Stop recording camera1", exact: true })
    .click();
  await expect(
    page.getByLabel("camera1 recording replay", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByLabel("camera2 recording state", { exact: true }),
  ).toContainText("recording");
  await page
    .getByRole("button", { name: "Stop recording camera2", exact: true })
    .click();
  await expect(
    page.getByLabel("camera2 recording replay", { exact: true }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page
        .getByLabel("camera1 recording replay", { exact: true })
        .evaluate((v) => (v as HTMLVideoElement).readyState),
    )
    .toBeGreaterThanOrEqual(1);
  expect(uploads).toBe(0);
  const download = page.waitForEvent("download");
  await page
    .getByRole("link", { name: "Download recording camera1", exact: true })
    .click();
  expect((await download).suggestedFilename()).toMatch(/^camera1-.*\.webm$/);
  await expect(
    page.getByRole("button", {
      name: "Import camera1 to Video RAG",
      exact: true,
    }),
  ).toBeDisabled();
  await page.getByLabel("camera1 import consent", { exact: true }).check();
  await page
    .getByRole("button", { name: "Import camera1 to Video RAG", exact: true })
    .click();
  await expect.poll(() => uploads).toBe(1);
  await expect(
    page.getByLabel("camera1 recording job", { exact: true }),
  ).toContainText("complete", { timeout: 10000 });
  await page
    .getByRole("button", {
      name: "Delete local recording camera2",
      exact: true,
    })
    .click();
  await expect(
    page.getByLabel("camera2 recording replay", { exact: true }),
  ).toHaveCount(0);
  expect(
    await page
      .getByLabel("camera2 preview", { exact: true })
      .evaluate((v) => (v as HTMLVideoElement).srcObject !== null),
  ).toBe(true);
  expect(
    await page.evaluate(() =>
      (
        window as unknown as { recordedTracks: MediaStreamTrack[] }
      ).recordedTracks.every((t) => t.readyState === "ended"),
    ),
  ).toBe(true);
  await page.getByRole("link", { name: "Library", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Live Visual Mentor", exact: true }),
  ).toHaveCount(0);
  expect(
    await page.evaluate(() => {
      const w = window as unknown as {
        createdRecordingUrls: string[];
        revokedRecordingUrls: string[];
      };
      return w.createdRecordingUrls.every((url) =>
        w.revokedRecordingUrls.includes(url),
      );
    }),
  ).toBe(true);
  await page.getByRole("link", { name: "Live", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Live Visual Mentor", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByLabel("camera1 recording replay", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByLabel("camera1 recording state", { exact: true }),
  ).toContainText("idle");
  expect(
    await page
      .getByLabel("camera1 preview", { exact: true })
      .evaluate((v) => (v as HTMLVideoElement).srcObject),
  ).toBeNull();
});

test("device stop finalizes interrupted recording and unsupported codecs fail visibly", async ({
  page,
}) => {
  await previews(page);
  await page.getByLabel("camera1 recording consent", { exact: true }).check();
  await page
    .getByRole("button", { name: "Record camera1", exact: true })
    .click();
  await page.waitForTimeout(600);
  await page
    .getByRole("button", { name: "Stop camera", exact: true })
    .first()
    .click();
  await expect(
    page.getByLabel("camera1 recording review", { exact: true }),
  ).toContainText("Interrupted");
  await expect(
    page.getByLabel("camera1 recording state", { exact: true }),
  ).toContainText("idle");
  await page
    .getByRole("button", {
      name: "Delete local recording camera1",
      exact: true,
    })
    .click();
  await page.evaluate(() =>
    Object.defineProperty(MediaRecorder, "isTypeSupported", {
      value: () => false,
    }),
  );
  await page
    .getByRole("button", { name: "Start preview", exact: true })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Record camera1", exact: true })
    .click();
  await expect(
    page.getByLabel("camera1 recording controls", { exact: true }),
  ).toContainText("No supported WebM or MP4 recording codec");
});

test("synthetic boxes drive stable selection and mirror-safe framing, then recover full frame", async ({
  page,
}) => {
  let detection = true;
  await page.route("**/api/providers", (r) =>
    r.fulfill({
      json: {
        config_version: 1,
        providers: { mock: { destination: "fixture.invalid" } },
        features: {
          "live.camera1.scene": { enabled: true, providers: ["mock"] },
        },
      },
    }),
  );
  await page.route("**/api/live/sessions", (r) =>
    r.fulfill({ json: { session_id: "framing-session", config_version: 1 } }),
  );
  await page.route("**/api/live/sessions/framing-session/frames", async (r) => {
    const body = r.request().postDataJSON();
    await r.fulfill({
      json: {
        ...body,
        session_id: "framing-session",
        source_width: 640,
        source_height: 480,
        observed_at: new Date().toISOString(),
        detections: detection
          ? [
              {
                detection_id: "d",
                label: "tool",
                bbox_xyxy: [0.2, 0.2, 0.4, 0.4],
                confidence: 0.9,
                source: "synthetic",
              },
            ]
          : [],
        decisions: [],
        provider_results: [{ provider: "mock", status: "ok", latency_ms: 1 }],
        warnings: [],
      },
    });
  });
  await previews(page);
  await page
    .getByRole("button", { name: "Authorize analysis session", exact: true })
    .click();
  await page.getByLabel("camera1 FPS", { exact: true }).fill("0.1");
  await page.getByLabel("camera1 send frames", { exact: true }).check();
  await page
    .getByRole("button", { name: "Analyze now", exact: true })
    .first()
    .click();
  await expect(
    page.getByLabel("camera1 tracked object", { exact: true }),
  ).toContainText("camera1-track-1");
  await page
    .getByLabel("camera1 tracked object", { exact: true })
    .selectOption("camera1-track-1");
  const canvas = page.getByLabel("camera1 framed preview", { exact: true });
  await expect
    .poll(() =>
      canvas.evaluate(
        (c) => JSON.parse((c as HTMLElement).dataset.crop!).width,
      ),
    )
    .toBeLessThan(400);
  await page
    .getByRole("button", { name: "Analyze now", exact: true })
    .first()
    .click();
  await expect(
    page.getByLabel("camera1 tracked object", { exact: true }),
  ).toHaveValue("camera1-track-1");
  const mirror = page
    .locator("section")
    .filter({
      has: page.getByRole("heading", { name: "Camera 1", exact: true }),
    })
    .getByRole("checkbox", { name: "Mirror", exact: true });
  await mirror.check();
  await page.getByLabel("camera1 recording consent", { exact: true }).check();
  await page
    .getByLabel("camera1 recording output", { exact: true })
    .selectOption("canvas");
  await page
    .getByRole("button", { name: "Record camera1", exact: true })
    .click();
  await page.waitForTimeout(600);
  await page
    .getByRole("button", { name: "Stop recording camera1", exact: true })
    .click();
  await expect(
    page.getByLabel("camera1 recording review", { exact: true }),
  ).toContainText("Canvas output");
  detection = false;
  await page.waitForTimeout(550);
  await page
    .getByRole("button", { name: "Analyze now", exact: true })
    .first()
    .click();
  await expect(canvas).toHaveAttribute("data-target", "full-frame", {
    timeout: 6000,
  });
  await expect
    .poll(
      () =>
        canvas.evaluate(
          (c) => JSON.parse((c as HTMLElement).dataset.crop!).width,
        ),
      { timeout: 6000 },
    )
    .toBeGreaterThan(620);
});

test("late microphone permission after stop is discarded without recording or upload", async ({
  page,
}) => {
  let uploads = 0;
  await page.route("**/api/ingest?*", (r) => {
    uploads++;
    return r.abort();
  });
  await page.addInitScript(() => {
    const original = navigator.mediaDevices.getUserMedia.bind(
      navigator.mediaDevices,
    );
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
      value: (constraints: MediaStreamConstraints) =>
        constraints.audio
          ? new Promise<MediaStream>((resolve) =>
              Object.assign(window, { resolveRecordingMic: resolve }),
            )
          : original(constraints),
    });
  });
  await previews(page);
  await page.getByLabel("camera1 recording consent", { exact: true }).check();
  await page.getByLabel("camera1 microphone consent", { exact: true }).check();
  await page
    .getByRole("button", { name: "Record camera1", exact: true })
    .click();
  await expect(
    page.getByLabel("camera1 recording state", { exact: true }),
  ).toContainText("starting");
  await page
    .getByRole("button", { name: "Stop recording camera1", exact: true })
    .click();
  await page.evaluate(() => {
    const context = new AudioContext(),
      destination = context.createMediaStreamDestination();
    Object.assign(window, {
      lateRecordingTracks: destination.stream.getTracks(),
      lateRecordingContext: context,
    });
    (
      window as unknown as {
        resolveRecordingMic: (stream: MediaStream) => void;
      }
    ).resolveRecordingMic(destination.stream);
  });
  await expect
    .poll(() =>
      page.evaluate(() =>
        (
          window as unknown as { lateRecordingTracks: MediaStreamTrack[] }
        ).lateRecordingTracks.every((t) => t.readyState === "ended"),
      ),
    )
    .toBe(true);
  await expect(
    page.getByLabel("camera1 recording replay", { exact: true }),
  ).toHaveCount(0);
  expect(uploads).toBe(0);
  await page.evaluate(
    () =>
      void (
        window as unknown as { lateRecordingContext: AudioContext }
      ).lateRecordingContext.close(),
  );
});

test("local quota failure discards oversized recording and preserves camera preview", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const Original = MediaRecorder;
    Object.defineProperty(window, "MediaRecorder", {
      value: class extends Original {
        start(timeslice?: number) {
          super.start(timeslice);
          setTimeout(() => {
            const data = new Blob(["synthetic quota fixture"]);
            Object.defineProperty(data, "size", {
              value: 128 * 1024 * 1024 + 1,
            });
            this.dispatchEvent(new BlobEvent("dataavailable", { data }));
          }, 100);
        }
      },
    });
  });
  await previews(page);
  await page.getByLabel("camera1 recording consent", { exact: true }).check();
  await page
    .getByRole("button", { name: "Record camera1", exact: true })
    .click();
  await expect(
    page.getByLabel("camera1 recording controls", { exact: true }),
  ).toContainText("quota exceeded");
  await expect(
    page.getByLabel("camera1 recording state", { exact: true }),
  ).toContainText("idle");
  await expect(
    page.getByLabel("camera1 recording replay", { exact: true }),
  ).toHaveCount(0);
  expect(
    await page
      .getByLabel("camera1 preview", { exact: true })
      .evaluate((v) => (v as HTMLVideoElement).srcObject !== null),
  ).toBe(true);
});

for (const failure of ["denied", "missing-track"]) {
  test(`microphone ${failure} fails closed without silently claiming audio`, async ({
    page,
  }) => {
    await page.addInitScript((failure) => {
      const original = navigator.mediaDevices.getUserMedia.bind(
        navigator.mediaDevices,
      );
      Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
        value: (constraints: MediaStreamConstraints) => {
          if (!constraints.audio) return original(constraints);
          return failure === "denied"
            ? Promise.reject(
                new DOMException(
                  "Microphone permission denied",
                  "NotAllowedError",
                ),
              )
            : Promise.resolve(new MediaStream());
        },
      });
    }, failure);
    await previews(page);
    await page.getByLabel("camera1 recording consent", { exact: true }).check();
    await page
      .getByLabel("camera1 microphone consent", { exact: true })
      .check();
    await page
      .getByRole("button", { name: "Record camera1", exact: true })
      .click();
    await expect(
      page.getByLabel("camera1 recording controls", { exact: true }),
    ).toContainText(
      failure === "denied"
        ? "Microphone permission denied"
        : "No live microphone track",
    );
    await expect(
      page.getByLabel("camera1 recording state", { exact: true }),
    ).toContainText("idle");
    await expect(
      page.getByLabel("camera1 recording replay", { exact: true }),
    ).toHaveCount(0);
    expect(
      await page
        .getByLabel("camera1 preview", { exact: true })
        .evaluate(
          (v) =>
            (
              (v as HTMLVideoElement).srcObject as MediaStream
            ).getVideoTracks()[0].readyState,
        ),
    ).toBe("live");
  });
}
