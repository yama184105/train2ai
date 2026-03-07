from __future__ import annotations

import json

from app.config import COACH_NOTES_FILE, PROFILE_FILE


def load_profile() -> dict:
    if PROFILE_FILE.exists():
        try:
            data = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {"name": None, "sport": None, "goal": None, "notes": None}


def save_profile(data: dict) -> None:
    PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_coach_notes() -> dict:
    if COACH_NOTES_FILE.exists():
        try:
            data = json.loads(COACH_NOTES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {"entries": []}


def save_coach_notes(data: dict) -> None:
    COACH_NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    COACH_NOTES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_coach_prompt(context: dict) -> str:
    profile = context.get("profile") or {}
    coach_notes = context.get("coach_notes") or {}
    recent_summary = context.get("recent_summary") or {}

    lines: list[str] = []

    # Athlete profile
    lines.append("## Athlete Profile")
    lines.append(f"Name:  {profile.get('name') or 'Unknown'}")
    lines.append(f"Sport: {profile.get('sport') or 'Unknown'}")
    lines.append(f"Goal:  {profile.get('goal') or 'Not set'}")
    if profile.get("notes"):
        lines.append(f"Notes: {profile['notes']}")

    # Coaching notes
    lines.append("")
    lines.append("## Coaching Notes")
    entries = coach_notes.get("entries") or []
    if entries:
        for entry in entries:
            date = entry.get("date") or "Unknown date"
            text = entry.get("text") or ""
            lines.append(f"- [{date}] {text}")
    else:
        lines.append("No coaching notes recorded yet.")

    # Recent training summary
    lines.append("")
    lines.append("## Recent Training Summary")
    source = recent_summary.get("source")
    period_days = recent_summary.get("period_days")
    observations = recent_summary.get("observations") or []

    if source:
        lines.append(f"Source:  {source}")
    if period_days is not None:
        lines.append(f"Period:  {period_days} days")
    if observations:
        for obs in observations:
            lines.append(f"- {obs}")
    else:
        lines.append("No recent training data loaded.")

    return "\n".join(lines)


def recommend_next_workout(context: dict) -> dict:
    _prompt = (
        "You are a running / triathlon coach. Recommend the next workout.\n\n"
        + build_coach_prompt(context)
    )
    # AI call will replace this mock once the API is wired in.
    return {
        "type": "easy run",
        "duration_minutes": 45,
        "target_pace": "6:00 min/km",
        "reason": "Mock recommendation — AI not connected yet.",
    }


def build_coaching_context() -> dict:
    return {
        "profile": load_profile(),
        "coach_notes": load_coach_notes(),
        "recent_summary": {
            "source": None,
            "period_days": None,
            "observations": [],
        },
    }
