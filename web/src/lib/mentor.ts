export type Detection = { detection_id: string; object_id?: string; label: string; bbox_xyxy: [number, number, number, number]; confidence: number; source: string };
export type Observation = { session_id: string; camera_id: string; frame_id: number; request_id: string; config_version: number; source_width: number; source_height: number; observed_at: string; detections: Detection[]; decisions: {action:string; reason:string; source:string}[]; provider_results: {provider:string; status:string; latency_ms:number}[]; warnings:string[] };
export function token(admin = false) { return sessionStorage.getItem(admin ? "vm-admin-token" : "vm-user-token") ?? ""; }
export async function api<T>(path: string, body?: unknown, admin = false, method?: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, {method: method ?? (body === undefined ? "GET" : "POST"), headers: {"Content-Type":"application/json", Authorization:`Bearer ${token(admin)}`}, body:body === undefined ? undefined : JSON.stringify(body), signal});
  const data = await res.json();
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${res.status})`);
  return data as T;
}
export function download(name: string, contents: string) {
  const href = URL.createObjectURL(new Blob([contents], {type:"application/yaml"}));
  const a = document.createElement("a"); a.href = href; a.download = name; a.click(); URL.revokeObjectURL(href);
}
