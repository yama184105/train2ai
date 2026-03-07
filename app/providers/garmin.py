import json
import os
from datetime import datetime, timezone
from fastapi import HTTPException

from app.config import ALLOWED_GARMIN_DATA
from app.utils.dates import parse_iso_like_datetime


def normalize_included_data(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        if value in ALLOWED_GARMIN_DATA and value not in cleaned:
            cleaned.append(value)
    return cleaned


def is_daily_summary_file(filename: str) -> bool:
    lower = filename.lower()
    return lower.startswith("udsfile_") and lower.endswith(".json")


def is_sleep_file(filename: str) -> bool:
    return filename.lower().endswith("_sleepdata.json")


def is_workout_file(filename: str) -> bool:
    lower = filename.lower()
    return "summarizedactivities" in lower and lower.endswith(".json")


def scan_garmin_files(root_dir: str) -> dict[str, list[str]]:
    uds_files: list[str] = []
    sleep_files: list[str] = []
    workout_files: list[str] = []

    for root, _, files in os.walk(root_dir):
        for name in files:
            path = os.path.join(root, name)
            if is_daily_summary_file(name):
                uds_files.append(path)
            elif is_sleep_file(name):
                sleep_files.append(path)
            elif is_workout_file(name):
                workout_files.append(path)

    return {
        "daily_summary": sorted(uds_files),
        "sleep": sorted(sleep_files),
        "workouts": sorted(workout_files),
    }


def collect_daily_summary(uds_files: list[str], start, end) -> list[dict]:
    results: list[dict] = []
    for file_path in uds_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            date_str = item.get("calendarDate")
            if not date_str:
                continue
            try:
                day = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue
            if not (start <= day <= end):
                continue
            dist = item.get("totalDistanceMeters")
            results.append(
                {
                    "date": date_str,
                    "steps": item.get("totalSteps"),
                    "total_calories": item.get("totalKilocalories"),
                    "active_calories": item.get("activeKilocalories"),
                    "distance_km": round(dist / 1000, 2) if dist is not None else None,
                    "resting_hr": item.get("restingHeartRate"),
                }
            )
    return sorted(results, key=lambda x: x["date"])


def collect_sleep(sleep_files: list[str], start, end) -> list[dict]:
    results: list[dict] = []
    for file_path in sleep_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            date_str = item.get("calendarDate")
            if not date_str:
                continue
            try:
                day = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue
            if not (start <= day <= end):
                continue
            results.append(
                {
                    "date": date_str,
                    "sleep_start": parse_iso_like_datetime(item.get("sleepStartTimestampGMT")),
                    "sleep_end": parse_iso_like_datetime(item.get("sleepEndTimestampGMT")),
                    "deep_sleep_min": round((item.get("deepSleepSeconds") or 0) / 60),
                    "light_sleep_min": round((item.get("lightSleepSeconds") or 0) / 60),
                    "rem_sleep_min": round((item.get("remSleepSeconds") or 0) / 60),
                }
            )
    return sorted(results, key=lambda x: x["date"])


def extract_workout_activity_list(data):
    if isinstance(data, list):
        if data and isinstance(data[0], dict) and "summarizedActivitiesExport" in data[0]:
            nested = data[0].get("summarizedActivitiesExport")
            if isinstance(nested, list):
                return nested
        return data
    if isinstance(data, dict):
        nested = data.get("summarizedActivitiesExport")
        if isinstance(nested, list):
            return nested
    return []


def collect_workouts(workout_files: list[str], start, end) -> list[dict]:
    results: list[dict] = []
    for file_path in workout_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        activities = extract_workout_activity_list(data)
        for act in activities:
            if not isinstance(act, dict):
                continue
            start_time = act.get("startTimeLocal")
            if not isinstance(start_time, (int, float)):
                continue
            activity_date = datetime.fromtimestamp(start_time / 1000, tz=timezone.utc).date()
            if not (start <= activity_date <= end):
                continue
            dist = act.get("distance")
            dur = act.get("duration")
            results.append(
                {
                    "date": activity_date.isoformat(),
                    "sport": act.get("sportType"),
                    # Keep the existing normalization requested by the user.
                    "distance_km": round(dist / 100000, 2) if dist is not None else None,
                    "duration_min": round(dur / 60000, 1) if dur is not None else None,
                    "avg_hr": act.get("avgHr"),
                    "max_hr": act.get("maxHr"),
                }
            )
    return sorted(results, key=lambda x: x["date"])


def validate_detected_files(found_files: dict[str, list[str]], selected: list[str]) -> None:
    total_found = sum(len(v) for v in found_files.values())
    if total_found == 0:
        raise HTTPException(
            status_code=400,
            detail="No supported Garmin data files were found in this ZIP. Please upload the official Garmin account export ZIP.",
        )

    missing = [name for name in selected if not found_files.get(name)]
    if missing:
        names = ", ".join(missing)
        raise HTTPException(
            status_code=400,
            detail=f"The uploaded ZIP does not contain the selected data type(s): {names}.",
        )


def validate_collected_results(result_map: dict[str, list], selected: list[str], start_date_str: str, end_date_str: str) -> None:
    empty_selected = [name for name in selected if len(result_map.get(name, [])) == 0]

    if len(empty_selected) == len(selected):
        names = ", ".join(selected)
        raise HTTPException(
            status_code=400,
            detail=(
                f"No records were found for the selected date range ({start_date_str} to {end_date_str}) for: {names}."
            ),
        )

    # Keep the user's preferred behavior: workouts=0 should not fail if it is the only missing selected type.
    only_missing_workouts = empty_selected == ["workouts"]
    if empty_selected and not only_missing_workouts:
        names = ", ".join(empty_selected)
        raise HTTPException(
            status_code=400,
            detail=(
                f"The ZIP was valid, but no records were found in the selected date range ({start_date_str} to {end_date_str}) for: {names}."
            ),
        )


def build_output(plan: str, start_date: str, end_date: str, selected: list[str], daily_summary: list[dict], sleep: list[dict], workouts: list[dict]) -> dict:
    return {
        "source": "garmin",
        "schema_version": "1.2",
        "plan": plan,
        "date_range": {"start": start_date, "end": end_date},
        "included_data": selected,
        "field_notes": {
            "daily_summary.distance_km": "Distance in kilometers.",
            "workouts.distance_km": "Distance in kilometers, normalized from Garmin summarized activity export.",
            "limitations": [
                "No second-by-second workout time series.",
                "No GPS track in output JSON.",
                "No in-app AI coaching.",
            ],
        },
        "daily_summary": daily_summary if "daily_summary" in selected else [],
        "sleep": sleep if "sleep" in selected else [],
        "workouts": workouts if "workouts" in selected else [],
        "record_counts": {
            "daily_summary": len(daily_summary) if "daily_summary" in selected else 0,
            "sleep": len(sleep) if "sleep" in selected else 0,
            "workouts": len(workouts) if "workouts" in selected else 0,
        },
    }
