from __future__ import annotations

import csv
import gzip
import math
import os
import tempfile
from datetime import datetime
from typing import Any

from fitparse import FitFile


SPORT_MAP_SUMMARY = {
    "run": {"run", "running", "trail run", "virtual run", "treadmill"},
    "ride": {"ride", "cycling", "virtual ride", "ebikeride", "mountain bike ride", "gravel ride"},
}

SPORT_MAP_ANALYSIS = {
    "run": {"running"},
    "ride": {"cycling"},
}


def scan_strava_files(root_dir: str) -> dict[str, Any]:
    activities_csv = None
    fit_files: list[str] = []
    fit_file_map: dict[str, str] = {}

    for root, _, files in os.walk(root_dir):
        for name in files:
            lower = name.lower()
            path = os.path.join(root, name)

            if lower == "activities.csv":
                activities_csv = path
            elif lower.endswith(".fit.gz"):
                fit_files.append(path)

                basename = os.path.basename(path)
                activity_id = basename[:-7]  # remove ".fit.gz"
                if activity_id:
                    fit_file_map[activity_id] = path

    return {
        "activities_csv": activities_csv,
        "fit_files": sorted(fit_files),
        "fit_file_map": fit_file_map,
    }


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except Exception:
        return None


def _parse_strava_csv_date(value: str) -> datetime.date | None:
    if not value:
        return None

    candidates = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%b %d, %Y, %I:%M:%S %p",
        "%b %d, %Y",
    ]

    text = value.strip()
    for fmt in candidates:
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            pass

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        return None


def _normalize_summary_sport(activity_type: str | None) -> str | None:
    if not activity_type:
        return None
    text = activity_type.strip().lower()
    for target, names in SPORT_MAP_SUMMARY.items():
        if text in names:
            return target
    return None


def collect_strava_summary(
    csv_path: str,
    sport: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()

    workouts: list[dict[str, Any]] = []

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            activity_date = _parse_strava_csv_date(row.get("Activity Date", ""))
            if activity_date is None:
                continue
            if not (start <= activity_date <= end):
                continue

            normalized_sport = _normalize_summary_sport(row.get("Activity Type"))
            if sport != "all" and normalized_sport != sport:
                continue

            distance_m = _safe_float(row.get("Distance"))
            moving_time_sec = _safe_float(row.get("Moving Time"))
            elapsed_time_sec = _safe_float(row.get("Elapsed Time"))
            avg_hr = _safe_float(row.get("Average Heart Rate"))
            max_hr = _safe_float(row.get("Max Heart Rate"))
            calories = _safe_float(row.get("Calories"))

            workouts.append(
                {
                    "date": activity_date.isoformat(),
                    "title": row.get("Activity Name"),
                    "sport": normalized_sport or row.get("Activity Type"),
                    "distance_km": round(distance_m / 1000, 2) if distance_m is not None else None,
                    "duration_min": round(moving_time_sec / 60, 1) if moving_time_sec is not None else None,
                    "elapsed_min": round(elapsed_time_sec / 60, 1) if elapsed_time_sec is not None else None,
                    "avg_hr": avg_hr,
                    "max_hr": max_hr,
                    "calories": calories,
                }
            )

    workouts.sort(key=lambda x: x["date"])
    return workouts


def build_summary_output(
    plan: str,
    sport: str,
    start_date: str,
    end_date: str,
    workouts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "source": "strava",
        "schema_version": "2.2",
        "plan": plan,
        "mode": "summary",
        "sport": sport,
        "date_range": {
            "start": start_date,
            "end": end_date,
        },
        "workouts": workouts,
        "record_counts": {
            "workouts": len(workouts),
        },
    }


def _extract_fit_to_temp_path(fit_gz_path: str) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".fit", delete=False)
    tmp_path = tmp.name
    tmp.close()

    with gzip.open(fit_gz_path, "rb") as gz, open(tmp_path, "wb") as out:
        out.write(gz.read())

    return tmp_path


def _fit_sport_matches(fit_sport: str | None, requested_sport: str) -> bool:
    if fit_sport is None:
        return False
    text = str(fit_sport).strip().lower()
    return text in SPORT_MAP_ANALYSIS.get(requested_sport, set())


def _mean_ignore_none(values: list[float | int | None]) -> float | None:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 2)


def _speed_to_pace(speed_mps: float | None) -> float | None:
    if speed_mps is None or speed_mps <= 0:
        return None
    return round((1000 / speed_mps) / 60, 2)


def _compress_records(records: list[dict[str, Any]], target_points: int = 200) -> dict[str, list[Any]]:
    if not records:
        return {
            "elapsed_sec": [],
            "pace_min_per_km": [],
            "heart_rate": [],
            "cadence": [],
        }

    n = len(records)
    bucket_count = min(target_points, n)
    chunk_size = n / bucket_count

    elapsed_sec_list: list[int] = []
    pace_list: list[float | None] = []
    hr_list: list[float | None] = []
    cadence_list: list[float | None] = []
    power_list: list[float | None] = []
    altitude_list: list[float | None] = []

    start_ts = records[0].get("timestamp")

    for i in range(bucket_count):
        start_idx = int(math.floor(i * chunk_size))
        end_idx = int(math.floor((i + 1) * chunk_size))
        if end_idx <= start_idx:
            end_idx = start_idx + 1

        chunk = records[start_idx:end_idx]
        if not chunk:
            continue

        current_ts = chunk[len(chunk) // 2].get("timestamp")
        elapsed_sec = None
        if start_ts is not None and current_ts is not None:
            try:
                elapsed_sec = int((current_ts - start_ts).total_seconds())
            except Exception:
                elapsed_sec = i

        speeds = [_safe_float(r.get("speed")) for r in chunk]
        hrs = [_safe_float(r.get("heart_rate")) for r in chunk]
        cads = [_safe_float(r.get("cadence")) for r in chunk]
        pows = [_safe_float(r.get("power")) for r in chunk]
        alts = [_safe_float(r.get("altitude")) for r in chunk]

        avg_speed = _mean_ignore_none(speeds)

        elapsed_sec_list.append(elapsed_sec if elapsed_sec is not None else i)
        pace_list.append(_speed_to_pace(avg_speed))
        hr_list.append(_mean_ignore_none(hrs))
        cadence_list.append(_mean_ignore_none(cads))

        if any(v is not None for v in pows):
            power_list.append(_mean_ignore_none(pows))
        if any(v is not None for v in alts):
            altitude_list.append(_mean_ignore_none(alts))

    result = {
        "elapsed_sec": elapsed_sec_list,
        "pace_min_per_km": pace_list,
        "heart_rate": hr_list,
        "cadence": cadence_list,
    }

    if power_list:
        result["power"] = power_list
    if altitude_list:
        result["altitude_m"] = altitude_list

    return result


def _build_analysis_workout_from_fit(fit_gz_path: str) -> dict[str, Any] | None:
    temp_fit_path = _extract_fit_to_temp_path(fit_gz_path)

    try:
        fit = FitFile(temp_fit_path)

        session = None
        for msg in fit.get_messages("session"):
            row = {}
            for field in msg:
                row[field.name] = field.value
            session = row
            break

        if not session:
            return None

        records: list[dict[str, Any]] = []
        for msg in fit.get_messages("record"):
            row = {}
            for field in msg:
                row[field.name] = field.value
            records.append(row)

        start_time = session.get("start_time")
        sport = session.get("sport")

        activity_date = None
        if start_time is not None:
            try:
                activity_date = start_time.date().isoformat()
            except Exception:
                activity_date = None

        total_distance = _safe_float(session.get("total_distance"))
        total_timer_time = _safe_float(session.get("total_timer_time"))
        avg_hr = _safe_float(session.get("avg_heart_rate"))
        max_hr = _safe_float(session.get("max_heart_rate"))

        return {
            "fit_path": fit_gz_path,
            "date": activity_date,
            "sport_raw": str(sport).lower() if sport is not None else None,
            "distance_km": round(total_distance / 1000, 2) if total_distance is not None else None,
            "duration_min": round(total_timer_time / 60, 1) if total_timer_time is not None else None,
            "avg_hr": avg_hr,
            "max_hr": max_hr,
            "compressed_streams": _compress_records(records, target_points=200),
        }
    finally:
        try:
            os.remove(temp_fit_path)
        except Exception:
            pass


def _read_activity_rows(csv_path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            activity_date = _parse_strava_csv_date(raw.get("Activity Date", ""))
            normalized_sport = _normalize_summary_sport(raw.get("Activity Type"))
            activity_id = str(raw.get("Activity ID", "")).strip()

            rows.append(
                {
                    "activity_id": activity_id,
                    "date": activity_date.isoformat() if activity_date else None,
                    "date_obj": activity_date,
                    "sport": normalized_sport,
                    "title": raw.get("Activity Name"),
                }
            )

    return rows


def _load_recent_activity_ids(csv_path: str, sport: str, recent_count: int) -> list[str]:
    rows = _read_activity_rows(csv_path)

    filtered = [
        row for row in rows
        if row.get("sport") == sport and row.get("date_obj") is not None and row.get("activity_id")
    ]

    filtered.sort(key=lambda x: (x["date_obj"], x["activity_id"]), reverse=True)

    selected = filtered[:recent_count]
    return [row["activity_id"] for row in selected]


def _load_activity_id_candidates(csv_path: str, sport: str, activity_date: str) -> set[str]:
    target_date = datetime.strptime(activity_date, "%Y-%m-%d").date()
    rows = _read_activity_rows(csv_path)

    ids: set[str] = set()
    for row in rows:
        if row.get("date_obj") != target_date:
            continue
        if row.get("sport") != sport:
            continue
        activity_id = row.get("activity_id")
        if activity_id:
            ids.add(activity_id)

    return ids


def _select_fit_files_for_recent(
    csv_path: str,
    fit_file_map: dict[str, str],
    sport: str,
    recent_count: int,
) -> list[str]:
    recent_ids = _load_recent_activity_ids(csv_path, sport, recent_count)
    selected: list[str] = []

    for activity_id in recent_ids:
        fit_path = fit_file_map.get(activity_id)
        if fit_path:
            selected.append(fit_path)

    return selected


def build_analysis_workouts(
    csv_path: str,
    fit_file_map: dict[str, str],
    sport: str,
    recent_count: int,
) -> list[dict[str, Any]]:
    target_fit_files = _select_fit_files_for_recent(
        csv_path=csv_path,
        fit_file_map=fit_file_map,
        sport=sport,
        recent_count=recent_count,
    )

    workouts: list[dict[str, Any]] = []

    for fit_path in target_fit_files:
        workout = _build_analysis_workout_from_fit(fit_path)
        if not workout:
            continue
        if not _fit_sport_matches(workout.get("sport_raw"), sport):
            continue

        workouts.append(
            {
                "date": workout["date"],
                "sport": sport,
                "distance_km": workout["distance_km"],
                "duration_min": workout["duration_min"],
                "avg_hr": workout["avg_hr"],
                "max_hr": workout["max_hr"],
                "compressed_streams": workout["compressed_streams"],
            }
        )

    workouts.sort(key=lambda x: x.get("date") or "", reverse=True)
    return workouts


def build_analysis_workouts_for_date(
    csv_path: str,
    fit_file_map: dict[str, str],
    sport: str,
    activity_date: str,
) -> list[dict[str, Any]]:
    candidate_ids = _load_activity_id_candidates(csv_path, sport, activity_date)
    if not candidate_ids:
        raise ValueError(f"No {sport} activities found for {activity_date}.")

    target_fit_files = []
    for activity_id in candidate_ids:
        fit_path = fit_file_map.get(activity_id)
        if fit_path:
            target_fit_files.append(fit_path)

    if not target_fit_files:
        raise ValueError(f"No FIT files matched the {sport} activities on {activity_date}.")

    workouts: list[dict[str, Any]] = []

    for fit_path in target_fit_files:
        workout = _build_analysis_workout_from_fit(fit_path)
        if not workout:
            continue
        if not _fit_sport_matches(workout.get("sport_raw"), sport):
            continue

        workouts.append(
            {
                "date": workout["date"],
                "sport": sport,
                "distance_km": workout["distance_km"],
                "duration_min": workout["duration_min"],
                "avg_hr": workout["avg_hr"],
                "max_hr": workout["max_hr"],
                "compressed_streams": workout["compressed_streams"],
            }
        )

    workouts.sort(key=lambda x: x.get("date") or "")
    if not workouts:
        raise ValueError(f"No readable {sport} FIT activities found for {activity_date}.")
    return workouts


def build_analysis_output(
    plan: str,
    sport: str,
    recent_count: int | None,
    workouts: list[dict[str, Any]],
    analysis_scope: str = "recent",
    activity_date: str | None = None,
) -> dict[str, Any]:
    result = {
        "source": "strava",
        "schema_version": "2.2",
        "plan": plan,
        "mode": "analysis",
        "analysis_scope": analysis_scope,
        "sport": sport,
        "target_stream_points": 200,
        "workouts": workouts,
        "record_counts": {
            "workouts": len(workouts),
        },
    }

    if analysis_scope == "recent":
        result["recent_count"] = recent_count
    if analysis_scope == "date":
        result["activity_date"] = activity_date

    return result
