from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import Response, HTMLResponse
from pathlib import Path

import zipfile
import tempfile
import os
import json
from datetime import datetime, timezone

app = FastAPI()

USAGE_FILE = "usage_log.json"
FREE_MONTHLY_LIMIT = 3


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
        <title>train2ai</title>
    </head>
    <body style="font-family: Arial; max-width:600px; margin:40px auto;">
        <h1>train2ai</h1>
        <p>Turn Garmin data into AI-ready JSON.</p>

        <form action="/upload" method="post" enctype="multipart/form-data">

            <label>Garmin export ZIP</label><br>
            <input type="file" name="file" accept=".zip" required><br><br>

            <label>Start date</label><br>
            <input type="date" name="start_date" required><br><br>

            <label>End date</label><br>
            <input type="date" name="end_date" required><br><br>

            <label>Plan</label><br>
            <select name="plan">
                <option value="free">Free</option>
                <option value="pro">Pro</option>
            </select><br><br>

            <button type="submit">Generate dataset</button>

        </form>

        <p style="margin-top:20px;font-size:14px;color:gray;">
        Free plan: up to 7 days, 3 exports per month
        </p>

    </body>
    </html>
    """


def parse_input_date(date_str: str, field_name: str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}. Use YYYY-MM-DD."
        )


def parse_garmin_datetime(dt_str):
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str).isoformat()
    except:
        return None


def enforce_plan_limit(plan: str, start_dt, end_dt):

    days = (end_dt - start_dt).days + 1

    if plan == "free" and days > 7:
        raise HTTPException(
            status_code=400,
            detail="Free plan supports up to 7 days per export."
        )

    if plan == "pro" and days > 365:
        raise HTTPException(
            status_code=400,
            detail="Pro plan supports up to 365 days per export."
        )


def check_usage_limit(ip: str, plan: str):

    if plan != "free":
        return

    now = datetime.utcnow()
    month_key = now.strftime("%Y-%m")

    if Path(USAGE_FILE).exists():
        with open(USAGE_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}

    if month_key not in data:
        data[month_key] = {}

    count = data[month_key].get(ip, 0)

    if count >= FREE_MONTHLY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Free plan monthly limit reached (3 exports)."
        )

    data[month_key][ip] = count + 1

    with open(USAGE_FILE, "w") as f:
        json.dump(data, f)


@app.post("/upload")
async def upload_garmin_data(
    request: Request,
    file: UploadFile = File(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    plan: str = Form("free")
):

    ip = request.client.host

    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload a Garmin export zip")

    start_dt = parse_input_date(start_date, "start_date")
    end_dt = parse_input_date(end_date, "end_date")

    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    enforce_plan_limit(plan, start_dt, end_dt)
    check_usage_limit(ip, plan)

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

                        distance = item.get("totalDistanceMeters")

                        daily_summary.append({

                            "date": date_str,
                            "steps": item.get("totalSteps"),
                            "total_calories": item.get("totalKilocalories"),
                            "active_calories": item.get("activeKilocalories"),
                            "distance_m": distance,
                            "distance_km": round(distance / 1000, 2) if distance else None,
                            "resting_hr": item.get("restingHeartRate")

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
                            "sleep_start": parse_garmin_datetime(item.get("sleepStartTimestampGMT")),
                            "sleep_end": parse_garmin_datetime(item.get("sleepEndTimestampGMT")),
                            "deep_sleep_min": round((item.get("deepSleepSeconds") or 0)/60),
                            "light_sleep_min": round((item.get("lightSleepSeconds") or 0)/60),
                            "rem_sleep_min": round((item.get("remSleepSeconds") or 0)/60)

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

                    if not isinstance(start_time, (int, float)):
                        continue

                    workout_date = datetime.fromtimestamp(start_time/1000, tz=timezone.utc).date()

                    if start_dt <= workout_date <= end_dt:

                        dist = act.get("distance")
                        dur = act.get("duration")

                        workouts.append({

                            "date": workout_date.isoformat(),
                            "sport": act.get("sportType"),
                            "distance_km": round(dist / 100000, 2) if dist else None,
                            "duration_min": round(dur / 60000, 1) if dur else None,
                            "avg_hr": act.get("avgHr"),
                            "max_hr": act.get("maxHr"),
                            "start_time_utc_iso": datetime.fromtimestamp(start_time/1000, tz=timezone.utc).isoformat()

                        })

            result = {

                "source": "garmin",
                "plan": plan,

                "date_range": {
                    "start": start_date,
                    "end": end_date
                },

                "daily_summary": sorted(daily_summary, key=lambda x: x["date"]),
                "sleep": sorted(sleep, key=lambda x: x["date"]),
                "workouts": sorted(workouts, key=lambda x: x["date"]),

                "record_counts": {
                    "daily_summary": len(daily_summary),
                    "sleep": len(sleep),
                    "workouts": len(workouts)
                }

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
        
