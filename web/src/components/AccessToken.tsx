"use client";
import {useState} from "react";
export function AccessToken({admin=false}: {admin?:boolean}) {
  const [saved, setSaved] = useState(false);
  return <label className="block my-3 text-sm">{admin ? "Admin" : "Session"} access token (kept in this tab only)
    <input aria-label={admin ? "Admin token" : "Session token"} type="password" autoComplete="off" className="vm-input ml-2" onChange={e=>{sessionStorage.setItem(admin ? "vm-admin-token":"vm-user-token",e.target.value); setSaved(true);}} />
    {saved && <span className="text-muted ml-2">Stored for this tab</span>}
  </label>;
}
