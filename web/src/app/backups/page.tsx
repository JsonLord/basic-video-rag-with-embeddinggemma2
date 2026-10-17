"use client";
import { useState } from "react";
import { AccessToken } from "@/components/AccessToken";
import { api } from "@/lib/mentor";

type Report = {
  configured: boolean;
  stale: boolean;
  last_success: { checkpoint: string; created_at?: number; encrypted_bytes_referenced?: number } | null;
  pending_uploads: number | null;
  encrypted_storage_bytes: number | null;
  restore_points: string[];
  last_recovery_test: { verified: boolean; checkpoint?: string; tested_at: number } | null;
  failure_code: string | null;
  queued: boolean;
};
export default function Backups() {
  const [report, setReport] = useState<Report | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function refresh() { setReport(await api<Report>("/api/admin/backup-status", undefined, true)); }
  async function run(path?: string) {
    setBusy(true);
    try {
      if (path) {
        await api(path, {}, true);
        setMessage("Request queued. Refresh to check completion; acceptance does not establish success.");
      }
      await refresh();
    } catch (error) { setMessage(String(error)); }
    finally { setBusy(false); }
  }
  const panel = "rounded-xl border border-line bg-surface p-5";
  const button = "rounded-lg border border-line px-4 py-2 text-sm disabled:opacity-50";
  return <div className="space-y-5">
    <h1 className="text-2xl font-semibold">Backup administration</h1>
    <p className="text-sm text-ink-2">Encrypted GitHub recovery checkpoints. The Space filesystem is ephemeral. A queued backup is not a successful checkpoint.</p>
    <AccessToken admin />
    <div className="flex flex-wrap gap-3">
      <button className={button} disabled={busy} onClick={() => void run()}>Refresh status</button>
      <button className={button} disabled={busy || !report?.configured} onClick={() => void run("/api/admin/backup")}>Back up now</button>
      <button className={button} disabled={busy || !report?.configured} onClick={() => void run("/api/admin/backup/recovery-test")}>Test isolated recovery</button>
    </div>
    <p role="status" className="text-sm">{message}</p>
    {report && <>
      <div className="grid gap-4 md:grid-cols-2">
        <section className={panel}><h2 className="font-medium">Latest successful checkpoint</h2><p className="mt-2 break-all text-sm">{report.last_success?.checkpoint ?? "No verified checkpoint"}</p><p className="text-sm text-muted">{report.stale ? "Stale or unverified" : "Within 14 hours"} · {report.queued ? "Backup queued or running" : "Idle"}</p></section>
        <section className={panel}><h2 className="font-medium">Pending uploads</h2><p>{report.pending_uploads ?? "Not measured"}</p><h2 className="mt-3 font-medium">Encrypted GitHub storage</h2><p>{report.encrypted_storage_bytes === null ? "Not measured" : `${(report.encrypted_storage_bytes / 1024 ** 2).toFixed(2)} MiB`}</p><p className="text-xs text-muted">Includes historical and incomplete release assets in this namespace.</p></section>
        <section className={panel}><h2 className="font-medium">Last recovery test</h2><p>{report.last_recovery_test ? (report.last_recovery_test.verified ? "Verified complete recovery" : "Failed") : "Not tested"}</p><p className="break-all text-sm">{report.last_recovery_test?.checkpoint}</p><p className="text-sm">{report.failure_code ?? "No recorded failure"}</p></section>
        <section className={panel}><h2 className="font-medium">Restore points</h2><ul className="mt-2 max-h-64 overflow-auto text-xs">{report.restore_points.map(point => <li className="mb-2 break-all" key={point}>{point}</li>)}</ul><p className="text-xs text-muted">Startup restores the latest committed checkpoint into empty state. Existing state is never overwritten.</p></section>
      </div>
    </>}
  </div>;
}
