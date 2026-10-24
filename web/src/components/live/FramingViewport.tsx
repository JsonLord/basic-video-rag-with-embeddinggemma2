"use client";
import { RefObject, useEffect, useRef, useState } from "react";
import { Tracker, Track } from "@/lib/tracking";
import { cropForBox, fullFrame, smoothCrop } from "@/lib/framing";

export function FramingViewport({
  slot,
  video,
  canvas,
  tracker,
  active,
  mirror,
  locked,
}: {
  slot: string;
  video: RefObject<HTMLVideoElement | null>;
  canvas: RefObject<HTMLCanvasElement | null>;
  tracker: Tracker;
  active: boolean;
  mirror: boolean;
  locked: boolean;
}) {
  const [mode, setMode] = useState("off"),
    [target, setTarget] = useState("");
  const [margin, setMargin] = useState(0.25),
    [smoothing, setSmoothing] = useState(250);
  const [minimum, setMinimum] = useState(0.25),
    [lostTimeout, setLostTimeout] = useState(2000);
  const [annotations, setAnnotations] = useState(false),
    [tracks, setTracks] = useState<Track[]>([]);
  const chosen = useRef("");
  useEffect(() => {
    let frame = 0,
      last = performance.now(),
      crop = fullFrame(640, 480),
      dimensions = "";
    const draw = (now: number) => {
      const v = video.current,
        c = canvas.current;
      if (active && v?.videoWidth && c) {
        const current = tracker.snapshot(now, lostTimeout);
        if (mode === "auto" && !chosen.current && current.length) {
          chosen.current = [...current].sort(
            (a, b) => b.confidence - a.confidence,
          )[0].id;
          setTarget(chosen.current);
        }
        const tracked = current.find((t) => t.id === chosen.current);
        const desired = cropForBox(
          mode !== "off" && tracked ? tracked.box : null,
          v.videoWidth,
          v.videoHeight,
          margin,
          minimum,
        );
        const nextDimensions = `${v.videoWidth}x${v.videoHeight}`;
        if (dimensions !== nextDimensions) {
          dimensions = nextDimensions;
          crop = fullFrame(v.videoWidth, v.videoHeight);
        }
        crop = smoothCrop(crop, desired, now - last, smoothing);
        last = now;
        const w = Math.min(v.videoWidth, 640),
          h = Math.round((w * v.videoHeight) / v.videoWidth);
        if (c.width !== w || c.height !== h) {
          c.width = w;
          c.height = h;
        }
        const ctx = c.getContext("2d");
        if (ctx) {
          ctx.save();
          if (mirror) {
            ctx.translate(w, 0);
            ctx.scale(-1, 1);
          }
          ctx.drawImage(v, crop.x, crop.y, crop.width, crop.height, 0, 0, w, h);
          ctx.restore();
          if (annotations)
            for (const t of current) {
              const x = ((t.box[0] * v.videoWidth - crop.x) / crop.width) * w;
              const y = ((t.box[1] * v.videoHeight - crop.y) / crop.height) * h;
              const bw =
                  (((t.box[2] - t.box[0]) * v.videoWidth) / crop.width) * w,
                bh =
                  (((t.box[3] - t.box[1]) * v.videoHeight) / crop.height) * h;
              ctx.strokeStyle = t.id === chosen.current ? "#fbbf24" : "#4ade80";
              ctx.lineWidth = 2;
              ctx.strokeRect(mirror ? w - x - bw : x, y, bw, bh);
              ctx.fillStyle = ctx.strokeStyle;
              ctx.font = "12px sans-serif";
              ctx.fillText(
                `${t.label} · ${t.id}`,
                mirror ? w - x - bw : x,
                Math.max(14, y - 3),
              );
            }
        }
        c.dataset.crop = JSON.stringify(crop);
        c.dataset.target = tracked?.id ?? "full-frame";
      } else if (c) {
        c.getContext("2d")?.clearRect(0, 0, c.width, c.height);
        c.dataset.target = "full-frame";
      }
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    const timer = setInterval(
      () =>
        setTracks(
          active ? tracker.snapshot(performance.now(), lostTimeout) : [],
        ),
      200,
    );
    return () => {
      cancelAnimationFrame(frame);
      clearInterval(timer);
    };
  }, [
    active,
    annotations,
    canvas,
    lostTimeout,
    margin,
    minimum,
    mirror,
    mode,
    smoothing,
    tracker,
    video,
  ]);
  const select = (id: string) => {
    chosen.current = id;
    setTarget(id);
  };
  const field = "rounded border border-line bg-page px-2 py-1 text-sm";
  return (
    <div className="mt-4 border-t border-line pt-3">
      <h3 className="font-medium">Virtual framing · {slot}</h3>
      <p className="text-xs text-muted">
        Browser association of spatial detections; no motion prediction between
        detections. Lost targets return to full frame after {lostTimeout / 1000}{" "}
        seconds. Original source is preserved.
      </p>
      <div className="my-2 flex flex-wrap items-center gap-2">
        <select
          className={field}
          aria-label={`${slot} framing mode`}
          value={mode}
          disabled={locked}
          onChange={(e) => {
            setMode(e.target.value);
            select("");
          }}
        >
          <option value="off">Full frame</option>
          <option value="manual">Follow selected object</option>
          <option value="auto">Auto-select highest confidence once</option>
        </select>
        <select
          className={field}
          aria-label={`${slot} tracked object`}
          value={target}
          disabled={locked}
          onChange={(e) => {
            setMode("manual");
            select(e.target.value);
          }}
        >
          <option value="">No selected object</option>
          {target && !tracks.some((t) => t.id === target) && (
            <option value={target}>Lost target — full frame recovery</option>
          )}
          {tracks.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label} · {t.id} · {t.source} · {t.state}
            </option>
          ))}
        </select>
        <label className="text-xs">
          Margin{" "}
          <input
            aria-label={`${slot} framing margin`}
            type="number"
            min={0}
            max={1}
            step={0.1}
            value={margin}
            disabled={locked}
            onChange={(e) =>
              setMargin(Math.min(1, Math.max(0, +e.target.value || 0)))
            }
            className={`${field} w-20`}
          />
        </label>
        <label className="text-xs">
          Smoothing ms{" "}
          <input
            aria-label={`${slot} framing smoothing`}
            type="number"
            min={0}
            max={2000}
            step={50}
            value={smoothing}
            disabled={locked}
            onChange={(e) =>
              setSmoothing(Math.min(2000, Math.max(0, +e.target.value || 0)))
            }
            className={`${field} w-24`}
          />
        </label>
        <label className="text-xs">
          Minimum crop %{" "}
          <input
            aria-label={`${slot} minimum crop`}
            type="number"
            min={10}
            max={100}
            step={5}
            value={minimum * 100}
            disabled={locked}
            onChange={(e) =>
              setMinimum(
                Math.min(100, Math.max(10, +e.target.value || 10)) / 100,
              )
            }
            className={`${field} w-20`}
          />
        </label>
        <label className="text-xs">
          Lost timeout ms{" "}
          <input
            aria-label={`${slot} lost timeout`}
            type="number"
            min={250}
            max={10000}
            step={250}
            value={lostTimeout}
            disabled={locked}
            onChange={(e) =>
              setLostTimeout(
                Math.min(10000, Math.max(250, +e.target.value || 250)),
              )
            }
            className={`${field} w-24`}
          />
        </label>
        <label className="text-xs">
          <input
            aria-label={`${slot} canvas overlays`}
            type="checkbox"
            checked={annotations}
            disabled={locked}
            onChange={(e) => setAnnotations(e.target.checked)}
          />{" "}
          Render annotations into canvas output
        </label>
        <button
          className={field}
          disabled={locked}
          onClick={() => {
            setMode("off");
            select("");
          }}
        >
          Reset framing
        </button>
        <button
          className={field}
          disabled={!active}
          onClick={() =>
            void canvas.current?.requestFullscreen().catch(() => {})
          }
        >
          Fullscreen framed view
        </button>
      </div>
      <canvas
        ref={canvas}
        aria-label={`${slot} framed preview`}
        className="w-full rounded-lg bg-black"
        width={640}
        height={480}
      />
      <p className="text-xs text-muted">
        Canvas output: framing, mirror and optional annotations exactly as
        shown. This is separate from the original camera stream.
      </p>
    </div>
  );
}
