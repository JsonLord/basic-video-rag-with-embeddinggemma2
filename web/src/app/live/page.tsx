"use client";
import {useCallback, useEffect, useRef, useState} from "react";
import {AccessToken} from "@/components/AccessToken";
import {api, Observation} from "@/lib/mentor";

type Registry = {config_version:number; providers:Record<string,{destination:string|null}>; features:Record<string,{enabled:boolean;providers:string[]}>};
function Camera({slot, devices, session, registry, onObservation}: {slot:string;devices:MediaDeviceInfo[];session:string|null;registry:Registry|null;onObservation:(o:Observation)=>void}) {
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream|null>(null);
  const pending = useRef(false);
  const generation = useRef(0);
  const frame = useRef(0);
  const abort = useRef<AbortController|null>(null);
  const [device,setDevice] = useState("");
  const [active,setActive] = useState(false);
  const [send,setSend] = useState(false);
  const [fps,setFps] = useState(1);
  const [width,setWidth] = useState(640);
  const [mirror,setMirror] = useState(false);
  const [feature,setFeature] = useState(`live.${slot}.scene`);
  const [error,setError] = useState("");
  const [result,setResult] = useState<{observation:Observation;image:string}|null>(null);
  const stop = useCallback(()=>{generation.current++; abort.current?.abort(); stream.current?.getTracks().forEach(t=>t.stop()); stream.current=null; if(video.current) video.current.srcObject=null; setActive(false);setSend(false);setResult(null);},[]);
  useEffect(()=>()=>{generation.current++;abort.current?.abort(); stream.current?.getTracks().forEach(t=>t.stop());},[]);
  useEffect(()=>{const hide=()=>{if(document.hidden) stop();};document.addEventListener("visibilitychange",hide);return()=>document.removeEventListener("visibilitychange",hide);},[stop]);
  useEffect(()=>{if(!session) {generation.current++;abort.current?.abort();}},[session]);
  async function start() {
    stop(); setError(""); const g=generation.current;
    try {
      const next = await navigator.mediaDevices.getUserMedia({video:{deviceId:device ? {exact:device}:undefined,width:{ideal:width},height:{ideal:width*0.75}},audio:false});
      if(g!==generation.current) {next.getTracks().forEach(t=>t.stop());return;}
      stream.current=next;
      next.getVideoTracks()[0].addEventListener("ended",stop,{once:true});
      if(video.current) {video.current.srcObject=next;await video.current.play();}
      setActive(true);
    } catch(e) {setError(`Camera unavailable: ${e instanceof Error ? e.message:String(e)}. Check permission or device contention.`);}
  }
  const analyze = useCallback(async()=>{
    if(!session || !send || !active || pending.current || !video.current || !registry) return;
    const v=video.current;
    if(!v.videoWidth) return;
    const canvas=document.createElement("canvas");
    canvas.width=Math.min(v.videoWidth,width);canvas.height=Math.round(canvas.width*v.videoHeight/v.videoWidth);
    if(canvas.height>1080) return;
    canvas.getContext("2d")?.drawImage(v,0,0,canvas.width,canvas.height);
    const image=canvas.toDataURL("image/jpeg",0.7), id=++frame.current, requestId=crypto.randomUUID(), g=generation.current;
    pending.current=true;abort.current=new AbortController();
    try {
      const o=await api<Observation>(`/api/live/sessions/${session}/frames`,{camera_id:slot,frame_id:id,captured_at:performance.now(),image,feature,config_version:registry.config_version,request_id:requestId},false,undefined,abort.current.signal);
      if(g===generation.current && o.frame_id===id && o.camera_id===slot && o.request_id===requestId && o.session_id===session) {setResult({observation:o,image});onObservation(o);setError("");}
    } catch(e) {if(!(e instanceof DOMException && e.name==="AbortError")) setError(e instanceof Error?e.message:String(e));}
    finally {pending.current=false;}
  },[session,send,active,registry,width,slot,feature,onObservation]);
  useEffect(()=>{if(!send)return;const timer=setInterval(()=>void analyze(),1000/fps);return()=>clearInterval(timer);},[analyze,send,fps]);
  const features=Object.keys(registry?.features??{}).filter(f=>(f.startsWith(`live.${slot}.`)||f==="live.visual_decision")&&registry?.features[f].enabled);
  const destinations=(registry?.features[feature]?.providers??[]).map(p=>`${p}: ${registry?.providers[p]?.destination??"unconfigured"}`).join(", ");
  return <section className="vm-panel">
    <h2 className="text-xl font-semibold">{slot==="camera1"?"Camera 1":"Camera 2"}</h2>
    <div className="flex flex-wrap gap-2 my-3">
      <select aria-label={`${slot} device`} value={device} className="vm-input" onChange={e=>{stop();setDevice(e.target.value);}}><option value="">Default camera</option>{devices.map(d=><option key={d.deviceId} value={d.deviceId}>{d.label||"Camera"}</option>)}</select>
      <select aria-label={`${slot} resolution`} value={width} className="vm-input" onChange={e=>{stop();setWidth(+e.target.value);}}>{[320,640,1280].map(w=><option key={w} value={w}>{w} × {w*0.75}</option>)}</select>
      <button className="vm-button" onClick={()=>void start()}>Start preview</button><button className="vm-button" onClick={stop}>Stop camera</button>
    </div>
    <video aria-label={`${slot} preview`} ref={video} autoPlay muted playsInline className="w-full rounded-lg bg-black aspect-[4/3] object-contain" style={{transform:mirror?"scaleX(-1)":undefined}} />
    <div className="flex flex-wrap gap-3 my-3 items-center">
      <label><input type="checkbox" checked={mirror} onChange={e=>setMirror(e.target.checked)} /> Mirror</label>
      <label>FPS <input aria-label={`${slot} FPS`} className="vm-input w-20" type="number" min="0.1" max="2" step="0.1" value={fps} onChange={e=>setFps(Math.min(2,Math.max(0.1,+e.target.value||1)))} /></label>
      <select aria-label={`${slot} route`} className="vm-input" value={feature} onChange={e=>{generation.current++;abort.current?.abort();setResult(null);setFeature(e.target.value);}}><option value={`live.${slot}.scene`}>Select route</option>{features.map(f=><option key={f}>{f}</option>)}</select>
      <label><input aria-label={`${slot} send frames`} type="checkbox" disabled={!session||!active||!features.includes(feature)} checked={send&&!!session} onChange={e=>{generation.current++;abort.current?.abort();setResult(null);setSend(e.target.checked);}} /> Enable frame transfer</label>
      <button className="vm-button" disabled={!send} onClick={()=>void analyze()}>Analyze now</button>
    </div>
    <p className="text-sm text-muted">{send?"Sending sampled frames":"Local preview only"} · Destination: {destinations||"none"} · One request in flight maximum.</p>
    {error&&<p role="alert" className="text-red-300 my-2">{error}</p>}
    {result&&session&&<div className="mt-4"><p className="text-sm">Analyzed frame {result.observation.frame_id} · {result.observation.observed_at}</p>
      <div className="relative w-full" style={{aspectRatio:`${result.observation.source_width}/${result.observation.source_height}`,transform:mirror?"scaleX(-1)":undefined}}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img alt="Last analyzed frame, retained only in this browser tab" src={result.image} className="absolute inset-0 w-full h-full" />
        <svg aria-label={`${slot} detection overlay`} className="absolute inset-0 w-full h-full" viewBox="0 0 1000 1000" preserveAspectRatio="none">{result.observation.detections.map(d=>{const [x1,y1,x2,y2]=d.bbox_xyxy;return <g key={`${d.source}-${d.detection_id}`}><rect x={x1*1000} y={y1*1000} width={(x2-x1)*1000} height={(y2-y1)*1000} fill="none" stroke="#4ade80" strokeWidth="3"/><title>{d.label} {Math.round(d.confidence*100)}% · {d.source}</title></g>;})}</svg>
      </div>
      {result.observation.detections.map(d=><p key={`${d.source}-${d.detection_id}`}>{d.label} {Math.round(d.confidence*100)}% · {d.source}{d.object_id?` · track ${d.object_id}`:""}</p>)}
      {result.observation.decisions.map((d,i)=><p key={i} className="mt-2">{d.source}: {d.reason}</p>)}
    </div>}
  </section>;
}

function Microphone({session,onText}:{session:string|null;onText:(s:string)=>void}) {
  const recorder=useRef<MediaRecorder|null>(null), mic=useRef<MediaStream|null>(null), timer=useRef<ReturnType<typeof setTimeout>|null>(null);
  const [recording,setRecording]=useState(false), [error,setError]=useState("");
  const disposed=useRef(false);
  useEffect(()=>{disposed.current=false;return()=>{disposed.current=true;if(recorder.current?.state==="recording")recorder.current.stop();mic.current?.getTracks().forEach(t=>t.stop());if(timer.current)clearTimeout(timer.current);};},[]);
  useEffect(()=>{if(!session){if(recorder.current?.state==="recording")recorder.current.stop();mic.current?.getTracks().forEach(t=>t.stop());}},[session]);
  async function start(){
    if(!session)return;
    try {
      if(!MediaRecorder.isTypeSupported("audio/webm"))throw new Error("This browser does not support bounded WebM recording");
      const s=await navigator.mediaDevices.getUserMedia({audio:true});
      if(disposed.current){s.getTracks().forEach(t=>t.stop());return;}
      mic.current=s;const r=new MediaRecorder(s,{mimeType:"audio/webm",audioBitsPerSecond:64000});recorder.current=r;const chunks:Blob[]=[];
      r.ondataavailable=e=>{chunks.push(e.data);};
      r.onstop=async()=>{s.getTracks().forEach(t=>t.stop());if(timer.current)clearTimeout(timer.current);if(disposed.current)return;setRecording(false);
        try{const blob=new Blob(chunks,{type:"audio/webm"});if(blob.size>2000000)throw new Error("Audio clip too large");const bytes=new Uint8Array(await blob.arrayBuffer());let binary="";for(const b of bytes)binary+=String.fromCharCode(b);const response=await api<{text:string}>(`/api/live/sessions/${session}/transcribe`,{audio:btoa(binary),duration_ms:15000});onText(response.text||"No transcription result");}catch(e){setError(e instanceof Error?e.message:String(e));}};
      r.start();setRecording(true);timer.current=setTimeout(()=>{if(r.state==="recording")r.stop();},15000);
    }catch(e){setError(e instanceof Error?e.message:String(e));}
  }
  return <div className="my-3"><button className="vm-button" disabled={!session} onClick={()=>{if(recording)recorder.current?.stop();else void start();}}>{recording?"Stop and send audio":"Push to talk (send up to 15 seconds)"}</button>{error&&<p role="alert">{error}</p>}</div>;
}

export default function Live(){
  const [devices,setDevices]=useState<MediaDeviceInfo[]>([]),[session,setSession]=useState<string|null>(null),[registry,setRegistry]=useState<Registry|null>(null),[error,setError]=useState("");
  const [observations,setObservations]=useState<Observation[]>([]),[combined,setCombined]=useState(true),[guidance,setGuidance]=useState(""),[goal,setGoal]=useState(""),[step,setStep]=useState("Observe"),[completed,setCompleted]=useState(false);
  const current=useRef<string|null>(null);
  const observation=useCallback((o:Observation)=>setObservations(old=>[o,...old].slice(0,30)),[]);
  useEffect(()=>()=>{if(current.current)void api(`/api/live/sessions/${current.current}`,undefined,false,"DELETE").catch(()=>{});},[]);
  async function enumerate(){try{const s=await navigator.mediaDevices.getUserMedia({video:true,audio:false});s.getTracks().forEach(t=>t.stop());setDevices((await navigator.mediaDevices.enumerateDevices()).filter(d=>d.kind==="videoinput"));}catch(e){setError(e instanceof Error?e.message:String(e));}}
  async function enable(){try{const reg=await api<Registry>("/api/providers");setRegistry(reg);const res=await api<{session_id:string}>("/api/live/sessions",{consent:true});setSession(res.session_id);current.current=res.session_id;setError("");}catch(e){setError(e instanceof Error?e.message:String(e));}}
  async function clear(){const old=current.current;setSession(null);current.current=null;setObservations([]);setGuidance("");setGoal("");setStep("Observe");setCompleted(false);if(old)try{await api(`/api/live/sessions/${old}`,undefined,false,"DELETE");}catch(e){setError(e instanceof Error?e.message:String(e));}}
  async function mentor(){if(!session)return;try{await api(`/api/live/sessions/${session}/task`,{goal,step,completed},false,"PUT");const r=await api<{guidance:string}>(`/api/live/sessions/${session}/guidance`,{});setGuidance(r.guidance||"No mentor provider result");}catch(e){setError(e instanceof Error?e.message:String(e));}}
  return <><h1 className="text-3xl font-semibold">Live mentor</h1><p className="text-ink-2 my-2">Two local camera previews. Frame and microphone transfer require explicit actions. No recording is stored by the server.</p><AccessToken/>
    <div className="flex flex-wrap gap-3 my-4"><button className="vm-button" onClick={()=>void enumerate()}>Grant camera permission & list devices</button><button className="vm-button" disabled={!!session} onClick={()=>void enable()}>Authorize analysis session</button><button className="vm-button" onClick={()=>void clear()}>Clear session & pause transfers</button><label><input type="checkbox" checked={combined} onChange={e=>setCombined(e.target.checked)}/> Combined view</label></div>
    <p className="text-muted text-sm mb-3">Preview stops when this tab is hidden or left. Detection overlays use the exact analyzed still, so moving live video never receives stale boxes.</p>
    {error&&<p role="alert" className="text-red-300">{error}</p>}
    <div className={combined?"grid gap-4 lg:grid-cols-2":"grid gap-4"}>{["camera1","camera2"].map(slot=><Camera key={`${slot}-${session??"preview"}`} slot={slot} devices={devices} session={session} registry={registry} onObservation={observation}/>)}</div>
    <section className="vm-panel mt-5"><h2 className="text-xl">Mentor guidance</h2><div className="flex flex-wrap gap-3 my-3"><input aria-label="Mentoring goal" className="vm-input" placeholder="Goal" maxLength={1000} value={goal} onChange={e=>setGoal(e.target.value)}/><input aria-label="Current task step" className="vm-input" placeholder="Current step" maxLength={500} value={step} onChange={e=>setStep(e.target.value)}/><label><input type="checkbox" checked={completed} onChange={e=>setCompleted(e.target.checked)}/> Step complete</label></div><Microphone key={session??"disabled"} session={session} onText={setGuidance}/><button className="vm-button" disabled={!session} onClick={()=>void mentor()}>Request guidance from observations</button><p className="my-3 whitespace-pre-wrap">{guidance||"Guidance is advisory; no autonomous actions."}</p></section>
    <section className="vm-panel mt-5"><h2 className="text-xl">Observation timeline & routing monitor</h2>{!observations.length&&<p className="text-muted">No frames sent.</p>}{observations.map(o=><article key={`${o.camera_id}-${o.frame_id}-${o.request_id}`} className="border-b border-line py-3"><p>{o.camera_id} · frame {o.frame_id} · config {o.config_version} · {o.observed_at}</p>{o.provider_results.map(r=><p key={r.provider} className="text-sm">{r.provider}: {r.status} · {r.latency_ms} ms</p>)}{o.warnings.map(w=><p key={w}>{w}</p>)}</article>)}</section>
  </>;
}
