"""Wake name + listen/silent mode for voice (and text) — stored on user profile."""

from __future__ import annotations

import re
from typing import Any

# Ask assistant to stay silent until wake name is used (voice gate).
# Includes common STT variants (e.g. "quite" for "quiet", "be quiet").
#
# IMPORTANT: Do **not** use bare `don't listen` / `do not listen` — they match normal sentences
# ("I don't listen to jazz") and flip silent mode on by accident, so voice then looks "dead"
# until the user says the wake name or resumes.
_LISTEN_PAUSE = re.compile(
    r"(?i)(?:"
    r"\bkeep\s+(?:quiet|silent|quite)\b|"
    r"\bstay\s+quiet\b|"
    r"\bplease\s+be\s+quiet\b|"
    r"\bbe\s+quiet\b|"
    r"\bstop\s+listening\b|"
    r"\b(?:don'?t|do\s+not)\s+listen\s+to\s+me\b|"
    r"\bbe\s+silent\s+until\b|"
    r"\bquiet\s+until\b|"
    r"\bsilence\s+until\b|"
    r"\bwait\s+until\s+I\s+(?:say|call|ask)\b"
    r")"
)

_LISTEN_RESUME = re.compile(
    r"(?i)(?:"
    r"\byou\s+can\s+listen\s+again\b|"
    r"\bresume\s+listen(?:ing)?\b|"
    r"\bstart\s+listening\s+again\b|"
    r"\bI'?m\s+ready\s+to\s+talk\b|"
    r"\bgo\s+back\s+to\s+listening\b|"
    r"\blisten\s+again\b|"
    r"\bturn\s+off\s+(?:silent|quiet)\s+mode\b|"
    r"\b(?:disable|exit)\s+silent\s+mode\b"
    r")"
)

# End the “talking with the assistant” turn (still in quiet mode; say resume to listen to everything again).
_STOP_WAKE_SESSION = re.compile(
    r"(?i)(?:"
    r"^\s*stop\s*[.!?\s]*$|"
    r"^\s*enough\s*[.!?\s]*$|"
    r"\b(?:ok(?:ay)?[,.\s]+)?(?:that'?s\s+enough|that'?s\s+all|we(?:'re|\s+are)\s+done|"
    r"end\s+(?:the\s+)?(?:conversation|this)|you\s+can\s+stop|stop\s+now|"
    r"thank\s+you(?:\s*,)?\s*(?:that'?s\s+all)?|(?:go\s+to\s+)?sleep)\b"
    r")"
)

# Set wake / assistant name (text or voice).
_WAKE_NAME_SET = re.compile(
    r"(?i)(?:wake\s*(?:word|name)\s+is\s+|call\s+(?:yourself|you)\s+|I\s*(?:'ll|will)\s+call\s+you\s+|"
    r"your\s+name\s+is\s+|I\s*'?m\s+going\s+to\s+call\s+you\s+|assistant\s+name\s+is\s+)"
    r"([A-Za-z][A-Za-z0-9\-]{0,39})"
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def detect_listen_pause_command(text: str) -> bool:
    return bool(_LISTEN_PAUSE.search(text))


def detect_listen_resume_command(text: str) -> bool:
    return bool(_LISTEN_RESUME.search(text))


def detect_stop_wake_session_command(text: str) -> bool:
    """User is done with back-and-forth after calling by name (still in quiet mode)."""
    return bool(_STOP_WAKE_SESSION.search(text))


def extract_wake_name_assignment(text: str) -> str | None:
    m = _WAKE_NAME_SET.search(text)
    if not m:
        return None
    name = (m.group(1) or "").strip()
    return name or None


def transcript_contains_wake(transcript: str, wake_name: str) -> bool:
    """True if the user addressed the assistant by wake name.

    Short names (≤3 chars after trim) must match as a **whole word**, otherwise a wake
    like ``a`` matches inside almost every English sentence and the UI/session state breaks.
    """
    if not wake_name.strip():
        return True
    w = _norm(wake_name)
    t = _norm(transcript)
    if not w:
        return True
    # Whole-word tokens only — avoids "a" in "and", "at", "that", etc.
    if len(w) <= 3:
        tokens = re.findall(r"[a-z0-9]+", t)
        if w in tokens:
            return True
        return t.startswith(w + " ") or t.startswith(w + ",") or t.startswith(w + ".") or t == w
    if w in t:
        return True
    return t.startswith(w) or t.startswith(w + ",")


def strip_wake_prefix(transcript: str, wake_name: str) -> str:
    t = transcript.strip()
    if not wake_name.strip():
        return t
    pattern = re.compile(
        r"^\s*" + re.escape(wake_name.strip()) + r"[,\s!?.:;\"']*\s*",
        re.IGNORECASE,
    )
    out = pattern.sub("", t, count=1).strip()
    return out if out else t


def is_meta_voice_control_utterance(text: str) -> bool:
    """Do not apply wake-only skip to control phrases (pause / resume / rename / stop session)."""
    if detect_listen_pause_command(text) or detect_listen_resume_command(text):
        return True
    if detect_stop_wake_session_command(text):
        return True
    if extract_wake_name_assignment(text):
        return True
    return False


def merge_voice_listen_profile(profile: dict[str, Any], message: str) -> tuple[dict[str, Any], bool]:
    """Apply pause/resume/wake-name/stop-session phrases. Returns (merged_profile, changed)."""
    merged = dict(profile)
    changed = False

    if detect_stop_wake_session_command(message):
        if merged.get("voice_wake_session_active"):
            merged["voice_wake_session_active"] = False
            changed = True

    had_listen_pause = detect_listen_pause_command(message)
    if had_listen_pause:
        merged["voice_listen_paused"] = True
        merged["voice_wake_session_active"] = False
        changed = True

    if detect_listen_resume_command(message):
        merged["voice_listen_paused"] = False
        merged["voice_wake_session_active"] = False
        changed = True

    wake = extract_wake_name_assignment(message)
    if wake:
        merged["assistant_wake_name"] = wake
        changed = True

    wname = merged.get("assistant_wake_name")
    if isinstance(wname, str) and len(wname.strip()) < 2:
        merged.pop("assistant_wake_name", None)
        if merged.get("voice_wake_session_active"):
            merged["voice_wake_session_active"] = False
            changed = True
        wname = merged.get("assistant_wake_name")

    # After calling the assistant by name in quiet mode, stay “live” until stop / keep quiet / resume.
    if (
        merged.get("voice_listen_paused")
        and not had_listen_pause
        and isinstance(wname, str)
        and len(wname.strip()) >= 2
        and transcript_contains_wake(message, wname)
        and not detect_stop_wake_session_command(message)
    ):
        merged["voice_wake_session_active"] = True
        changed = True

    return merged, changed


def should_drop_voice_for_wake_gate(
    profile_before: dict[str, Any],
    transcript: str,
) -> bool:
    """
    If user previously asked for silent mode, ignore voice that does not mention the wake name.
    Control utterances (pause/resume/rename) are never dropped.
    """
    if not profile_before.get("voice_listen_paused"):
        return False
    if profile_before.get("voice_wake_session_active"):
        return False
    if detect_stop_wake_session_command(transcript):
        return False
    wake = profile_before.get("assistant_wake_name")
    if not isinstance(wake, str) or not wake.strip():
        return False
    if is_meta_voice_control_utterance(transcript):
        return False
    return not transcript_contains_wake(transcript, wake)
