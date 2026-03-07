import csv
import gzip
import math
import os
import tempfile
from datetime import datetime
from pathlib import Path
from statistics import mean

from fastapi import HTTPException

from app.config import TARGET_STREAM_POINTS

try:
    from fitparse import FitFile
except Exception:  # pragma: no cover - runtime dependency
    FitFile = None


RUN_SPORTS = {"run", "running", "trail run", "virtual run", "treadmill"}
RIDE_SPORTS = {"ride", "cycling", "bike", "ebikeride", "virtualride", "mountain bike ride", "gravel ride"}


def normalize_sport_name(raw: str | None) -> str | None:
    if not raw:
        return None
    value = str(raw).strip().lower()
    if value in RUN_SPORTS or "run" in value:
        return "run"
    if value in RIDE_SPORTS or "ride" in value or "cycl" in value or "bike" in value:
        return "ride"
    return None


def scan_strava_files(root_dir: str) -> dict[str, list[str] | str | None]:
    activities_csv: str | None = None
    fit_files: list[str] = []

    for root, _, files in os.walk(root_dir):
        for name in files:
            path = os.path.join(root, name)
            lower = name.lower()
            if lower == "activities.csv":
                activities_csv = path
            elif lower.endswith(".fit") or lower.endswith(".fit.gz"):
                fit_files.append(path)

    return {
        "activities_csv": activities_csv,
        "fit_files": sorted(fit_files),
    }


def parse_strava_datetime(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported datetime format: {value}")


def to_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def to_int(value) -> int | None:
    number = to_float(value)
    if number is None:
        return None
    return int(round(number))


def collect_strava_summary(csv_path: str, sport: str, recent_count: int | None = None) -> list[dict]:
    workouts: list[dict] = []
    try:
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                normalized_sport = normalize_sport_name(row.get("Activity Type"))
                if normalized_sport != sport:
                    continue

                date_raw = row.get("Activity Date")
                if not date_raw:
                    continue

                try:
                    activity_dt = parse_strava_datetime(date_raw)
                except ValueError:
                    continue

                distance_m = to_float(row.get("Distance"))
                moving_time_sec = to_float(row.get("Moving Time"))

                workouts.append(
                    {
                        "activity_id": str(row.get("Activity ID") or "").strip() or None,
                        "date": activity_dt.date().isoformat(),
                        "start_time": activity_dt.isoformat(),
                        "title": row.get("Activity Name") or None,
                        "sport": normalized_sport,
                        "distance_km": round(distance_m / 1000, 2) if distance_m is not None else None,
                        "duration_min": round(moving_time_sec / 60, 1) if moving_time_sec is not None else None,
                        "avg_hr": to_int(row.get("Average Heart Rate")),
                        "max_hr": to_int(row.get("Max Heart Rate")),
                        "calories": to_int(row.get("Calories")),
                        "elevation_gain_m": to_float(row.get("Elevation Gain")),
                    }
                )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail="activities.csv was not found in the Strava export ZIP.") from exc

    workouts.sort(key=lambda x: x.get("start_time") or "", reverse=True)
    if recent_count:
        workouts = workouts[:recent_count]
    return workouts


def open_fit_file(path: str):
    if path.lower().endswith(".fit.gz"):
        tmp = tempfile.NamedTemporaryFile(suffix=".fit", delete=False)
        with gzip.open(path, "rb") as gz:
            tmp.write(gz.read())
        tmp.close()
        return tmp.name, True
    return path, False


def fit_message_to_dict(message) -> dict:
    return {field.name: field.value for field in message}


def extract_fit_summary(path: str) -> dict | None:
    if FitFile is None:
        raise HTTPException(
            status_code=500,
            detail="FIT analysis requires the fitparse package. Add fitparse to requirements.txt before deploying analysis mode.",
        )

    temp_path, should_delete = open_fit_file(path)
    try:
        fit = FitFile(temp_path)
        for msg in fit.get_messages("session"):
            data = fit_message_to_dict(msg)
            sport = normalize_sport_name(data.get("sport") or data.get("sub_sport"))
            start_time = data.get("start_time")
            if not start_time:
                continue
            return {
                "path": path,
                "activity_id": Path(path).name.split(".")[0],
                "sport": sport,
                "start_time": start_time,
                "date": start_time.date().isoformat() if hasattr(start_time, "date") else None,
                "distance_km": round(float(data.get("total_distance")) / 1000, 2) if data.get("total_distance") is not None else None,
                "duration_min": round(float(data.get("total_timer_time")) / 60, 1) if data.get("total_timer_time") is not None else None,
                "avg_hr": to_int(data.get("avg_heart_rate")),
                "max_hr": to_int(data.get("max_heart_rate")),
                "calories": to_int(data.get("total_calories")),
                "elevation_gain_m": to_float(data.get("total_ascent")),
            }
        return None
    finally:
        if should_delete:
            Path(temp_path).unlink(missing_ok=True)


def list_recent_analysis_candidates(fit_files: list[str], sport: str, recent_count: int) -> list[dict]:
    candidates: list[dict] = []
    for fit_path in fit_files:
        summary = extract_fit_summary(fit_path)
        if not summary:
            continue
        if summary.get("sport") != sport:
            continue
        candidates.append(summary)

    candidates.sort(key=lambda x: x.get("start_time") or datetime.min, reverse=True)
    return candidates[:recent_count]


def avg_or_none(values: list[float | int | None]) -> float | None:
    cleaned = [float(v) for v in values if v is not None]
    if not cleaned:
        return None
    return mean(cleaned)


def compress_records(records: list[dict], target_points: int = TARGET_STREAM_POINTS) -> dict:
    if not records:
        return {}

    total_points = len(records)
    actual_points = min(target_points, total_points)
    compressed = {
        "elapsed_sec": [],
        "heart_rate": [],
        "speed_mps": [],
        "cadence": [],
    }

    has_power = any(r.get("power") is not None for r in records)
    has_altitude = any(r.get("altitude") is not None for r in records)
    if has_power:
        compressed["power"] = []
    if has_altitude:
        compressed["altitude_m"] = []

    for i in range(actual_points):
        start_idx = math.floor(i * total_points / actual_points)
        end_idx = math.floor((i + 1) * total_points / actual_points)
        chunk = records[start_idx:max(end_idx, start_idx + 1)]
        center = chunk[len(chunk) // 2]

        hr = avg_or_none([r.get("heart_rate") for r in chunk])
        speed = avg_or_none([r.get("speed") for r in chunk])
        cadence = avg_or_none([r.get("cadence") for r in chunk])

        compressed["elapsed_sec"].append(int(center.get("elapsed_sec") or 0))
        compressed["heart_rate"].append(round(hr, 1) if hr is not None else None)
        compressed["speed_mps"].append(round(speed, 3) if speed is not None else None)
        compressed["cadence"].append(round(cadence, 1) if cadence is not None else None)

        if has_power:
            value = avg_or_none([r.get("power") for r in chunk])
            compressed["power"].append(round(value, 1) if value is not None else None)
        if has_altitude:
            value = avg_or_none([r.get("altitude") for r in chunk])
            compressed["altitude_m"].append(round(value, 1) if value is not None else None)

    pace_values = []
    for speed in compressed["speed_mps"]:
        if speed is None or speed <= 0:
            pace_values.append(None)
        else:
            pace_values.append(round(1000 / speed / 60, 2))
    compressed["pace_min_per_km"] = pace_values
    return compressed


def extract_fit_records(path: str) -> list[dict]:
    if FitFile is None:
        raise HTTPException(
            status_code=500,
            detail="FIT analysis requires the fitparse package. Add fitparse to requirements.txt before deploying analysis mode.",
        )

    temp_path, should_delete = open_fit_file(path)
    try:
        fit = FitFile(temp_path)
        rows: list[dict] = []
        base_ts = None

        for msg in fit.get_messages("record"):
            data = fit_message_to_dict(msg)
            timestamp = data.get("timestamp")
            if timestamp is None:
                continue
            if base_ts is None:
                base_ts = timestamp
            elapsed_sec = int((timestamp - base_ts).total_seconds()) if hasattr(timestamp, "__sub__") else None
            rows.append(
                {
                    "timestamp": timestamp,
                    "elapsed_sec": elapsed_sec,
                    "heart_rate": to_float(data.get("heart_rate")),
                    "speed": to_float(data.get("speed")),
                    "cadence": to_float(data.get("cadence")),
                    "power": to_float(data.get("power")),
                    "altitude": to_float(data.get("altitude")),
                }
            )
        return rows
    finally:
        if should_delete:
            Path(temp_path).unlink(missing_ok=True)


def build_analysis_workouts(fit_files: list[str], sport: str, recent_count: int) -> list[dict]:
    selected = list_recent_analysis_candidates(fit_files, sport, recent_count)
    workouts: list[dict] = []

    for summary in selected:
        records = extract_fit_records(summary["path"])
        if not records:
            continue
        workouts.append(
            {
                "activity_id": summary.get("activity_id"),
                "date": summary.get("date"),
                "start_time": summary.get("start_time").isoformat() if summary.get("start_time") else None,
                "sport": summary.get("sport"),
                "distance_km": summary.get("distance_km"),
                "duration_min": summary.get("duration_min"),
                "avg_hr": summary.get("avg_hr"),
                "max_hr": summary.get("max_hr"),
                "calories": summary.get("calories"),
                "elevation_gain_m": summary.get("elevation_gain_m"),
                "compressed_streams": compress_records(records),
            }
        )

    if not workouts:
        raise HTTPException(status_code=400, detail="No matching FIT activities with record data were found for analysis mode.")
    return workouts


def build_summary_output(plan: str, sport: str, recent_count: int, workouts: list[dict]) -> dict:
    return {
        "source": "strava",
        "schema_version": "2.0",
        "plan": plan,
        "mode": "summary",
        "sport": sport,
        "recent_count": recent_count,
        "field_notes": {
            "distance_km": "Distance in kilometers from activities.csv.",
            "duration_min": "Moving time in minutes from activities.csv.",
            "limitations": [
                "Summary mode uses activities.csv only.",
                "No second-by-second data in summary mode.",
                "No GPS track in output JSON.",
            ],
        },
        "workouts": workouts,
        "record_counts": {"workouts": len(workouts)},
    }


def build_analysis_output(plan: str, sport: str, recent_count: int, workouts: list[dict]) -> dict:
    return {
        "source": "strava",
        "schema_version": "2.0",
        "plan": plan,
        "mode": "analysis",
        "sport": sport,
        "recent_count": recent_count,
        "target_stream_points": TARGET_STREAM_POINTS,
        "field_notes": {
            "compressed_streams": "Each activity is compressed to about 200 averaged points.",
            "speed_mps": "Average speed per compressed chunk in meters per second.",
            "pace_min_per_km": "Derived from compressed speed.",
            "limitations": [
                "Analysis mode uses FIT files only.",
                "Missing fields remain null.",
                "No GPS track in output JSON.",
            ],
        },
        "workouts": workouts,
        "record_counts": {"workouts": len(workouts)},
    }
