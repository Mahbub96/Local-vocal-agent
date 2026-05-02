/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useMemo, useState } from "react";
import type { Profile } from "../types/ui";
import type { VoiceCaptureMode } from "../hooks/useVoiceCapture";

type SettingsWorkspaceProps = {
  profile: Profile | null;
  onSaveProfile: (next: Profile) => Promise<void>;
  captureMode: VoiceCaptureMode;
  onCaptureModeChange: (mode: VoiceCaptureMode) => void;
};

const EMPTY: Profile = {
  name: null,
  language: null,
  location: null,
  profession: null,
  project: null,
  preferences: [],
};

export function SettingsWorkspace({
  profile,
  onSaveProfile,
  captureMode,
  onCaptureModeChange,
}: SettingsWorkspaceProps) {
  const [form, setForm] = useState<Profile>(profile ?? EMPTY);
  const [prefsText, setPrefsText] = useState((profile?.preferences ?? []).join(", "));
  const [saving, setSaving] = useState(false);
  const [savedNote, setSavedNote] = useState("");

  useEffect(() => {
    const p = profile ?? EMPTY;
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
      voice_wake_session_active: p.voice_wake_session_active === true,
    });
    setPrefsText((p.preferences ?? []).join(", "));
  }, [profile]);

  const dirty = useMemo(() => {
    const p = profile ?? EMPTY;
    return (
      (form.name ?? "") !== (p.name ?? "") ||
      (form.language ?? "") !== (p.language ?? "") ||
      (form.location ?? "") !== (p.location ?? "") ||
      (form.profession ?? "") !== (p.profession ?? "") ||
      (form.project ?? "") !== (p.project ?? "") ||
      prefsText.trim() !== (p.preferences ?? []).join(", ").trim() ||
      (form.tts_playback_speed ?? null) !== (p.tts_playback_speed ?? null) ||
      (form.assistant_wake_name ?? "") !== (p.assistant_wake_name ?? "") ||
      Boolean(form.voice_listen_paused) !== Boolean(p.voice_listen_paused)
    );
  }, [form, prefsText, profile]);

  const save = async () => {
    const prefs = prefsText
      .split(/[,;]+/)
      .map((p) => p.trim())
      .filter(Boolean);
    setSaving(true);
    setSavedNote("");
    try {
      await onSaveProfile({
        ...form,
        preferences: prefs,
        voice_wake_session_active: form.voice_listen_paused
          ? Boolean(profile?.voice_wake_session_active)
          : false,
      });
      setSavedNote("Settings saved.");
      window.setTimeout(() => setSavedNote(""), 2200);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="aurora-glass flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 p-3 sm:p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-white">Settings</h3>
          <p className="text-xs text-white/50">
            Manage voice behavior and persistent assistant preferences.
          </p>
        </div>
        {savedNote ? (
          <span className="rounded-lg border border-emerald-400/25 bg-emerald-500/10 px-2 py-1 text-[11px] text-emerald-200">
            {savedNote}
          </span>
        ) : null}
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-y-auto md:grid-cols-2">
        <label className="block space-y-1">
          <span className="aurora-field-label">Name</span>
          <input className="aurora-field" value={form.name ?? ""} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value || null }))} />
        </label>
        <label className="block space-y-1">
          <span className="aurora-field-label">Language</span>
          <input className="aurora-field" value={form.language ?? ""} onChange={(e) => setForm((f) => ({ ...f, language: e.target.value || null }))} />
        </label>
        <label className="block space-y-1">
          <span className="aurora-field-label">Location</span>
          <input className="aurora-field" value={form.location ?? ""} onChange={(e) => setForm((f) => ({ ...f, location: e.target.value || null }))} />
        </label>
        <label className="block space-y-1">
          <span className="aurora-field-label">Profession</span>
          <input className="aurora-field" value={form.profession ?? ""} onChange={(e) => setForm((f) => ({ ...f, profession: e.target.value || null }))} />
        </label>
        <label className="block space-y-1">
          <span className="aurora-field-label">Working on</span>
          <input className="aurora-field" value={form.project ?? ""} onChange={(e) => setForm((f) => ({ ...f, project: e.target.value || null }))} />
        </label>
        <label className="block space-y-1">
          <span className="aurora-field-label">Preferences</span>
          <input className="aurora-field" value={prefsText} onChange={(e) => setPrefsText(e.target.value)} placeholder="comma-separated" />
        </label>
        <label className="block space-y-1">
          <span className="aurora-field-label">Speech speed</span>
          <input
            className="aurora-field"
            type="number"
            min={0.85}
            max={2}
            step={0.05}
            value={form.tts_playback_speed ?? ""}
            onChange={(e) => {
              const v = e.target.value.trim();
              if (!v) return setForm((f) => ({ ...f, tts_playback_speed: null }));
              const n = Number(v);
              setForm((f) => ({ ...f, tts_playback_speed: Number.isFinite(n) ? n : null }));
            }}
          />
        </label>
        <label className="block space-y-1">
          <span className="aurora-field-label">Wake name</span>
          <input className="aurora-field" value={form.assistant_wake_name ?? ""} onChange={(e) => setForm((f) => ({ ...f, assistant_wake_name: e.target.value.trim() || null }))} />
        </label>

        <div className="rounded-xl border border-white/10 bg-white/3 px-3 py-2.5 md:col-span-2">
          <p className="mb-2 text-sm font-medium text-white/90">Voice capture mode</p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onCaptureModeChange("always")}
              className={`rounded-lg px-3 py-1.5 text-xs ${
                captureMode === "always"
                  ? "border border-cyan-300/30 bg-cyan-400/12 text-cyan-100"
                  : "border border-white/10 bg-white/5 text-white/65"
              }`}
            >
              Hands-free
            </button>
            <button
              type="button"
              onClick={() => onCaptureModeChange("push")}
              className={`rounded-lg px-3 py-1.5 text-xs ${
                captureMode === "push"
                  ? "border border-cyan-300/30 bg-cyan-400/12 text-cyan-100"
                  : "border border-white/10 bg-white/5 text-white/65"
              }`}
            >
              Push-to-talk
            </button>
          </div>
        </div>

        <label className="flex items-start gap-2.5 rounded-xl border border-white/10 bg-white/3 px-3 py-2.5 md:col-span-2">
          <input
            type="checkbox"
            className="mt-0.5 size-4 rounded border-white/25 accent-cyan-500"
            checked={Boolean(form.voice_listen_paused)}
            onChange={(e) =>
              setForm((f) => ({ ...f, voice_listen_paused: e.target.checked }))
            }
          />
          <span className="text-sm text-white/85">
            Voice silent mode (require wake name in voice clips)
          </span>
        </label>
      </div>

      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving || !dirty}
          className="rounded-xl border border-cyan-300/30 bg-cyan-400/12 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/18 disabled:opacity-45"
        >
          {saving ? "Saving..." : "Save settings"}
        </button>
      </div>
    </section>
  );
}
