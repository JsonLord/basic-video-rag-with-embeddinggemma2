// Types + fetch helpers for the FastAPI backend (proxied at /api and /media by next.config.ts).

export type View = "text" | "frame" | "video" | "audio" | "fused" | "hybrid";
export const DIMS = [768, 512, 256, 128] as const;
export type Dim = (typeof DIMS)[number];

export interface VideoMeta {
  id: string;
  title: string;
  duration: number;
  source_file: string;
  youtube_id: string | null;
  webpage_url: string | null;
  view_count: number | null;
  channel_position: number | null;
  transcript_source?: string;
  transcript_engine?: string;
  num_segments: number;
  thumb: string;
  video: string;
}

export interface Segment {
  id: string;
  video_id?: string;
  title?: string;
  idx: number;
  start: number;
  end: number;
  text: string;
  frame: string;
}

export interface Hit extends Segment {
  video_id: string;
  title: string;
  score: number;
  rank: number;
}

export interface Cue {
  start: number;
  end: number;
  text: string;
}

export interface VideoDetail extends VideoMeta {
  segments: Segment[];
  transcript: Cue[];
  transcripts?: Record<string, Cue[]>;
}

export interface Stats {
  model?: string;
  segments?: number;
  videos?: number;
  built_at?: string;
  dims: number[];
  views: View[];
  view_descriptions: Record<string, string>;
  storage: { dim: number; bytes_per_view: number }[];
  total_duration_s: number;
  views_built?: Record<string, { seconds: number; ms_per_segment: number; count: number }>;
}

export interface SearchResponse {
  query: string;
  view: View;
  dim: number;
  hits: Hit[];
  timing?: { embed_ms: number; search_ms: number };
}

export interface CompareResponse {
  query: string;
  view: View;
  k: number;
  columns: { dim: number; hits: Hit[]; overlap_with_768: number; top1_matches_768: boolean; bytes_per_view: number }[];
}

export interface CompareViewsResponse {
  query: string;
  dim: number;
  k: number;
  columns: { view: View; hits: Hit[] }[];
}

export interface AskResponse {
  question: string;
  answer: string;
  settings: { view: View; dim: number; k: number; use_video: boolean; use_audio: boolean };
  clips: Hit[];
  usage: { prompt_tokens: number; completion_tokens: number };
  timing: { retrieve_s: number; generate_s: number };
  created_at: string;
}

export interface GridRow {
  view: View;
  dim: number;
  query_type: "all" | "spoken" | "visual";
  "recall@1": number;
  "recall@5": number;
  "recall@10": number;
  "mrr@10": number;
  "neighbor_recall@5": number;
  "video_hit@1": number;
  n: number;
  search_ms: number;
}

export interface PerQuery {
  query: string;
  type: "spoken" | "visual";
  segment_id: string;
  video_id: string;
  evidence?: string;
  source: string;
  ranks: Record<string, number>;
  segment?: Hit;
}

export interface Experiments {
  created_at: string;
  model: string;
  transcripts?: string;
  variants?: string[];
  num_segments: number;
  num_queries: number;
  query_types: Record<string, number>;
  query_embed_ms: number;
  dims: number[];
  views: View[];
  storage: { dim: number; bytes_per_vector: number; bytes_per_view: number; bytes_all_views: number }[];
  grid: GridRow[];
  per_query: PerQuery[];
}

export async function getJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const qs = (params: Record<string, string | number | undefined>) =>
  new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== "")
      .map(([k, v]) => [k, String(v)]),
  ).toString();
