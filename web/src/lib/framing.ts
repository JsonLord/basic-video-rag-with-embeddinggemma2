import { Box, validBox } from "./tracking";
export type Crop = { x: number; y: number; width: number; height: number };
const clamp = (n: number, lo: number, hi: number) =>
  Math.min(hi, Math.max(lo, n));
export function fullFrame(width: number, height: number): Crop {
  return { x: 0, y: 0, width, height };
}
/** Pixel-space source crop. Mirror is a presentation transform, never a box rewrite. */
export function cropForBox(
  box: Box | null,
  width: number,
  height: number,
  margin = 0.25,
  minScale = 0.25,
): Crop {
  if (!(width > 0 && height > 0) || !Number.isFinite(width + height))
    throw new Error("Invalid source dimensions");
  if (!box || !validBox(box)) return fullFrame(width, height);
  const aspect = width / height;
  const m = clamp(margin, 0, 1),
    min = clamp(minScale, 0.1, 1);
  let w = Math.max((box[2] - box[0]) * width * (1 + 2 * m), min * width);
  let h = Math.max((box[3] - box[1]) * height * (1 + 2 * m), min * height);
  w = Math.max(w, h * aspect);
  h = w / aspect;
  if (w >= width || h >= height) return fullFrame(width, height);
  return {
    x: clamp(((box[0] + box[2]) * width) / 2 - w / 2, 0, width - w),
    y: clamp(((box[1] + box[3]) * height) / 2 - h / 2, 0, height - h),
    width: w,
    height: h,
  };
}
export function smoothCrop(
  previous: Crop,
  target: Crop,
  dt: number,
  smoothingMs: number,
): Crop {
  const alpha =
    smoothingMs <= 0 ? 1 : 1 - Math.exp(-clamp(dt, 0, 1000) / smoothingMs);
  return {
    x: previous.x + (target.x - previous.x) * alpha,
    y: previous.y + (target.y - previous.y) * alpha,
    width: previous.width + (target.width - previous.width) * alpha,
    height: previous.height + (target.height - previous.height) * alpha,
  };
}
/** Projection for contain/cover overlays and mirrored previews; source boxes stay canonical. */
export function projectBox(
  box: Box,
  sourceWidth: number,
  sourceHeight: number,
  viewWidth: number,
  viewHeight: number,
  fit: "contain" | "cover",
  mirror = false,
): Crop {
  const scale = (fit === "contain" ? Math.min : Math.max)(
    viewWidth / sourceWidth,
    viewHeight / sourceHeight,
  );
  const w = (box[2] - box[0]) * sourceWidth * scale,
    h = (box[3] - box[1]) * sourceHeight * scale;
  const x =
    (viewWidth - sourceWidth * scale) / 2 + box[0] * sourceWidth * scale;
  return {
    x: mirror ? viewWidth - x - w : x,
    y: (viewHeight - sourceHeight * scale) / 2 + box[1] * sourceHeight * scale,
    width: w,
    height: h,
  };
}
