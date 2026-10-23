/** Browser association of verified spatial boxes. No inference or cross-camera fusion. */
export type Box = [number, number, number, number];
export type SpatialDetection = {
  detection_id: string;
  source: string;
  label: string;
  bbox_xyxy: Box;
  confidence: number;
  object_id?: string;
};
export type Track = {
  id: string;
  source: string;
  label: string;
  box: Box;
  confidence: number;
  lastSeen: number;
  objectId?: string;
  state: "tracked" | "missing";
};
export interface Tracker {
  update(detections: SpatialDetection[], capturedAt: number): Track[];
  snapshot(now: number, maxAgeMs?: number): Track[];
  reset(): void;
}
export function validBox(b: Box): boolean {
  return (
    b.length === 4 &&
    b.every((n) => Number.isFinite(n) && n >= 0 && n <= 1) &&
    b[0] < b[2] &&
    b[1] < b[3]
  );
}
export function iou(a: Box, b: Box): number {
  const overlap =
    Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])) *
    Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  return (
    overlap /
    ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - overlap)
  );
}
export class AssociationTracker implements Tracker {
  private tracks: Track[] = [];
  private counter = 0;
  private timestamp = -1;
  constructor(
    private camera: string,
    private ttl = 2000,
    private threshold = 0.2,
  ) {}
  reset() {
    this.tracks = [];
    this.timestamp = -1; /* IDs never recycle within this camera instance. */
  }
  snapshot(now: number, maxAgeMs = this.ttl): Track[] {
    return this.tracks
      .filter((t) => now - t.lastSeen <= Math.min(this.ttl, maxAgeMs))
      .map((t) => ({ ...t, box: [...t.box] as Box }));
  }
  update(input: SpatialDetection[], capturedAt: number): Track[] {
    if (!Number.isFinite(capturedAt) || capturedAt <= this.timestamp)
      return this.snapshot(this.timestamp);
    this.timestamp = capturedAt;
    const detections = input
      .slice(0, 64)
      .filter(
        (d) =>
          validBox(d.bbox_xyxy) &&
          Number.isFinite(d.confidence) &&
          d.confidence >= 0 &&
          d.confidence <= 1,
      );
    this.tracks = this.tracks
      .filter((t) => capturedAt - t.lastSeen <= this.ttl)
      .map((t) => ({ ...t, state: "missing" }));
    const pairs: { t: number; d: number; score: number }[] = [];
    this.tracks.forEach((t, ti) =>
      detections.forEach((d, di) => {
        if (t.source !== d.source || t.label !== d.label) return;
        if (t.objectId && d.object_id && t.objectId !== d.object_id) return;
        const score =
          t.objectId && t.objectId === d.object_id
            ? 2
            : iou(t.box, d.bbox_xyxy);
        if (score >= this.threshold) pairs.push({ t: ti, d: di, score });
      }),
    );
    pairs.sort((a, b) => b.score - a.score || a.t - b.t || a.d - b.d);
    const usedTracks = new Set<number>(),
      usedDetections = new Set<number>();
    for (const pair of pairs) {
      if (usedTracks.has(pair.t) || usedDetections.has(pair.d)) continue;
      const d = detections[pair.d],
        previous = this.tracks[pair.t];
      this.tracks[pair.t] = {
        ...previous,
        box: [...d.bbox_xyxy],
        confidence: d.confidence,
        objectId: d.object_id,
        lastSeen: capturedAt,
        state: "tracked",
      };
      usedTracks.add(pair.t);
      usedDetections.add(pair.d);
    }
    detections.forEach((d, i) => {
      if (!usedDetections.has(i) && this.tracks.length < 128)
        this.tracks.push({
          id: `${this.camera}-track-${++this.counter}`,
          source: d.source,
          label: d.label,
          box: [...d.bbox_xyxy],
          confidence: d.confidence,
          objectId: d.object_id,
          lastSeen: capturedAt,
          state: "tracked",
        });
    });
    return this.snapshot(capturedAt);
  }
}
