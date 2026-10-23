"use client";
import {
  MutableRefObject,
  RefObject,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import { api, token } from "@/lib/mentor";

type Recording = {
  id: string;
  camera: string;
  mode: string;
  mime: string;
  width: number;
  height: number;
  started: string;
  ended: string;
  durationMs: number;
  bytes: number;
  audio: boolean;
  blob: Blob;
  url: string;
  interrupted: boolean;
  consent: { video: true; microphone: boolean };
};
type Job = {
  id: string;
  status: string;
  stage: string;
  error?: string;
  video_id: string;
};
const LOCAL_LIMIT = 128 * 1024 * 1024,
  IMPORT_LIMIT = 64 * 1024 * 1024;
export function CameraRecorder({
  slot,
  video,
  canvas,
  active,
  stopRef,
  onBusy,
}: {
  slot: string;
  video: RefObject<HTMLVideoElement | null>;
  canvas: RefObject<HTMLCanvasElement | null>;
  active: boolean;
  stopRef: MutableRefObject<((reason?: string) => void) | null>;
  onBusy: (busy: boolean) => void;
}) {
  const recorder = useRef<MediaRecorder | null>(null),
    capture = useRef<MediaStream | null>(null),
    mic = useRef<MediaStream | null>(null);
  const preparing = useRef(false);
  const generation = useRef(0),
    mounted = useRef(true),
    currentUrl = useRef<string | null>(null),
    uploader = useRef<XMLHttpRequest | null>(null);
  const chunks = useRef<Blob[]>([]),
    bytes = useRef(0),
    started = useRef(0),
    discarded = useRef(false),
    interrupted = useRef(false);
  const [consent, setConsent] = useState(false),
    [audio, setAudio] = useState(false),
    [mode, setMode] = useState("original");
  const [pausable, setPausable] = useState(false);
  const [state, setState] = useState("idle"),
    [elapsed, setElapsed] = useState(0),
    [size, setSize] = useState(0);
  const [recording, setRecording] = useState<Recording | null>(null),
    [message, setMessage] = useState("");
  const [uploadConsent, setUploadConsent] = useState(false),
    [progress, setProgress] = useState<number | null>(null),
    [job, setJob] = useState<Job | null>(null);
  const invalidate = useCallback(() => {
    generation.current++;
  }, []);
  const cleanup = useCallback(() => {
    capture.current?.getTracks().forEach((t) => t.stop());
    capture.current = null;
    mic.current?.getTracks().forEach((t) => t.stop());
    mic.current = null;
  }, []);
  const stop = useCallback(
    (reason?: string) => {
      const rec = recorder.current;
      if (!rec && !preparing.current) return;
      generation.current++;
      if (reason) {
        interrupted.current = true;
        if (mounted.current) setMessage(reason);
      }
      if (rec) {
        if (rec.state !== "inactive") {
          if (mounted.current) setState("stopping");
          rec.stop();
        }
      } else {
        preparing.current = false;
        cleanup();
        if (mounted.current) {
          setState("idle");
          onBusy(false);
        }
      }
    },
    [cleanup, onBusy],
  );
  useEffect(() => {
    mounted.current = true;
    stopRef.current = stop;
    return () => {
      mounted.current = false;
      stopRef.current = null;
      invalidate();
      const rec = recorder.current;
      // Next Activity hides routes without deleting their state. Detach late
      // encoder callbacks before releasing resources, then clear cached UI.
      if (rec) {
        rec.onstop = null;
        rec.ondataavailable = null;
        rec.onerror = null;
      }
      if (rec && rec.state !== "inactive") rec.stop();
      recorder.current = null;
      preparing.current = false;
      cleanup();
      chunks.current = [];
      uploader.current?.abort();
      if (currentUrl.current) URL.revokeObjectURL(currentUrl.current);
      currentUrl.current = null;
      setRecording(null);
      setState("idle");
      setProgress(null);
      setJob(null);
      setSize(0);
      setElapsed(0);
      setUploadConsent(false);
      onBusy(false);
    };
  }, [cleanup, stop, stopRef, invalidate, onBusy]);
  useEffect(() => {
    if (state !== "recording" && state !== "paused") return;
    const timer = setInterval(() => {
      setElapsed(Math.max(0, performance.now() - started.current));
      if (performance.now() - started.current >= 30 * 60 * 1000)
        stop("30-minute recording limit reached.");
    }, 500);
    return () => clearInterval(timer);
  }, [state, stop]);
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const timer = setInterval(
      () =>
        void api<Job[]>("/api/jobs")
          .then((rows) => {
            const next = rows.find((row) => row.id === job.id);
            if (next) setJob(next);
          })
          .catch(() =>
            setMessage("Job status unavailable; refresh from Library."),
          ),
      2000,
    );
    return () => clearInterval(timer);
  }, [job]);
  async function start() {
    if (
      !consent ||
      !active ||
      preparing.current ||
      recorder.current ||
      recording
    )
      return;
    const epoch = ++generation.current;
    preparing.current = true;
    setMessage("");
    setState("starting");
    onBusy(true);
    chunks.current = [];
    bytes.current = 0;
    discarded.current = false;
    interrupted.current = false;
    setSize(0);
    setElapsed(0);
    try {
      if (typeof MediaRecorder === "undefined")
        throw new Error("Video recording is unsupported in this browser.");
      const mime = [
        "video/webm;codecs=vp9,opus",
        "video/webm;codecs=vp8,opus",
        "video/webm",
        "video/mp4",
      ].find((m) => MediaRecorder.isTypeSupported(m));
      if (!mime) throw new Error("No supported WebM or MP4 recording codec.");
      if (audio) {
        const next = await navigator.mediaDevices.getUserMedia({
          audio: true,
          video: false,
        });
        if (epoch !== generation.current || !mounted.current) {
          next.getTracks().forEach((t) => t.stop());
          return;
        }
        mic.current = next;
      }
      const v = video.current,
        c = canvas.current,
        source = v?.srcObject as MediaStream | null;
      if (!source?.getVideoTracks().some((t) => t.readyState === "live"))
        throw new Error("Start the camera preview before recording.");
      const output =
        mode === "original"
          ? new MediaStream(source.getVideoTracks().map((t) => t.clone()))
          : c?.captureStream?.(15);
      if (!output)
        throw new Error("Canvas video capture is unsupported in this browser.");
      capture.current = output;
      const audioTracks =
        mic.current?.getAudioTracks().filter((t) => t.readyState === "live") ??
        [];
      if (audio && !audioTracks.length)
        throw new Error(
          "No live microphone track was returned; recording was not started.",
        );
      for (const track of audioTracks) output.addTrack(track.clone());
      for (const track of output.getTracks())
        track.addEventListener(
          "ended",
          () => stop("Recording interrupted: capture device ended."),
          { once: true },
        );
      const rec = new MediaRecorder(output, {
        mimeType: mime,
        videoBitsPerSecond: 2500000,
      });
      recorder.current = rec;
      preparing.current = false;
      setPausable(
        typeof rec.pause === "function" && typeof rec.resume === "function",
      );
      const metadata = {
        id: crypto.randomUUID(),
        camera: slot,
        mode:
          mode === "original"
            ? "Original source · no crop or overlay"
            : "Canvas output · framing/mirror/annotations as shown",
        mime: rec.mimeType || mime,
        width: mode === "original" ? v!.videoWidth : c!.width,
        height: mode === "original" ? v!.videoHeight : c!.height,
        started: new Date().toISOString(),
        audio,
        consent: { video: true as const, microphone: audio },
      };
      rec.ondataavailable = (event) => {
        if (!mounted.current || discarded.current) return;
        bytes.current += event.data.size;
        if (bytes.current > LOCAL_LIMIT) {
          discarded.current = true;
          chunks.current = [];
          stop(
            "128 MiB local quota exceeded; recording discarded. Record a shorter clip.",
          );
          return;
        }
        if (event.data.size) chunks.current.push(event.data);
        setSize(bytes.current);
      };
      rec.onerror = () =>
        stop(
          "Recording interrupted by an encoder error; inspect the local replay before use.",
        );
      rec.onstop = () => {
        rec.ondataavailable = null;
        rec.onerror = null;
        if (mounted.current) {
          if (!discarded.current && chunks.current.length) {
            const blob = new Blob(chunks.current, { type: metadata.mime }),
              url = URL.createObjectURL(blob);
            currentUrl.current = url;
            setRecording({
              ...metadata,
              blob,
              url,
              bytes: blob.size,
              ended: new Date().toISOString(),
              durationMs: Math.max(0, performance.now() - started.current),
              interrupted: interrupted.current,
            });
            setUploadConsent(false);
            setJob(null);
          } else if (!discarded.current)
            setMessage("No media was produced; try another browser or codec.");
          setState("idle");
          onBusy(false);
        }
        chunks.current = [];
        recorder.current = null;
        cleanup();
      };
      started.current = performance.now();
      rec.start(1000);
      setState("recording");
    } catch (error) {
      cleanup();
      recorder.current = null;
      preparing.current = false;
      if (mounted.current && epoch === generation.current) {
        setMessage(
          error instanceof Error ? error.message : "Recording unavailable",
        );
        setState("idle");
        onBusy(false);
      }
    }
  }
  function upload() {
    if (!recording || !uploadConsent || recording.bytes > IMPORT_LIMIT) return;
    const credential = token();
    if (!credential) {
      setMessage("Connect your private library session before importing.");
      return;
    }
    const xhr = new XMLHttpRequest();
    uploader.current = xhr;
    xhr.open(
      "POST",
      `/api/ingest?filename=${encodeURIComponent(`${slot}-${recording.id}.${recording.mime.includes("mp4") ? "mp4" : "webm"}`)}`,
    );
    xhr.setRequestHeader("Authorization", `Bearer ${credential}`);
    xhr.timeout = 300000;
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable)
        setProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = xhr.ontimeout = () => {
      setProgress(null);
      setMessage("Import failed; local recording retained.");
    };
    xhr.onabort = () => {
      if (mounted.current) {
        setProgress(null);
        setMessage("Import cancelled; local recording retained.");
      }
    };
    xhr.onload = () => {
      setProgress(null);
      try {
        const body = JSON.parse(xhr.responseText);
        if (xhr.status !== 200 || typeof body.id !== "string")
          throw new Error();
        setJob({
          id: body.id,
          video_id: body.video_id ?? "",
          status: body.status ?? "queued",
          stage: "upload",
        });
        setMessage(
          "Imported through the existing Video RAG queue; remote processing follows the approved profile.",
        );
      } catch {
        setMessage(
          `Import rejected (${xhr.status}); local recording retained.`,
        );
      }
    };
    setProgress(0);
    xhr.send(recording.blob);
  }
  const busy = state !== "idle",
    button =
      "rounded-lg border border-line px-3 py-2 text-sm disabled:opacity-50";
  return (
    <div
      aria-label={`${slot} recording controls`}
      className="mt-4 border-t border-line pt-3"
    >
      <h3 className="font-medium">
        Video recording · local until explicit import
      </h3>
      <div className="my-2 flex flex-wrap items-center gap-3 text-sm">
        <label>
          <input
            aria-label={`${slot} recording consent`}
            type="checkbox"
            checked={consent}
            disabled={busy}
            onChange={(e) => setConsent(e.target.checked)}
          />{" "}
          Consent to record this camera locally
        </label>
        <label>
          <input
            aria-label={`${slot} microphone consent`}
            type="checkbox"
            checked={audio}
            disabled={busy}
            onChange={(e) => setAudio(e.target.checked)}
          />{" "}
          Include microphone (separate consent)
        </label>
        <select
          aria-label={`${slot} recording output`}
          className={`${button} bg-page`}
          value={mode}
          disabled={busy}
          onChange={(e) => setMode(e.target.value)}
        >
          <option value="original">Original source · no crop or overlay</option>
          <option value="canvas">
            Canvas output · framed / optionally annotated
          </option>
        </select>
        <button
          className={button}
          disabled={!active || !consent || busy || !!recording}
          onClick={() => void start()}
        >
          Record {slot}
        </button>
        <button
          className={button}
          disabled={!["recording", "paused"].includes(state) || !pausable}
          onClick={() => {
            const rec = recorder.current;
            if (!rec) return;
            if (rec.state === "recording") {
              rec.pause();
              setState("paused");
            } else if (rec.state === "paused") {
              rec.resume();
              setState("recording");
            }
          }}
        >
          {state === "paused"
            ? `Resume recording ${slot}`
            : `Pause recording ${slot}`}
        </button>
        <button className={button} disabled={!busy} onClick={() => stop()}>
          Stop recording {slot}
        </button>
      </div>
      <p aria-label={`${slot} recording state`} className="text-xs text-muted">
        {state} · elapsed wall time {(elapsed / 1000).toFixed(1)}s ·{" "}
        {(size / 1024 / 1024).toFixed(2)} MiB · 30 min / 128 MiB local maximum;
        import limit 64 MiB. One local clip per camera.
      </p>
      {recording && (
        <div className="mt-3 space-y-2" aria-label={`${slot} recording review`}>
          <p className="text-sm">
            {recording.mode} · {recording.width}×{recording.height} ·{" "}
            {recording.mime} ·{" "}
            {recording.audio ? "microphone included" : "no audio"} ·{" "}
            {(recording.bytes / 1024 / 1024).toFixed(2)} MiB{" "}
            {recording.interrupted ? "· Interrupted; inspect playback" : ""}
          </p>
          <video
            aria-label={`${slot} recording replay`}
            src={recording.url}
            controls
            playsInline
            className="w-full rounded-lg"
          />
          <a
            className={button}
            download={`${slot}-${recording.id}.${recording.mime.includes("mp4") ? "mp4" : "webm"}`}
            href={recording.url}
          >
            Download recording {slot}
          </a>
          <button
            className={button}
            disabled={progress !== null}
            onClick={() => {
              URL.revokeObjectURL(recording.url);
              currentUrl.current = null;
              setRecording(null);
              setUploadConsent(false);
            }}
          >
            Delete local recording {slot}
          </button>
          <p className="text-xs text-muted">
            Import stores this video on the server and may send
            audio/transcripts to approved inference providers. It is never
            automatically sent to research agents. Local recordings disappear
            when you close this tab.
          </p>
          <label className="block text-sm">
            <input
              aria-label={`${slot} import consent`}
              type="checkbox"
              checked={uploadConsent}
              onChange={(e) => setUploadConsent(e.target.checked)}
            />{" "}
            Authorize server storage and configured ingestion processing for
            this clip
          </label>
          <button
            className={button}
            disabled={
              !uploadConsent ||
              progress !== null ||
              recording.bytes > IMPORT_LIMIT ||
              !!job
            }
            onClick={upload}
          >
            Import {slot} to Video RAG
          </button>
          {recording.bytes > IMPORT_LIMIT && (
            <p className="text-sm">
              Over 64 MiB: download locally and create a shorter clip to import.
            </p>
          )}
          {progress !== null && (
            <>
              <progress
                aria-label={`${slot} recording upload progress`}
                value={progress}
                max={100}
              />
              <button
                className={button}
                onClick={() => uploader.current?.abort()}
              >
                Cancel import {slot}
              </button>
            </>
          )}
          {job && (
            <p aria-label={`${slot} recording job`} className="text-sm">
              {job.status} · {job.stage} {job.error ?? ""}{" "}
              <Link href="/">Open Library</Link>
            </p>
          )}
        </div>
      )}
      <p role="status" className="text-sm text-muted">
        {message}
      </p>
    </div>
  );
}
