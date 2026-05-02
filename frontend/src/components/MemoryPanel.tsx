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
      const next: Profile = { ...form, preferences: prefs };
      await onSave(next);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }, [form, onSave, prefsText]);

  const p = profile;
  const NA = "—";

  return (
    <section className="aurora-glass rounded-3xl border border-white/10 p-4 md:p-5" aria-label="Memory">
      <div className="mb-4 flex items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold tracking-tight text-white">Known about you</h3>
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
              className="text-white/55 underline-offset-4 transition hover:text-white"
            >
              View All
            </button>
            <button
              type="button"
              onClick={startEdit}
              className="rounded-lg bg-white/6 px-2.5 py-1 text-cyan-200/90 ring-1 ring-white/10 transition hover:bg-white/10"
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
        </div>
      ) : (
        <ul className="space-y-2.5 text-sm">
          <li className="flex flex-col gap-0.5 sm:flex-row sm:gap-2">
            <span className="min-w-[5.5rem] text-xs text-aurora-fg-muted">Name</span>
            <span className="text-aurora-fg/85">{p?.name || NA}</span>
          </li>
          <li className="flex flex-col gap-0.5 sm:flex-row sm:gap-2">
            <span className="min-w-[5.5rem] text-xs text-aurora-fg-muted">Language</span>
            <span className="text-aurora-fg/85">{p?.language || NA}</span>
          </li>
          <li className="flex flex-col gap-0.5 sm:flex-row sm:gap-2">
            <span className="min-w-[5.5rem] text-xs text-aurora-fg-muted">Location</span>
            <span className="text-aurora-fg/85">{p?.location || NA}</span>
          </li>
          <li className="flex flex-col gap-0.5 sm:flex-row sm:gap-2">
            <span className="min-w-[5.5rem] text-xs text-aurora-fg-muted">Profession</span>
            <span className="text-aurora-fg/85">{p?.profession || NA}</span>
          </li>
          <li className="flex flex-col gap-0.5 sm:flex-row sm:gap-2">
            <span className="min-w-[5.5rem] text-xs text-aurora-fg-muted">Working on</span>
            <span className="text-aurora-fg/85">{p?.project || NA}</span>
          </li>
          <li className="flex flex-col gap-0.5 sm:flex-row sm:gap-2">
            <span className="min-w-[5.5rem] text-xs text-aurora-fg-muted">Preference</span>
            <span className="text-aurora-fg/85">{p?.preferences?.length ? p.preferences.join(", ") : NA}</span>
          </li>
        </ul>
      )}
    </section>
  );
}
