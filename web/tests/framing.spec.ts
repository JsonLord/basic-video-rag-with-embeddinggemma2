import { test, expect } from "@playwright/test";
import { AssociationTracker, Box, SpatialDetection } from "../src/lib/tracking";
import {
  cropForBox,
  projectBox,
  smoothCrop,
  fullFrame,
} from "../src/lib/framing";
const detection = (
  box: Box = [0.2, 0.2, 0.5, 0.6],
  source = "fixture",
): SpatialDetection => ({
  detection_id: "d",
  source,
  label: "tool",
  confidence: 0.9,
  bbox_xyxy: box,
});

test("stable association, lost/reacquired state, expiry and monotonic frame time", () => {
  const tracker = new AssociationTracker("camera1");
  const first = tracker.update([detection()], 100)[0];
  expect(tracker.update([detection([0.22, 0.2, 0.52, 0.6])], 200)[0].id).toBe(
    first.id,
  );
  expect(tracker.update([], 300)[0].state).toBe("missing");
  expect(tracker.update([detection([0.23, 0.2, 0.53, 0.6])], 500)[0].id).toBe(
    first.id,
  );
  expect(tracker.update([detection([0.7, 0.7, 0.8, 0.8])], 400)[0].id).toBe(
    first.id,
  );
  expect(tracker.snapshot(2600)).toHaveLength(0);
  expect(tracker.update([detection()], 2700)[0].id).not.toBe(first.id);
  tracker.reset();
  expect(tracker.update([detection()], 2800)[0].id).not.toBe(first.id);
});
test("tracks never associate across source, camera or incompatible upstream IDs", () => {
  const a = new AssociationTracker("camera1"),
    b = new AssociationTracker("camera2");
  const t = a.update([{ ...detection(), object_id: "upstream-a" }], 100)[0];
  const next = a.update(
    [
      { ...detection(), object_id: "upstream-b" },
      detection(undefined, "other-provider"),
    ],
    200,
  );
  expect(
    next.filter((n) => n.state === "tracked").every((n) => n.id !== t.id),
  ).toBe(true);
  expect(b.update([detection()], 100)[0].id).not.toBe(t.id);
  expect(
    a
      .update([detection([0, 0, 2, 1])], 300)
      .filter((t) => t.state === "tracked"),
  ).toHaveLength(0);
});
for (const box of [
  [0, 0, 0.1, 0.1],
  [0.85, 0.8, 1, 1],
  [0.1, 0.2, 0.9, 0.8],
  [0.3, 0.3, 0.4, 0.4],
] as Box[]) {
  test(`bounded aspect-correct crop ${box}`, () => {
    const c = cropForBox(box, 1920, 1080, 0.2, 0.25);
    expect(c.width / c.height).toBeCloseTo(1920 / 1080, 10);
    expect(c.x).toBeGreaterThanOrEqual(0);
    expect(c.y).toBeGreaterThanOrEqual(0);
    expect(c.x + c.width).toBeLessThanOrEqual(1920);
    expect(c.y + c.height).toBeLessThanOrEqual(1080);
    expect(c.width).toBeGreaterThanOrEqual(1920 * 0.25);
    expect(c.x).toBeLessThanOrEqual(box[0] * 1920);
    expect(c.x + c.width).toBeGreaterThanOrEqual(box[2] * 1920);
  });
}
test("full-frame loss, smoothing independent of update frequency, contain/cover and mirror", () => {
  expect(cropForBox(null, 640, 480)).toEqual(fullFrame(640, 480));
  const start = fullFrame(640, 480),
    target = cropForBox([0.2, 0.2, 0.4, 0.4], 640, 480);
  const once = smoothCrop(start, target, 32, 250),
    twice = smoothCrop(smoothCrop(start, target, 16, 250), target, 16, 250);
  expect(once.x).toBeCloseTo(twice.x, 10);
  expect(once.width / once.height).toBeCloseTo(4 / 3, 10);
  const contain = projectBox(
    [0.2, 0.1, 0.6, 0.8],
    640,
    480,
    100,
    100,
    "contain",
  );
  const mirrored = projectBox(
    [0.2, 0.1, 0.6, 0.8],
    640,
    480,
    100,
    100,
    "contain",
    true,
  );
  expect(contain.x).toBeCloseTo(20);
  expect(contain.y).toBeCloseTo(20);
  expect(mirrored.x).toBeCloseTo(40);
  const cover = projectBox([0.2, 0.1, 0.6, 0.8], 640, 480, 100, 100, "cover");
  expect(cover.width).toBeCloseTo(53.333333, 4);
});
