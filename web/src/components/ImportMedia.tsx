"use client";
import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";
type Job = {
  id: string;
  title: string;
  status: string;
  stage: string;
  error: string | null;
  video_id: string;
};
export function ImportMedia() {
  const [jobs, setJobs] = useState<Job[]>([]),
    [message, setMessage] = useState(""),
    [progress, setProgress] = useState<number | null>(null),
    [transcript, setTranscript] = useState("");
  async function refresh() {
    if (sessionStorage.getItem("vm-user-token"))
      setJobs(await getJSON("/api/jobs"));
  }
  useEffect(() => {
    const timer = setInterval(() => void refresh().catch(() => {}), 2000);
    return () => clearInterval(timer);
  }, []);
  function upload(file: File) {
    if (!sessionStorage.getItem("vm-user-token")) {
      setMessage("Connect your private library before importing media.");
      return;
    }
    if (file.size > 64 * 1024 * 1024) {
      setMessage("Choose a video under 64 MiB.");
      return;
    }
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/ingest?filename=${encodeURIComponent(file.name)}`);
    xhr.setRequestHeader(
      "Authorization",
      `Bearer ${sessionStorage.getItem("vm-user-token")}`,
    );
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable)
        setProgress(Math.round((100 * e.loaded) / e.total));
    };
    xhr.onerror = () => {
      setMessage("Upload failed; retry when connected.");
      setProgress(null);
    };
    xhr.onload = () => {
      setProgress(null);
      setMessage(
        xhr.status === 200
          ? "Upload queued. Processing continues in the background."
          : `Upload failed (${xhr.status}).`,
      );
      void refresh();
    };
    setProgress(0);
    xhr.send(file);
  }
  async function action(j: Job, action: "retry" | "cancel") {
    try {
      await getJSON(`/api/jobs/${j.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, ...(transcript ? { transcript } : {}) }),
      });
      await refresh();
    } catch (e) {
      setMessage(String(e));
    }
  }
  return (
    <details className="rounded-xl border border-line bg-surface p-4">
      <summary className="flex items-center justify-between text-sm font-medium">
        Import & indexing{" "}
        <span className="text-muted">
          64 MiB · 30 min · one processing worker
        </span>
      </summary>
      <div className="mt-4 space-y-3">
        <p className="text-sm text-ink-2">
          Upload a video for proxy, thumbnails, 30-second segments, remote
          transcription and text indexing. No video is sent to an inference
          service until you import it. Transcript/audio destinations follow your
          authorized provider profile.
        </p>
        <input
          aria-label="Import video"
          type="file"
          accept="video/*"
          disabled={progress !== null}
          onChange={(e) => {
            if (e.target.files?.[0]) upload(e.target.files[0]);
          }}
        />
        {progress !== null && (
          <progress aria-label="Upload progress" value={progress} max={100} />
        )}
        <p role="status" className="text-sm text-muted">
          {message}
        </p>
        <label className="block text-sm">
          Optional transcript for retry (videos without audio)
          <textarea
            aria-label="Retry transcript"
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            maxLength={64000}
            className="mt-1 block w-full rounded-lg border border-line bg-page p-3"
            rows={2}
          />
        </label>
        {jobs.map((j) => (
          <div
            key={j.id}
            className="flex flex-wrap items-center justify-between gap-2 border-t border-line py-3 text-sm"
          >
            <div>
              <a href={`/videos/${j.video_id}`} className="text-accent">
                {j.title}
              </a>
              <p className="text-muted">
                {j.status} · {j.stage}
                {j.error ? ` · ${j.error}` : ""}
              </p>
            </div>
            <div className="flex gap-2">
              {["blocked", "failed", "cancelled"].includes(j.status) && (
                <button
                  className="rounded border border-line px-3 py-1"
                  onClick={() => void action(j, "retry")}
                >
                  Retry
                </button>
              )}
              {["queued", "running"].includes(j.status) && (
                <button
                  className="rounded border border-line px-3 py-1"
                  onClick={() => void action(j, "cancel")}
                >
                  Cancel
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}
