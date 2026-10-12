import type { View } from "./api";

// Color follows the view (entity), in fixed categorical slot order - never re-assigned by rank or filter.
export const VIEW_ORDER: View[] = ["text", "frame", "video", "audio", "fused", "hybrid"];

export const VIEW_INFO: Record<View, { label: string; color: string; blurb: string }> = {
  text: { label: "Text", color: "var(--series-1)", blurb: "Transcript only" },
  frame: { label: "Frame", color: "var(--series-2)", blurb: "One keyframe image" },
  video: { label: "Video", color: "var(--series-3)", blurb: "Frames at 1fps, no audio" },
  audio: { label: "Audio", color: "var(--series-4)", blurb: "Raw 16kHz audio, no transcript" },
  fused: { label: "Fused", color: "var(--series-5)", blurb: "Transcript + video + audio in one vector" },
  hybrid: { label: "Hybrid", color: "var(--series-6)", blurb: "RRF of text, video & audio rankings" },
};

// Raw hexes for SVG/recharts (CSS vars don't resolve in some SVG attribute paths).
export const VIEW_HEX: Record<View, string> = {
  text: "#3987e5",
  frame: "#d95926",
  video: "#199e70",
  audio: "#c98500",
  fused: "#d55181",
  hybrid: "#008300",
};
