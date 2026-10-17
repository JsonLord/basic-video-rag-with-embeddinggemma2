"use client";
import { useState } from "react";
export function AccessToken({ admin = false }: { admin?: boolean }) {
  const [token, setToken] = useState(""),
    [message, setMessage] = useState("");
  async function save() {
    sessionStorage.setItem(admin ? "vm-admin-token" : "vm-user-token", token);
    if (!admin) {
      try {
        const r = await fetch("/api/access", {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) throw new Error("Access denied");
        window.location.reload();
      } catch (e) {
        sessionStorage.removeItem("vm-user-token");
        setMessage(String(e));
      }
    } else setMessage("Administrator token saved for this tab");
  }
  return (
    <div className="my-3 flex flex-wrap items-center gap-2 text-sm">
      <label>
        {admin ? "Admin" : "Session"} access token{" "}
        <input
          aria-label={admin ? "Admin token" : "Session token"}
          type="password"
          autoComplete="off"
          className="rounded-lg border border-line bg-surface px-3 py-2"
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
      </label>
      <button
        className="rounded-lg border border-line px-3 py-2 hover:bg-surface-2"
        onClick={() => void save()}
      >
        Connect {admin ? "administrator" : "private library"}
      </button>
      <button
        className="text-muted"
        onClick={() => {
          sessionStorage.removeItem(admin ? "vm-admin-token" : "vm-user-token");
          if (!admin)
            void fetch("/api/access", { method: "DELETE" }).then(() =>
              window.location.reload(),
            );
          setMessage("Cleared");
        }}
      >
        Disconnect
      </button>
      <span role="status">{message}</span>
    </div>
  );
}
