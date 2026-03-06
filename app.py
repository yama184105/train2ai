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
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>train2ai</title>
        <style>
            * {
                box-sizing: border-box;
            }

            body {
                margin: 0;
                font-family: Inter, Arial, sans-serif;
                background: linear-gradient(180deg, #f7f8fb 0%, #eef2ff 100%);
                color: #111827;
            }

            .container {
                max-width: 1100px;
                margin: 0 auto;
                padding: 48px 20px 80px;
            }

            .hero {
                display: grid;
                grid-template-columns: 1.1fr 0.9fr;
                gap: 32px;
                align-items: center;
                min-height: 80vh;
            }

            .badge {
                display: inline-block;
                padding: 8px 12px;
                border-radius: 999px;
                background: #e0e7ff;
                color: #3730a3;
                font-size: 13px;
                font-weight: 600;
                margin-bottom: 18px;
            }

            h1 {
                font-size: 56px;
                line-height: 1.05;
                margin: 0 0 16px;
                letter-spacing: -1.5px;
            }

            .lead {
                font-size: 20px;
                line-height: 1.7;
                color: #4b5563;
                max-width: 620px;
                margin-bottom: 28px;
            }

            .bullets {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 28px;
            }

            .chip {
                padding: 10px 14px;
                border-radius: 999px;
                background: white;
                border: 1px solid #e5e7eb;
                font-size: 14px;
                color: #374151;
            }

            .card {
                background: rgba(255, 255, 255, 0.88);
                backdrop-filter: blur(10px);
                border: 1px solid #e5e7eb;
                border-radius: 24px;
                padding: 28px;
                box-shadow: 0 20px 60px rgba(17, 24, 39, 0.08);
            }

            .card h2 {
                margin: 0 0 8px;
                font-size: 24px;
            }

            .card p {
                margin: 0 0 18px;
                color: #6b7280;
                font-size: 14px;
                line-height: 1.6;
            }

            label {
                display: block;
                font-size: 14px;
                font-weight: 600;
                margin: 16px 0 8px;
                color: #374151;
            }

            input[type="file"],
            input[type="date"],
            select,
            button {
                width: 100%;
                border-radius: 12px;
                border: 1px solid #d1d5db;
                padding: 12px 14px;
                font-size: 15px;
                background: white;
            }

            input[type="file"] {
                padding: 10px;
            }

            .row {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
            }

            button {
                margin-top: 22px;
                background: #111827;
                color: white;
                border: none;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.08s ease, opacity 0.2s ease;
            }

            button:hover {
                opacity: 0.95;
            }

            button:active {
                transform: translateY(1px);
            }

            .plan-box {
                margin-top: 18px;
                padding: 14px 16px;
                background: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 14px;
                font-size: 14px;
                color: #4b5563;
                line-height: 1.7;
            }

            .foot {
                margin-top: 14px;
                font-size: 12px;
                color: #9ca3af;
            }

            .preview {
                margin-top: 28px;
                background: #111827;
                color: #e5e7eb;
                border-radius: 20px;
                padding: 20px;
                font-size: 13px;
                line-height: 1.65;
                overflow: auto;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
            }

            .preview .dim {
                color: #9ca3af;
            }

            @media (max-width: 900px) {
                .hero {
                    grid-template-columns: 1fr;
                    min-height: auto;
                }

                h1 {
                    font-size: 42px;
                }
            }

            @media (max-width: 640px) {
                .row {
                    grid-template-columns: 1fr;
                }

                .container {
                    padding-top: 28px;
                }

                h1 {
                    font-size: 36px;
                }

                .lead {
                    font-size: 17px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <section class="hero">
                <div>
                    <div class="badge">Garmin → AI-ready JSON</div>
                    <h1>Turn training data into something AI can actually use.</h1>
                    <p class="lead">
                        Upload your Garmin export ZIP and get clean JSON for ChatGPT, Claude, and Gemini.
                        No analysis inside the app. Just structured data, ready for your AI workflow.
                    </p>

                    <div class="bullets">
                        <div class="chip">Daily summary</div>
                        <div class="chip">Sleep</div>
                        <div class="chip">Workouts</div>
                        <div class="chip">Free: 7 days</div>
                        <div class="chip">3 exports / month</div>
                    </div>

                    <div class="preview">
<pre style="margin:0; white-space:pre-wrap;">{
  <span class="dim">"source"</span>: "garmin",
  <span class="dim">"date_range"</span>: { "start": "2026-03-01", "end": "2026-03-07" },
  <span class="dim">"daily_summary"</span>: [...],
  <span class="dim">"sleep"</span>: [...],
  <span class="dim">"workouts"</span>: [...]
}</pre>
                    </div>
                </div>

                <div class="card">
                    <h2>Generate dataset</h2>
                    <p>
                        Export your Garmin data, choose a date range, and download a clean dataset JSON.
                    </p>

                    <form action="/upload" method="post" enctype="multipart/form-data">
                        <label for="file">Garmin export ZIP</label>
                        <input type="file" id="file" name="file" accept=".zip" required />

                        <div class="row">
                            <div>
                                <label for="start_date">Start date</label>
                                <input type="date" id="start_date" name="start_date" required />
                            </div>
                            <div>
                                <label for="end_date">End date</label>
                                <input type="date" id="end_date" name="end_date" required />
                            </div>
                        </div>

                        <label for="plan">Plan</label>
                        <select id="plan" name="plan" required>
                            <option value="free" selected>Free</option>
                            <option value="pro">Pro</option>
                        </select>

                        <button type="submit">Generate dataset</button>
                    </form>

                    <div class="plan-box">
                        <strong>Free</strong>: up to 7 days per export, 3 exports per month.<br>
                        <strong>Pro</strong>: up to 365 days per export.
                    </div>

                    <div class="foot">
                        Supported today: Garmin. Strava coming later.
                    </div>
                </div>
            </section>
        </div>
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
    except Exception:
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
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
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

    with open(USAGE_FILE, "w", encoding="utf-8") as f:
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

    if not file.filename or not file.filename.lower().endswith(".zip"):
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

            for root_dir, _, files in os.walk(temp_dir):
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
                        distance = item.get("totalDistanceMeters")

                        daily_summary.append({
                            "date": date_str,
                            "steps": item.get("totalSteps"),
                            "total_calories": item.get("totalKilocalories"),
                            "active_calories": item.get("activeKilocalories"),
                            "distance_m": distance,
                            "distance_km": round(distance / 1000, 2) if distance is not None else None,
                            "resting_hr": item.get("restingHeartRate")
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
                            "sleep_start": parse_garmin_datetime(item.get("sleepStartTimestampGMT")),
                            "sleep_end": parse_garmin_datetime(item.get("sleepEndTimestampGMT")),
                            "deep_sleep_min": round((item.get("deepSleepSeconds") or 0) / 60),
                            "light_sleep_min": round((item.get("lightSleepSeconds") or 0) / 60),
                            "rem_sleep_min": round((item.get("remSleepSeconds") or 0) / 60)
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

                    if not isinstance(start_time, (int, float)):
                        continue

                    workout_date = datetime.fromtimestamp(start_time / 1000, tz=timezone.utc).date()

                    if start_dt <= workout_date <= end_dt:
                        dist = act.get("distance")
                        dur = act.get("duration")

                        workouts.append({
                            "date": workout_date.isoformat(),
                            "sport": act.get("sportType"),
                            "distance_km": round(dist / 100000, 2) if dist is not None else None,
                            "duration_min": round(dur / 60000, 1) if dur is not None else None,
                            "avg_hr": act.get("avgHr"),
                            "max_hr": act.get("maxHr"),
                            "start_time_utc_iso": datetime.fromtimestamp(
                                start_time / 1000, tz=timezone.utc
                            ).isoformat()
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
