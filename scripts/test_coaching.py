"""
Smoke test for coaching persistence helpers.

Uses a temporary directory so the real users/default/ files are never touched.
Run from the project root:

    python scripts/test_coaching.py
"""
import tempfile
from pathlib import Path

import app.utils.coaching as coaching


def run():
    with tempfile.TemporaryDirectory() as tmp:
        # Redirect file paths to temp dir for the duration of this script.
        # `from app.config import ...` binds names in the coaching module's
        # own namespace, so patching them here works correctly.
        coaching.PROFILE_FILE = Path(tmp) / "profile.json"
        coaching.COACH_NOTES_FILE = Path(tmp) / "coach_notes.json"

        # --- profile ---

        profile = coaching.load_profile()
        assert profile == {"name": None, "sport": None, "goal": None, "notes": None}, (
            f"unexpected default: {profile}"
        )
        print("PASS  load_profile returns default when file is missing")

        coaching.save_profile({"name": "Alice", "sport": "run", "goal": "sub-20 5k", "notes": None})
        reloaded = coaching.load_profile()
        assert reloaded["name"] == "Alice", f"unexpected value: {reloaded}"
        assert reloaded["sport"] == "run", f"unexpected value: {reloaded}"
        print("PASS  save_profile / load_profile round-trip")

        # --- coach notes ---

        notes = coaching.load_coach_notes()
        assert notes == {"entries": []}, f"unexpected default: {notes}"
        print("PASS  load_coach_notes returns default when file is missing")

        coaching.save_coach_notes({"entries": [{"date": "2024-01-01", "text": "Good session"}]})
        reloaded_notes = coaching.load_coach_notes()
        assert reloaded_notes["entries"][0]["text"] == "Good session", (
            f"unexpected value: {reloaded_notes}"
        )
        print("PASS  save_coach_notes / load_coach_notes round-trip")

    print("\nAll coaching persistence checks passed.")


if __name__ == "__main__":
    run()
