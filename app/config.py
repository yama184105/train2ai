from pathlib import Path

USAGE_FILE = Path("usage_log.json")

PROFILE_FILE = Path("users/default/profile.json")
COACH_NOTES_FILE = Path("users/default/coach_notes.json")

FREE_TOTAL_LIMIT = 3
FREE_MAX_DAYS = 7
PRO_MAX_DAYS = 365

ALLOWED_GARMIN_DATA = {"daily_summary", "sleep", "workouts"}
ALLOWED_SOURCES = {"garmin", "strava"}
ALLOWED_MODES = {"summary", "analysis"}
ALLOWED_SPORTS = {"run", "ride"}
ANALYSIS_RECENT_CHOICES = {3, 5, 10}
TARGET_STREAM_POINTS = 200
SCHEMA_VERSION = "2.0"
