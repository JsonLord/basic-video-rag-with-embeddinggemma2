export type Detection = { detection_id: string; object_id?: string; label: string; bbox_xyxy: [number, number, number, number]; confidence: number; source: string };
export type Observation = { session_id: string; camera_id: string; frame_id: number; captured_at: number; request_id: string; config_version: number; source_width: number; source_height: number; observed_at: string; detections: Detection[]; decisions: {action:string; reason:string; source:string}[]; provider_results: {provider:string; status:string; latency_ms:number}[]; warnings:string[] };
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

export function matchesObservation(o: Observation, expected: {session:string;camera:string;frame:number;request:string;version:number;width:number;height:number}) {
  return o.session_id===expected.session && o.camera_id===expected.camera && o.frame_id===expected.frame &&
    o.request_id===expected.request && o.config_version===expected.version && o.source_width===expected.width && o.source_height===expected.height &&
    Array.isArray(o.detections) && o.detections.every(d=>{
      const box=d.bbox_xyxy;
      return Array.isArray(box) && box.length===4 && box.every(n=>Number.isFinite(n)&&n>=0&&n<=1) &&
        box[0]<box[2] && box[1]<box[3] && Number.isFinite(d.confidence) && d.confidence>=0 && d.confidence<=1;
    });
}
