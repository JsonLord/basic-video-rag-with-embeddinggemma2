"use client";
import { useState } from "react";
import { parse, stringify } from "yaml";
import { AccessToken } from "@/components/AccessToken";
import { api, download } from "@/lib/mentor";
type Provider = {
  label?: string;
  capability_version?: number;
  model_env?: string | null;
  adapter: string;
  model: string;
  capabilities: string[];
  base_url_env: string;
  api_key_secret?: string | null;
  trust: string;
};
type Route = {
  strategy: string;
  providers: string[];
  enabled: boolean;
  result_policy?: string;
  quorum?: number;
  fusion?: string;
  conditions?: { field: string; equals: string; provider: string }[];
};
type Config = {
  version: number;
  profile: string;
  providers: Record<string, Provider>;
  features: Record<string, Route>;
};
type EnvironmentDefaults = {
  status: string;
  error?: string;
  live_status: string;
  providers: Record<
    string,
    {
      destination: string | null;
      model: string;
      credential_present: boolean;
      capability_version: number;
      trust: string;
    }
  >;
};
const featureRoles = [
  "mentor.conversation",
  "live.camera1.detection",
  "live.camera2.detection",
  "live.camera1.decisions",
  "live.camera2.decisions",
  "live.tracking",
  "live.framing.target_selection",
  "live.temporal_reasoning",
  "audio.transcription",
  "research.dispatch",
];
type Snapshot = {
  models?: Record<string, { model: string; configured: boolean }>;
  schema_version?: number;
  history_revision?: number;
  environment_defaults?: EnvironmentDefaults;
  yaml: string;
  config_version: number;
  history: number[];
  writable: boolean;
  config: Config;
  destinations?: Record<string, string | null>;
  credentials?: Record<string, boolean>;
};
const btn =
  "rounded-lg border border-line px-3 py-2 text-sm hover:bg-surface-2";
const field = "rounded-lg border border-line bg-page px-3 py-2 text-sm";
const panel = "rounded-xl border border-line bg-surface p-5";
const caps: Record<string, string[]> = {
  "openai-conversation": ["conversation", "reasoning"],
  a2a: ["research_dispatch"],
  "laya-vision": ["image_understanding", "visual_decision"],
  "detection-http": ["object_detection", "bounding_boxes"],
  "openai-chat-vision": ["image_understanding", "reasoning"],
  "openai-embeddings": ["text_embeddings"],
  "openai-transcription": ["transcription"],
};
export default function Models() {
  const [state, setState] = useState<Snapshot | null>(null),
    [text, setText] = useState(""),
    [profiles, setProfiles] = useState<Record<string, string>>({}),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [valid, setValid] = useState(""),
    [rollback, setRollback] = useState(1),
    [trace, setTrace] = useState<unknown>(null),
    [backup, setBackup] = useState<unknown>(null);
  const [feature, setFeature] = useState("live.camera1.scene"),
    [strategy, setStrategy] = useState("parallel"),
    [providers, setProviders] = useState<string[]>([]),
    [policy, setPolicy] = useState("all"),
    [quorum, setQuorum] = useState(1);
  const [pid, setPid] = useState(""),
    [adapter, setAdapter] = useState("laya-vision"),
    [model, setModel] = useState(""),
    [endpoint, setEndpoint] = useState(""),
    [secret, setSecret] = useState(""),
    [trust, setTrust] = useState("public_only");
  let draft: Config | null = null;
  try {
    const c = parse(text, { maxAliasCount: 0 });
    if (c && typeof c === "object")
      draft = { version: 1, providers: {}, features: {}, ...c } as Config;
  } catch {}
  function edit(t: string) {
    setText(t);
    setValid("");
  }
  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      setMessage(JSON.stringify(await fn(), null, 2));
    } catch (e) {
      setMessage(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function load() {
    const s = await api<Snapshot>("/api/config", undefined, true);
    setState(s);
    edit(s.yaml);
    setProfiles(await api("/api/config/profiles", undefined, true));
    return { version: s.config_version, profile: s.config.profile };
  }
  function buildRoute() {
    if (!draft) throw Error("Load a profile first.");
    const r: Route = { strategy, providers, enabled: true };
    if (strategy === "parallel") {
      r.result_policy = policy;
      r.quorum = quorum;
      r.fusion = "spatial_semantic";
    }
    if (strategy === "conditional")
      r.conditions = providers.map((provider) => ({
        field: "camera_id",
        equals: feature.includes("camera2") ? "camera2" : "camera1",
        provider,
      }));
    edit(
      stringify({ ...draft, features: { ...draft.features, [feature]: r } }),
    );
    return { updated: "draft only" };
  }
  function buildProvider() {
    if (
      ["openai-conversation", "a2a"].includes(adapter) &&
      draft?.version !== 2
    )
      throw Error("Migrate the draft to schema v2 first.");
    if (!draft) throw Error("Load a profile first.");
    if (!/^[a-zA-Z0-9_-]{1,64}$/.test(pid) || !model)
      throw Error("Provide an ID and a verified model ID.");
    edit(
      stringify({
        ...draft,
        providers: {
          ...draft.providers,
          [pid]: {
            label: pid,
            adapter,
            model,
            base_url_env: endpoint,
            api_key_secret: secret || null,
            capabilities: caps[adapter],
            trust,
          },
        },
      }),
    );
    return { updated: "draft only" };
  }
  const changes =
    draft && state
      ? (Object.keys(draft) as (keyof Config)[]).filter(
          (k) => JSON.stringify(draft?.[k]) !== JSON.stringify(state.config[k]),
        )
      : [];
  return (
    <div className="space-y-6">
      <section>
        <div className="flex flex-wrap justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold">Models & Routing</h1>
            <p className="mt-1 max-w-3xl text-sm text-ink-2">
              Remote models, authorized destinations and typed execution traces.
              Changes remain in the editor until reviewed and applied.
            </p>
          </div>
          <span className="text-xs text-muted">
            {state
              ? `${state.config.profile} · schema ${state.schema_version ?? state.config.version} · history revision ${state.history_revision ?? state.config_version}`
              : "Administrator access required"}
          </span>
        </div>
        <AccessToken admin />
      </section>
      <div className="flex flex-wrap items-center gap-2">
        <button className={btn} disabled={busy} onClick={() => void run(load)}>
          Load current config
        </button>
        <button
          className={btn}
          disabled={!draft || busy}
          onClick={() =>
            void run(async () => {
              const result = await api<{ yaml: string }>(
                "/api/config/migrate",
                { yaml: text },
                true,
              );
              edit(result.yaml);
              return { schema_version: 2, persisted: false };
            })
          }
        >
          Migrate draft to schema v2
        </button>
        <button
          className={btn}
          disabled={!draft || busy}
          onClick={() =>
            void run(async () => {
              const result = await api<{ yaml: string }>(
                "/api/config/migrate",
                { yaml: text, include_environment_defaults: true },
                true,
              );
              edit(result.yaml);
              return { environment_defaults: "draft only; routes disabled" };
            })
          }
        >
          Use HF defaults in draft
        </button>
        <label className={btn}>
          Import YAML
          <input
            aria-label="Import YAML"
            type="file"
            accept=".yaml,.yml"
            className="block max-w-48 text-xs"
            onChange={(e) =>
              void run(async () => {
                const f = e.target.files?.[0];
                if (!f || !/\.ya?ml$/i.test(f.name) || f.size > 65536)
                  throw Error("Choose .yaml/.yml under 64 KiB.");
                edit(await f.text());
                return { imported: f.name, applied: false };
              })
            }
          />
        </label>
        <label className="text-xs text-muted">
          Save as profile
          <input
            aria-label="Draft profile name"
            className={`${field} ml-2`}
            disabled={!draft}
            value={draft?.profile || ""}
            onChange={(e) => {
              if (draft) edit(stringify({ ...draft, profile: e.target.value }));
            }}
          />
        </label>
        <select
          aria-label="Example profile"
          className={field}
          value=""
          onChange={(e) => edit(profiles[e.target.value])}
        >
          <option value="">Choose profile template</option>
          {Object.keys(profiles)
            .sort()
            .map((p) => (
              <option key={p}>{p}</option>
            ))}
        </select>
        <button
          className={btn}
          disabled={!state}
          onClick={() => state && download("routing-active.yaml", state.yaml)}
        >
          Export active
        </button>
        <button
          className={btn}
          disabled={!draft}
          onClick={() => download("routing-draft.yaml", text)}
        >
          Save draft
        </button>
      </div>
      <p className="text-xs text-muted">
        {state?.writable
          ? "Configuration state is writable; external storage determines durability."
          : "Set VM_STATE_DIR to enable atomic updates."}{" "}
        Templates need real model IDs and approved HTTPS endpoints. Secrets stay
        in server environment settings.
      </p>
      {!draft && (
        <div className={panel}>
          <h2 className="font-medium">Start with a reviewed profile</h2>
          <p className="mt-2 text-sm text-muted">
            Load the current configuration or import YAML. Laya semantic
            decisions and NVIDIA gateway detections retain independent
            provenance. Scores never become boxes.
          </p>
        </div>
      )}
      {state?.environment_defaults && (
        <section className={panel} aria-label="Hugging Face runtime defaults">
          <h2 className="font-medium">Hugging Face runtime defaults</h2>
          <p className="text-sm">
            {state.environment_defaults.status} · Live health{" "}
            {state.environment_defaults.live_status}. Defaults do not authorize
            sensitive transfers or enable routes.
          </p>
          {state.environment_defaults.error && (
            <p role="alert">{state.environment_defaults.error}</p>
          )}
          {Object.entries(state.environment_defaults.providers).map(
            ([name, p]) => (
              <p className="text-sm break-all" key={name}>
                {name} · {p.destination ?? "unconfigured"} · {p.model} ·
                credential available: {String(p.credential_present)} ·
                capability contract v{p.capability_version}
              </p>
            ),
          )}
        </section>
      )}
      <section
        aria-label="Provider cards"
        className="grid gap-3 md:grid-cols-2 xl:grid-cols-3"
      >
        {Object.entries(draft?.providers ?? {}).map(([id, p]) => (
          <article key={id} className={panel}>
            <div className="flex justify-between gap-2">
              <h2 className="font-medium">{p.label || id}</h2>
              <span className="text-xs text-muted">Live status unchecked</span>
            </div>
            <p className="mt-1 break-all font-mono text-xs text-accent">
              {state?.models?.[id]?.model ?? p.model}
            </p>
            <p className="mt-3 text-xs text-ink-2">
              {p.adapter} · {p.capabilities.join(" · ")}
            </p>
            <div className="mt-3 space-y-1 text-xs text-muted">
              <p>
                Destination: {state?.destinations?.[id] || "not configured"}
              </p>
              <p>Endpoint reference: {p.base_url_env}</p>
              <p>Capability contract version: {p.capability_version ?? 1}</p>
              {p.model_env && <p>Model reference: {p.model_env}</p>}
              <p>
                Credentials:{" "}
                {state?.credentials?.[id]
                  ? "available or not required"
                  : "missing / unchecked"}
              </p>
              <p>Secret reference: {p.api_key_secret || "none"}</p>
              <p>Camera authorization: {p.trust}</p>
            </div>
            <button
              className={`${btn} mt-3`}
              disabled={!state?.config.providers[id] || busy}
              onClick={() =>
                void run(async () => {
                  const r = await api(`/api/providers/${id}/test`, {}, true);
                  setTrace(r);
                  return r;
                })
              }
            >
              Test synthetic
            </button>
          </article>
        ))}
      </section>
      <details className={panel}>
        <summary className="text-sm font-medium">
          Provider form · add or update
        </summary>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[
            ["Provider ID", pid, setPid],
            ["Model ID", model, setModel],
            ["Endpoint reference", endpoint, setEndpoint],
            ["Secret reference", secret, setSecret],
          ].map(([label, value, setter]) => (
            <label key={label as string} className="text-xs text-muted">
              {label as string}
              <input
                aria-label={label as string}
                className={`${field} mt-1 w-full`}
                value={value as string}
                onChange={(e) =>
                  (setter as (s: string) => void)(e.target.value)
                }
              />
            </label>
          ))}
          <label className="text-xs text-muted">
            Protocol
            <select
              aria-label="Provider protocol"
              className={`${field} mt-1 w-full`}
              value={adapter}
              onChange={(e) => setAdapter(e.target.value)}
            >
              {Object.keys(caps).map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </label>
          <label className="text-xs text-muted">
            Privacy authorization
            <select
              aria-label="Privacy authorization"
              className={`${field} mt-1 w-full`}
              value={trust}
              onChange={(e) => setTrust(e.target.value)}
            >
              <option>public_only</option>
              <option>approved_sensitive</option>
            </select>
          </label>
          <button
            className={btn}
            onClick={() => void run(async () => buildProvider())}
          >
            Update provider draft
          </button>
        </div>
      </details>
      <section className={panel}>
        <h2 className="font-medium">Feature routing matrix</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-[560px] w-full text-left text-sm">
            <thead className="text-xs text-muted">
              <tr>
                <th className="pb-2">Feature</th>
                <th>Execution</th>
                <th>Typed provider flow</th>
                <th>State</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(draft?.features ?? {}).map(([f, r]) => (
                <tr key={f} className="border-t border-line">
                  <td className="py-3">
                    <button
                      className="text-accent"
                      onClick={() => {
                        setFeature(f);
                        setStrategy(r.strategy);
                        setProviders(r.providers);
                        setPolicy(r.result_policy || "all");
                      }}
                    >
                      {f}
                    </button>
                  </td>
                  <td>{r.strategy}</td>
                  <td>
                    <div className="flex flex-wrap gap-2">
                      {r.providers.map((p, i) => (
                        <span
                          key={p}
                          className="rounded border border-line bg-page px-2 py-1 text-xs"
                        >
                          {i > 0
                            ? r.strategy === "parallel"
                              ? "∥ "
                              : "→ "
                            : ""}
                          {p}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="text-muted">
                    {r.enabled ? "Enabled" : "Disabled"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <details className="mt-4 border-t border-line pt-3">
          <summary className="text-sm">Route builder</summary>
          <div className="mt-3 flex flex-wrap gap-2">
            <input
              list="feature-roles"
              aria-label="Route feature"
              className={field}
              value={feature}
              onChange={(e) => setFeature(e.target.value)}
            />
            <datalist id="feature-roles">
              {featureRoles.map((role) => (
                <option key={role} value={role} />
              ))}
            </datalist>
            <select
              aria-label="Route strategy"
              className={field}
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
            >
              {[
                "single",
                "fallback",
                "parallel",
                "sequential",
                "conditional",
              ].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            {strategy === "parallel" && (
              <>
                <select
                  aria-label="Result policy"
                  className={field}
                  value={policy}
                  onChange={(e) => setPolicy(e.target.value)}
                >
                  {["all", "first_valid", "quorum"].map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
                {policy === "quorum" && (
                  <input
                    aria-label="Quorum"
                    type="number"
                    className={field}
                    value={quorum}
                    min={1}
                    max={8}
                    onChange={(e) => setQuorum(+e.target.value)}
                  />
                )}
              </>
            )}
            <button
              className={btn}
              onClick={() => void run(async () => buildRoute())}
            >
              Update route draft
            </button>
          </div>
          <div className="mt-3 flex flex-wrap gap-3">
            {Object.keys(draft?.providers ?? {}).map((p) => (
              <label key={p} className="text-sm">
                <input
                  type="checkbox"
                  checked={providers.includes(p)}
                  onChange={(e) =>
                    setProviders((old) =>
                      e.target.checked
                        ? [...old, p]
                        : old.filter((x) => x !== p),
                    )
                  }
                />{" "}
                {p}
                {providers.includes(p) ? ` (${providers.indexOf(p) + 1})` : ""}
              </label>
            ))}
          </div>
          <p className="mt-2 text-xs text-muted">
            Selection order determines fallback/sequential order. Conditional
            builder uses the feature camera; advanced predicates stay editable
            in YAML. Live can select an existing route without changing
            defaults.
          </p>
        </details>
      </section>
      <section className="grid gap-4 xl:grid-cols-2">
        <div className={panel}>
          <label className="text-sm font-medium">
            Routing YAML
            <textarea
              aria-label="Routing YAML"
              spellCheck={false}
              className="mt-3 h-[28rem] w-full rounded-lg border border-line bg-page p-3 font-mono text-xs leading-5"
              value={text}
              onChange={(e) => edit(e.target.value)}
            />
          </label>
        </div>
        <div className={panel}>
          <h2 className="text-sm font-medium">Review draft changes</h2>
          <p className="my-3 text-xs text-muted">
            Changed sections: {changes.join(", ") || "none"}. Server validation
            enforces schema, capabilities and destination policy.
          </p>
          <pre className="max-h-[28rem] overflow-auto whitespace-pre-wrap text-xs text-ink-2">
            {changes
              .map(
                (k) =>
                  `${k}\n− ${stringify(state?.config[k])}\n+ ${stringify(draft?.[k])}`,
              )
              .join("\n")}
          </pre>
        </div>
      </section>
      <div className="flex flex-wrap gap-2">
        <button
          className={btn}
          disabled={!text || busy}
          onClick={() =>
            void run(async () => {
              const r = await api(
                "/api/config/validate",
                { yaml: text, expected_version: state?.config_version ?? 1 },
                true,
              );
              setValid(text);
              return r;
            })
          }
        >
          Validate & preview diff
        </button>
        <button
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white"
          disabled={!state?.writable || valid !== text || busy}
          onClick={() =>
            void run(async () => {
              await api(
                "/api/config/apply",
                { yaml: text, expected_version: state?.config_version },
                true,
              );
              return load();
            })
          }
        >
          Apply profile atomically
        </button>
        <select
          aria-label="Rollback version"
          className={field}
          value={rollback}
          onChange={(e) => setRollback(+e.target.value)}
        >
          {(state?.history ?? [1]).map((v) => (
            <option key={v} value={v}>
              Revision {v}
            </option>
          ))}
        </select>
        <button
          className={btn}
          disabled={!state?.writable || busy}
          onClick={() =>
            void run(async () => {
              await api(
                "/api/config/rollback",
                { version: rollback, expected_version: state?.config_version },
                true,
              );
              return load();
            })
          }
        >
          Restore version
        </button>
        <button
          className={btn}
          disabled={!state || busy}
          onClick={() =>
            void run(async () => {
              const r = await api(
                "/api/routing/dry-run",
                {
                  feature,
                  camera_id: feature.includes("camera2")
                    ? "camera2"
                    : "camera1",
                },
                true,
              );
              setTrace(r);
              return r;
            })
          }
        >
          Dry-run routing
        </button>
      </div>
      <section className="grid gap-4 lg:grid-cols-2">
        <div className={panel}>
          <h2 className="text-sm font-medium">Synthetic execution trace</h2>
          <p className="mt-1 text-xs text-muted">
            Generated text/images only. Transcription requires an explicitly
            consented audio clip. Mock results never establish live readiness.
          </p>
          <pre className="mt-3 overflow-auto whitespace-pre-wrap text-xs">
            {trace ? JSON.stringify(trace, null, 2) : "No synthetic calls yet."}
          </pre>
        </div>
        <div className={panel}>
          <h2 className="text-sm font-medium">
            Private backup status · administrator only
          </h2>
          <p className="my-2 text-xs text-muted">
            A separate private repository must run encrypted snapshots every 12
            hours and pass a clean restore. Templates do not activate backups.
          </p>
          <button
            className={btn}
            onClick={() =>
              void run(async () => {
                const r = await api(
                  "/api/admin/backup-status",
                  undefined,
                  true,
                );
                setBackup(r);
                return { loaded: true };
              })
            }
          >
            Refresh backup status
          </button>
          <pre className="mt-3 overflow-auto whitespace-pre-wrap text-xs">
            {backup ? JSON.stringify(backup, null, 2) : "Status not loaded."}
          </pre>
        </div>
      </section>
      <pre
        role="status"
        className={`${panel} overflow-auto whitespace-pre-wrap text-xs`}
      >
        {message || "Configuration results appear here."}
      </pre>
    </div>
  );
}
