from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
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
        raise HTTPException(status_code=400, detail="Upload a Garmin export zip")

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

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

                    if lower.startswith("udsfile_") and lower.endswith(".json"):
                        uds_files.append(os.path.join(root_dir, name))

                    if lower.endswith("_sleepdata.json"):
                        sleep_files.append(os.path.join(root_dir, name))

                    if "summarizedactivities" in lower:
                        workout_files.append(os.path.join(root_dir, name))

            daily_summary = []

            for uds_file in uds_files:

                with open(uds_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if not isinstance(data, list):
                    continue

                for item in data:

                    date_str = item.get("calendarDate")

                    if not date_str:
                        continue

                    item_date = datetime.strptime(date_str, "%Y-%m-%d").date()

                    if start_dt <= item_date <= end_dt:

                        daily_summary.append({

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
                            "vigorous_intensity_minutes": item.get("vigorousIntensityMinutes")

                        })

            sleep = []

            for sleep_file in sleep_files:

                with open(sleep_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if not isinstance(data, list):
                    continue

                for item in data:

                    date_str = item.get("calendarDate")

                    if not date_str:
                        continue

                    item_date = datetime.strptime(date_str, "%Y-%m-%d").date()

                    if start_dt <= item_date <= end_dt:

                        sleep.append({

                            "date": date_str,
                            "sleep_start_gmt": item.get("sleepStartTimestampGMT"),
                            "sleep_end_gmt": item.get("sleepEndTimestampGMT"),
                            "deep_sleep_min": round((item.get("deepSleepSeconds") or 0)/60),
                            "light_sleep_min": round((item.get("lightSleepSeconds") or 0)/60),
                            "rem_sleep_min": round((item.get("remSleepSeconds") or 0)/60),
                            "awake_sleep_min": round((item.get("awakeSleepSeconds") or 0)/60),
                            "average_respiration": item.get("averageRespiration"),
                            "awake_count": item.get("awakeCount"),
                            "sleep_score": (item.get("sleepScores") or {}).get("overallScore")

                        })

            workouts = []

            for workout_file in workout_files:

                with open(workout_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, list):

                    if len(data) > 0 and "summarizedActivitiesExport" in data[0]:
                        activities = data[0]["summarizedActivitiesExport"]
                    else:
                        activities = data

                else:
                    activities = []

                for act in activities:

                    start_time = act.get("startTimeLocal")

                    if start_time is None:
                        continue

                    if isinstance(start_time, (int, float)):
                        workout_date = datetime.fromtimestamp(start_time/1000).date()
                    else:
                        continue

                    if start_dt <= workout_date <= end_dt:

                        workouts.append({

                            "date": workout_date.isoformat(),
                            "sport": act.get("sportType"),
                            "name": act.get("name"),
                            "distance_m": act.get("distance"),
                            "duration_s": act.get("duration"),
                            "avg_speed": act.get("avgSpeed"),
                            "max_speed": act.get("maxSpeed"),
                            "avg_hr": act.get("avgHr"),
                            "max_hr": act.get("maxHr"),
                            "calories": act.get("calories"),
                            "start_time_local": start_time,
                            "activity_id": act.get("activityId")

                        })

            result = {

                "source": "garmin",

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
                "workouts": sorted(workouts, key=lambda x: x["date"])

            }

            json_str = json.dumps(result, indent=2)

            return Response(
                content=json_str,
                media_type="application/json",
                headers={
                    "Content-Disposition": "attachment; filename=train2ai_dataset.json"
                }
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
