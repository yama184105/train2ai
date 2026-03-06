from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import zipfile
import tempfile
import os
import json
from datetime import datetime

app = FastAPI()


@app.get("/")
def root():
    return {"message": "train2ai API running"}


@app.post("/upload")
async def upload_garmin_data(
    file: UploadFile = File(...),
    start_date: str = Form(...),
    end_date: str = Form(...)
):
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Please upload a .zip file")

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

        if start_dt > end_dt:
            raise HTTPException(
                status_code=400,
                detail="start_date must be before or equal to end_date"
            )

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
                    lower_name = name.lower()

                    if lower_name.startswith("udsfile_") and lower_name.endswith(".json"):
                        uds_files.append(os.path.join(root_dir, name))

                    if lower_name.endswith("_sleepdata.json"):
                        sleep_files.append(os.path.join(root_dir, name))

                    if "summarizedactivities" in lower_name and lower_name.endswith(".json"):
                        workout_files.append(os.path.join(root_dir, name))

            if not uds_files:
                raise HTTPException(status_code=404, detail="UDSFile json files not found in zip")

            daily_summary = []

            for uds_file in uds_files:
                with open(uds_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if not isinstance(data, list):
                    continue

                for item in data:
                    if not isinstance(item, dict):
                        continue

                    date_str = item.get("calendarDate")
                    if not date_str:
                        continue

                    try:
                        item_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except ValueError:
                        continue

                    if start_dt <= item_date <= end_dt:
                        clean_item = {
                            "date": date_str,
                            "steps": item.get("totalSteps"),
                            "total_calories": item.get("totalKilocalories"),
                            "active_calories": item.get("activeKilocalories"),
                            "bmr_calories": item.get("bmrKilocalories"),
                            "total_distance_m": item.get("totalDistanceMeters"),
                            "resting_hr": item.get("restingHeartRate"),
                            "current_day_resting_hr": item.get("currentDayRestingHeartRate"),
                            "min_hr": item.get("minHeartRate"),
                            "max_hr": item.get("maxHeartRate"),
                            "moderate_intensity_minutes": item.get("moderateIntensityMinutes"),
                            "vigorous_intensity_minutes": item.get("vigorousIntensityMinutes"),
                        }
                        daily_summary.append(clean_item)

            sleep = []

            for sleep_file in sleep_files:
                with open(sleep_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if not isinstance(data, list):
                    continue

                for item in data:
                    if not isinstance(item, dict):
                        continue

                    date_str = item.get("calendarDate")
                    if not date_str:
                        continue

                    try:
                        item_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except ValueError:
                        continue

                    if start_dt <= item_date <= end_dt:
                        clean_item = {
                            "date": date_str,
                            "sleep_start_gmt": item.get("sleepStartTimestampGMT"),
                            "sleep_end_gmt": item.get("sleepEndTimestampGMT"),
                            "deep_sleep_min": round((item.get("deepSleepSeconds") or 0) / 60),
                            "light_sleep_min": round((item.get("lightSleepSeconds") or 0) / 60),
                            "rem_sleep_min": round((item.get("remSleepSeconds") or 0) / 60),
                            "awake_sleep_min": round((item.get("awakeSleepSeconds") or 0) / 60),
                            "average_respiration": item.get("averageRespiration"),
                            "awake_count": item.get("awakeCount"),
                            "sleep_score": (item.get("sleepScores") or {}).get("overallScore"),
                        }
                        sleep.append(clean_item)

            workouts = []

            for workout_file in workout_files:
                with open(workout_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, list):
                    if len(data) > 0 and isinstance(data[0], dict) and "summarizedActivitiesExport" in data[0]:
                        activities = data[0].get("summarizedActivitiesExport", [])
                    else:
                        activities = data
                elif isinstance(data, dict):
                    activities = data.get("summarizedActivitiesExport", [])
                else:
                    activities = []

                for act in activities:
                    if not isinstance(act, dict):
                        continue

                    date_str = act.get("startTimeLocal")
                    if not date_str:
                        continue

                    try:
                        workout_date = datetime.fromisoformat(date_str.replace("Z", "")).date()
                    except ValueError:
                        try:
                            workout_date = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
                        except ValueError:
                            continue

                    if start_dt <= workout_date <= end_dt:
                        clean_item = {
                            "date": workout_date.isoformat(),
                            "sport": act.get("sportType"),
                            "distance_m": act.get("distance"),
                            "duration_s": act.get("duration"),
                            "avg_speed": act.get("avgSpeed"),
                            "avg_hr": act.get("avgHr"),
                            "max_hr": act.get("maxHr"),
                            "calories": act.get("calories"),
                            "start_time_local": act.get("startTimeLocal"),
                            "activity_id": act.get("activityId"),
                        }
                        workouts.append(clean_item)

            daily_summary.sort(key=lambda x: x["date"])
            sleep.sort(key=lambda x: x["date"])
            workouts.sort(key=lambda x: x["date"])

            return {
                "source": "garmin",
                "date_range": {
                    "start": start_date,
                    "end": end_date
                },
                "included_data": ["daily_summary", "sleep", "workouts"],
                "daily_summary": daily_summary,
                "sleep": sleep,
                "workouts": workouts
            }

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip file")
    except ValueError:
        raise HTTPException(status_code=400, detail="Date format must be YYYY-MM-DD")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
