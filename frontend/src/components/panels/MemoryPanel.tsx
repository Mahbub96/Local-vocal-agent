import { useCallback, useState } from "react";
import { Card } from "../common/Card";
import { CardHeader } from "../common/CardHeader";
import type { Profile } from "../../types/ui";

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

  const cancel = useCallback(() => {
    setEditing(false);
  }, []);

  const apply = useCallback(
    (patch: Partial<Profile>) => {
      setForm((prev) => ({ ...prev, ...patch }));
    },
    [],
  );

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
      };
      await onSave(next);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }, [form, onSave, prefsText]);

  const p = profile;
  const NA = "—";

  return (
    <Card className="memory-card">
      <CardHeader
        title="Memory"
        subtitle="View All"
        action={
          editing ? (
            <div className="memory-actions">
              <button type="button" className="link-btn" onClick={cancel} disabled={saving}>
                Cancel
              </button>
              <button type="button" className="link-btn link-btn--primary" onClick={() => void save()} disabled={saving}>
                {saving ? "Saving" : "Save"}
              </button>
            </div>
          ) : (
            <button type="button" className="link-btn link-btn--primary" onClick={startEdit}>
              Edit
            </button>
          )
        }
      />
      <p className="memory-kicker">Known about you.</p>
      {editing ? (
        <div className="memory-form" role="form" aria-label="User profile">
          <label className="memory-field">
            <span>Name</span>
            <input
              value={form.name ?? ""}
              onChange={(e) => apply({ name: e.target.value || null })}
            />
          </label>
          <label className="memory-field">
            <span>Language</span>
            <input
              value={form.language ?? ""}
              onChange={(e) => apply({ language: e.target.value || null })}
            />
          </label>
          <label className="memory-field">
            <span>Location</span>
            <input
              value={form.location ?? ""}
              onChange={(e) => apply({ location: e.target.value || null })}
            />
          </label>
          <label className="memory-field">
            <span>Profession</span>
            <input
              value={form.profession ?? ""}
              onChange={(e) => apply({ profession: e.target.value || null })}
            />
          </label>
          <label className="memory-field">
            <span>Working on</span>
            <input
              value={form.project ?? ""}
              onChange={(e) => apply({ project: e.target.value || null })}
            />
          </label>
          <label className="memory-field">
            <span>Preferences</span>
            <input
              value={prefsText}
              onChange={(e) => setPrefsText(e.target.value)}
              placeholder="topic A, topic B"
            />
          </label>
        </div>
      ) : (
        <ul className="memory-list">
          <li>
            <span className="memory-k">Name</span> {p?.name || NA}
          </li>
          <li>
            <span className="memory-k">Language</span> {p?.language || NA}
          </li>
          <li>
            <span className="memory-k">Location</span> {p?.location || NA}
          </li>
          <li>
            <span className="memory-k">Profession</span> {p?.profession || NA}
          </li>
          <li>
            <span className="memory-k">Working on</span> {p?.project || NA}
          </li>
          <li>
            <span className="memory-k">Preference</span>{" "}
            {p?.preferences?.length ? p.preferences.join(", ") : NA}
          </li>
        </ul>
      )}
    </Card>
  );
}
