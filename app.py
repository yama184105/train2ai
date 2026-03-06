from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
import zipfile
import tempfile
import os
import json
from datetime import datetime, timezone

app = FastAPI()


@app.get("/")
def root():
    return {"message": "train2ai API running"}


def parse_input_date(date_str: str, field_name: str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}. Use YYYY-MM-DD and a real calendar date."
        )


def parse_garmin_datetime(dt_str):
    if not dt_str:
        return None
    if not isinstance(dt_str, str):
        return None

    # Garminの "2026-02-01T12:30:42.0" のような形式を想定
    try:
        return datetime.fromisoformat(dt_str).isoformat()
    except ValueError:
        return None


@app.post("/upload")
async def upload_garmin_data(
    file: UploadFile = File(...),
    start_date: str = Form(...),
    end_date: str = Form(...)
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload a Garmin export zip")

    start_dt = parse_input_date(start_date, "start_date")
    end_dt = parse_input_date(end_date, "end_date")

    if start_dt > end_dt:
        raise HTTPException(
            status_code=400,
            detail="start_date must be on or before end_date"
        )

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, file.filename)

            with open(zip_path, "wb") as f:
                f.write(await file.read())

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            uds_files = []
            sleep_files = []
            workout_files = []

            for root_dir, dirs, files in os.walk(temp_dir):
                for name in files:
                    lower = name.lower()
                    full_path = os.path.join(root_dir, name)

                    if lower.startswith("udsfile_") and lower.endswith(".json"):
                        uds_files.append(full_path)

                    if lower.endswith("_sleepdata.json"):
                        sleep_files.append(full_path)

                    if "summarizedactivities" in lower and lower.endswith(".json"):
                        workout_files.append(full_path)

            daily_summary = []

            for uds_file in uds_files:
                try:
                    with open(uds_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    continue

                if not isinstance(data, list):
                    continue

                for item in data:
                    date_str = item.get("calendarDate")
                    if not date_str:
                        continue

                    try:
                        item_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except ValueError:
                        continue

                    if start_dt <= item_date <= end_dt:
                        total_distance_m = item.get("totalDistanceMeters")

                        daily_summary.append({
                            "date": date_str,
                            "steps": item.get("totalSteps"),
                            "total_calories": item.get("totalKilocalories"),
                            "active_calories": item.get("activeKilocalories"),
                            "bmr_calories": item.get("bmrKilocalories"),
                            "total_distance_m": total_distance_m,
                            "total_distance_km": round(total_distance_m / 1000, 2) if total_distance_m is not None else None,
                            "resting_hr": item.get("restingHeartRate"),
                            "current_day_resting_hr": item.get("currentDayRestingHeartRate"),
                            "min_hr": item.get("minHeartRate"),
                            "max_hr": item.get("maxHeartRate"),
                            "moderate_intensity_minutes": item.get("moderateIntensityMinutes"),
                            "vigorous_intensity_minutes": item.get("vigorousIntensityMinutes")
                        })

            sleep = []

            for sleep_file in sleep_files:
                try:
                    with open(sleep_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    continue

                if not isinstance(data, list):
                    continue

                for item in data:
                    date_str = item.get("calendarDate")
                    if not date_str:
                        continue

                    try:
                        item_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except ValueError:
                        continue

                    if start_dt <= item_date <= end_dt:
                        sleep.append({
                            "date": date_str,
                            "sleep_start_gmt": item.get("sleepStartTimestampGMT"),
                            "sleep_end_gmt": item.get("sleepEndTimestampGMT"),
                            "sleep_start_gmt_iso": parse_garmin_datetime(item.get("sleepStartTimestampGMT")),
                            "sleep_end_gmt_iso": parse_garmin_datetime(item.get("sleepEndTimestampGMT")),
                            "deep_sleep_min": round((item.get("deepSleepSeconds") or 0) / 60),
                            "light_sleep_min": round((item.get("lightSleepSeconds") or 0) / 60),
                            "rem_sleep_min": round((item.get("remSleepSeconds") or 0) / 60),
                            "awake_sleep_min": round((item.get("awakeSleepSeconds") or 0) / 60),
                            "average_respiration": item.get("averageRespiration"),
                            "awake_count": item.get("awakeCount"),
                            "sleep_score": (item.get("sleepScores") or {}).get("overallScore")
                        })

            workouts = []

            for workout_file in workout_files:
                try:
                    with open(workout_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    continue

                if isinstance(data, list):
                    if len(data) > 0 and isinstance(data[0], dict) and "summarizedActivitiesExport" in data[0]:
                        activities = data[0]["summarizedActivitiesExport"]
                    else:
                        activities = data
                else:
                    activities = []

                for act in activities:
                    start_time = act.get("startTimeLocal")
                    if start_time is None:
                        continue

                    if not isinstance(start_time, (int, float)):
                        continue

                    workout_date = datetime.fromtimestamp(
                        start_time / 1000,
                        tz=timezone.utc
                    ).date()

                    if start_dt <= workout_date <= end_dt:
                        distance_raw = act.get("distance")
                        duration_raw = act.get("duration")

                        # Garmin summarizedActivities は distance=cm, duration=ms とみなす
                        distance_m = round(distance_raw / 100, 2) if distance_raw is not None else None
                        distance_km = round(distance_raw / 100000, 2) if distance_raw is not None else None
                        duration_s = round(duration_raw / 1000, 1) if duration_raw is not None else None
                        duration_min = round(duration_raw / 60000, 1) if duration_raw is not None else None

                        sport = act.get("sportType")

                        workouts.append({
                            "date": workout_date.isoformat(),
                            "sport": sport,
                            "sport_normalized": sport.lower() if isinstance(sport, str) else sport,
                            "name": act.get("name"),
                            "distance_raw": distance_raw,
                            "distance_m": distance_m,
                            "distance_km": distance_km,
                            "duration_raw": duration_raw,
                            "duration_s": duration_s,
                            "duration_min": duration_min,
                            "avg_speed": act.get("avgSpeed"),
                            "max_speed": act.get("maxSpeed"),
                            "avg_hr": act.get("avgHr"),
                            "max_hr": act.get("maxHr"),
                            "calories": act.get("calories"),
                            "start_time_local": start_time,
                            "start_time_local_iso": datetime.fromtimestamp(
                                start_time / 1000,
                                tz=timezone.utc
                            ).isoformat(),
                            "activity_id": act.get("activityId")
                        })

            result = {
                "source": "garmin",
                "schema_version": "1.1",
                "date_range": {
                    "start": start_date,
                    "end": end_date
                },
                "included_data": [
                    "daily_summary",
                    "sleep",
                    "workouts"
                ],
                "daily_summary": sorted(daily_summary, key=lambda x: x["date"]),
                "sleep": sorted(sleep, key=lambda x: x["date"]),
                "workouts": sorted(workouts, key=lambda x: x["date"]),
                "record_counts": {
                    "daily_summary": len(daily_summary),
                    "sleep": len(sleep),
                    "workouts": len(workouts)
                }
            }

            json_str = json.dumps(result, indent=2, ensure_ascii=False)

            return Response(
                content=json_str,
                media_type="application/json",
                headers={
                    "Content-Disposition": "attachment; filename=train2ai_dataset.json"
                }
            )

    except HTTPException:
        raise
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
