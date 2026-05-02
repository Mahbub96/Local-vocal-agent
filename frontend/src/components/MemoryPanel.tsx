import { useCallback, useState } from "react";
import type { Profile } from "../types/ui";

type MemoryPanelProps = {
  profile: Profile | null;
  onSave: (next: Profile) => Promise<void>;
};

const emptyProfile: Profile = {
  name: null,
  language: null,
  location: null,
  profession: null,
  project: null,
  preferences: [],
};

export function MemoryPanel({ profile, onSave }: MemoryPanelProps) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<Profile>(profile ?? emptyProfile);
  const [prefsText, setPrefsText] = useState((profile?.preferences ?? []).join(", "));

  const startEdit = useCallback(() => {
    const p = profile ?? emptyProfile;
    setForm({
      name: p.name,
      language: p.language,
      location: p.location,
      profession: p.profession,
      project: p.project,
      preferences: p.preferences ?? [],
      tts_playback_speed: p.tts_playback_speed ?? null,
      assistant_wake_name: p.assistant_wake_name ?? null,
      voice_listen_paused: p.voice_listen_paused === true,
    });
    setPrefsText((p.preferences ?? []).join(", "));
    setEditing(true);
  }, [profile]);

  const cancel = useCallback(() => setEditing(false), []);

  const apply = useCallback((patch: Partial<Profile>) => {
    setForm((prev) => ({ ...prev, ...patch }));
  }, []);

  const save = useCallback(async () => {
    const prefs = prefsText
      .split(/[,;]+/)
      .map((p) => p.trim())
      .filter(Boolean);
    setSaving(true);
    try {
      const next: Profile = {
        ...form,
        preferences: prefs,
        tts_playback_speed: form.tts_playback_speed ?? profile?.tts_playback_speed ?? null,
        assistant_wake_name: form.assistant_wake_name ?? profile?.assistant_wake_name ?? null,
        voice_listen_paused: form.voice_listen_paused === true,
        voice_wake_session_active:
          form.voice_listen_paused === true ? Boolean(profile?.voice_wake_session_active) : false,
      };
      await onSave(next);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }, [form, onSave, prefsText]);

  const p = profile;
  const NA = "—";
  const rows = [
    { label: "Name", value: p?.name || NA },
    { label: "Language", value: p?.language || NA },
    { label: "Location", value: p?.location || NA },
    { label: "Profession", value: p?.profession || NA },
    { label: "Working on", value: p?.project || NA },
    { label: "Preference", value: p?.preferences?.length ? p.preferences.join(", ") : NA },
    {
      label: "Speech speed",
      value:
        p?.tts_playback_speed != null && Number.isFinite(p.tts_playback_speed)
          ? `${p.tts_playback_speed.toFixed(2)}×`
          : NA,
    },
    { label: "Wake name", value: p?.assistant_wake_name?.trim() || NA },
    { label: "Voice silent", value: p?.voice_listen_paused ? "On" : "Off" },
    { label: "Wake follow-up", value: p?.voice_wake_session_active ? "Active" : NA },
  ] as const;

  return (
    <section
      className="aurora-glass rounded-3xl border border-white/12 bg-[linear-gradient(180deg,rgba(18,24,44,0.92),rgba(10,14,28,0.95))] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_0_20px_rgba(0,0,0,0.22)] md:p-5"
      aria-label="Memory"
    >
      <div className="mb-4 flex items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold tracking-tight text-white">Known about you</h3>
          <p className="mt-0.5 text-[11px] text-white/45">Persistent profile context used by chat and voice.</p>
          <p className="sr-only">Memory</p>
        </div>
        {editing ? (
          <div className="flex gap-2 text-xs">
            <button type="button" className="text-white/50 underline-offset-4 hover:text-white" onClick={cancel} disabled={saving}>
              Cancel
            </button>
            <button
              type="button"
              className="rounded-lg bg-purple-500/25 px-2.5 py-1 font-medium text-purple-100 ring-1 ring-purple-400/35 hover:bg-purple-500/35"
              onClick={() => void save()}
              disabled={saving}
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-4 text-xs font-medium">
            <button
              type="button"
              onClick={startEdit}
              className="text-xs text-white/55 underline-offset-4 transition hover:text-white"
            >
              View All
            </button>
            <button
              type="button"
              onClick={startEdit}
              className="rounded-xl border border-cyan-300/25 bg-cyan-300/10 px-2.5 py-1 text-xs text-cyan-100/95 ring-1 ring-cyan-200/15 transition hover:bg-cyan-300/14"
            >
              Edit
            </button>
          </div>
        )}
      </div>

      {editing ? (
        <div className="space-y-3 text-sm" role="form" aria-label="User profile">
          <label className="block space-y-1">
            <span className="aurora-field-label">Name</span>
            <input
              className="aurora-field"
              value={form.name ?? ""}
              onChange={(e) => apply({ name: e.target.value || null })}
            />
          </label>
          <label className="block space-y-1">
            <span className="aurora-field-label">Language</span>
            <input
              className="aurora-field"
              value={form.language ?? ""}
              onChange={(e) => apply({ language: e.target.value || null })}
            />
          </label>
          <label className="block space-y-1">
            <span className="aurora-field-label">Location</span>
            <input
              className="aurora-field"
              value={form.location ?? ""}
              onChange={(e) => apply({ location: e.target.value || null })}
            />
          </label>
          <label className="block space-y-1">
            <span className="aurora-field-label">Profession</span>
            <input
              className="aurora-field"
              value={form.profession ?? ""}
              onChange={(e) => apply({ profession: e.target.value || null })}
            />
          </label>
          <label className="block space-y-1">
            <span className="aurora-field-label">Working on</span>
            <input
              className="aurora-field"
              value={form.project ?? ""}
              onChange={(e) => apply({ project: e.target.value || null })}
            />
          </label>
          <label className="block space-y-1">
            <span className="aurora-field-label">Preferences</span>
            <input
              className="aurora-field"
              value={prefsText}
              onChange={(e) => setPrefsText(e.target.value)}
              placeholder="topic A, topic B"
            />
          </label>
          <label className="block space-y-1">
            <span className="aurora-field-label">Speech speed (playback)</span>
            <input
              className="aurora-field"
              type="number"
              step={0.05}
              min={0.85}
              max={2}
              value={form.tts_playback_speed ?? ""}
              placeholder="default (server)"
              onChange={(e) => {
                const v = e.target.value.trim();
                if (v === "") {
                  apply({ tts_playback_speed: null });
                  return;
                }
                const n = Number(v);
                apply({ tts_playback_speed: Number.isFinite(n) ? n : null });
              }}
            />
            <span className="text-xs text-aurora-fg-muted">1.0 = normal; higher = faster. You can also say “speak slightly faster” in chat.</span>
          </label>
          <label className="block space-y-1">
            <span className="aurora-field-label">Wake name (voice)</span>
            <input
              className="aurora-field"
              value={form.assistant_wake_name ?? ""}
              onChange={(e) => apply({ assistant_wake_name: e.target.value.trim() || null })}
              placeholder="e.g. Aurora"
            />
            <span className="text-xs text-aurora-fg-muted">
              Use at least 2 letters (single letters match inside normal words and break wake detection). When silent mode
              is on, start speech with this name, or say “call yourself Luna” in chat or voice.
            </span>
          </label>
          <label className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-white/10 bg-white/3 px-3 py-2.5">
            <input
              type="checkbox"
              className="mt-0.5 size-4 shrink-0 rounded border-white/25 accent-cyan-500"
              checked={Boolean(form.voice_listen_paused)}
              onChange={(e) => apply({ voice_listen_paused: e.target.checked })}
            />
            <span className="space-y-0.5">
              <span className="block text-sm font-medium text-aurora-fg">Voice silent mode (wake name required)</span>
              <span className="text-xs text-aurora-fg-muted">
                When on, voice is ignored unless your wake name appears in the clip — same as saying “stop listening”.
                Turn off here or say “resume listening”.
              </span>
            </span>
          </label>
        </div>
      ) : (
        <ul className="grid gap-2.5">
          {rows.map((row) => (
            <li
              key={row.label}
              className="grid grid-cols-[6.2rem_minmax(0,1fr)] items-center gap-2 rounded-xl border border-white/8 bg-white/2 px-2.5 py-2"
            >
              <span className="text-[11px] font-medium uppercase tracking-[0.06em] text-aurora-fg-muted/90">{row.label}</span>
              <span className="truncate text-sm font-medium text-white/92">{row.value}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
