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
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>train2ai</title>
<style>
    * {
        box-sizing: border-box;
    }

    body {
        margin: 0;
        font-family: Arial, sans-serif;
        background: #f4f6fb;
        color: #111827;
    }

    .page {
        max-width: 1200px;
        margin: 0 auto;
        padding: 40px 24px 80px;
    }

    .hero {
        display: grid;
        grid-template-columns: 1.2fr 0.8fr;
        gap: 40px;
        align-items: start;
    }

    h1 {
        font-size: 64px;
        margin: 0 0 10px;
        line-height: 1;
    }

    .subtitle {
        font-size: 18px;
        color: #4b5563;
        margin-bottom: 40px;
    }

    .lead {
        font-size: 18px;
        line-height: 1.5;
        max-width: 760px;
        margin-bottom: 24px;
    }

    .code-box {
        background: #05070b;
        color: #f3f4f6;
        border-radius: 18px;
        padding: 24px;
        margin-top: 28px;
        overflow-x: auto;
        box-shadow: 0 10px 30px rgba(0,0,0,0.15);
    }

    .code-box pre {
        margin: 0;
        font-size: 15px;
        line-height: 1.45;
        white-space: pre-wrap;
    }

    .form-card {
        background: white;
        border-radius: 24px;
        padding: 28px;
        box-shadow: 0 12px 35px rgba(0,0,0,0.08);
    }

    .form-card h2 {
        font-size: 28px;
        margin: 0 0 24px;
    }

    label {
        display: block;
        font-size: 15px;
        font-weight: 700;
        margin-top: 18px;
        margin-bottom: 8px;
    }

    input[type="file"],
    input[type="date"],
    select,
    button {
        width: 100%;
        padding: 14px 16px;
        border: 1px solid #d1d5db;
        border-radius: 14px;
        font-size: 16px;
        background: white;
    }

    .row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
    }

    button {
        margin-top: 24px;
        background: #000;
        color: white;
        border: none;
        font-weight: 700;
        cursor: pointer;
    }

    button:hover {
        opacity: 0.94;
    }

    button:disabled {
        opacity: 0.7;
        cursor: not-allowed;
    }

    .message {
        margin-top: 14px;
        font-size: 14px;
        min-height: 22px;
        font-weight: 700;
    }

    .plan-note {
        margin-top: 16px;
        font-size: 14px;
        color: #6b7280;
        line-height: 1.6;
    }

    .section {
        margin-top: 72px;
    }

    .section h2 {
        font-size: 34px;
        margin-bottom: 20px;
    }

    .steps {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
    }

    .step {
        background: white;
        border-radius: 18px;
        padding: 22px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.05);
    }

    .step-num {
        font-size: 14px;
        font-weight: 700;
        color: #2563eb;
        margin-bottom: 10px;
    }

    .step h3 {
        margin: 0 0 10px;
        font-size: 20px;
    }

    .step p {
        margin: 0;
        color: #4b5563;
        line-height: 1.6;
    }

    @media (max-width: 960px) {
        .hero {
            grid-template-columns: 1fr;
        }

        .steps {
            grid-template-columns: 1fr;
        }

        h1 {
            font-size: 48px;
        }
    }

    @media (max-width: 640px) {
        .row {
            grid-template-columns: 1fr;
        }

        .page {
            padding: 28px 16px 60px;
        }

        h1 {
            font-size: 42px;
        }
    }
</style>
</head>
<body>
<div class="page">

    <div class="hero">
        <div>
            <h1>train2ai</h1>
            <div class="subtitle">Turn Garmin exports into AI-ready datasets</div>

            <p class="lead">
                Upload your Garmin export ZIP and get clean JSON for ChatGPT, Claude, or Gemini.
                train2ai does not analyze your data — it prepares it for AI.
            </p>

            <div class="code-box">
<pre>{
  "source": "garmin",
  "date_range": {
    "start": "2026-02-06",
    "end": "2026-02-12"
  },
  "daily_summary": [...],
  "sleep": [...],
  "workouts": [...]
}</pre>
            </div>
        </div>

        <div class="form-card">
            <h2>Generate dataset</h2>

            <form id="uploadForm">
                <label for="file">Garmin export ZIP</label>
                <input type="file" id="file" name="file" accept=".zip" required>

                <div class="row">
                    <div>
                        <label for="start_date">Start date</label>
                        <input type="date" id="start_date" name="start_date" required>
                    </div>

                    <div>
                        <label for="end_date">End date</label>
                        <input type="date" id="end_date" name="end_date" required>
                    </div>
                </div>

                <label for="plan">Plan</label>
                <select id="plan" name="plan">
                    <option value="free">Free</option>
                    <option value="pro">Pro</option>
                </select>

                <button type="submit">Generate dataset</button>
            </form>

            <div id="message" class="message"></div>

            <div class="plan-note">
                Free: 7 days per export · 3 exports per month
            </div>
        </div>
    </div>

    <div class="section">
        <h2>How it works</h2>

        <div class="steps">
            <div class="step">
                <div class="step-num">Step 1</div>
                <h3>Export from Garmin Connect</h3>
                <p>Download your Garmin data export as a ZIP file.</p>
            </div>

            <div class="step">
                <div class="step-num">Step 2</div>
                <h3>Upload the ZIP here</h3>
                <p>Select your date range and choose your plan.</p>
            </div>

            <div class="step">
                <div class="step-num">Step 3</div>
                <h3>Download clean JSON</h3>
                <p>Use the dataset with ChatGPT, Claude, or Gemini.</p>
            </div>
        </div>
    </div>

</div>

<script>
const form = document.getElementById("uploadForm");
const message = document.getElementById("message");
const submitButton = form.querySelector("button[type='submit']");

form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const startDate = form.querySelector('input[name="start_date"]').value;
    const endDate = form.querySelector('input[name="end_date"]').value;
    const plan = form.querySelector('select[name="plan"]').value;

    if (!startDate || !endDate) {
        message.textContent = "Please select both start date and end date.";
        message.style.color = "#dc2626";
        return;
    }

    const start = new Date(startDate);
    const end = new Date(endDate);
    const days = Math.floor((end - start) / (1000 * 60 * 60 * 24)) + 1;

    if (end < start) {
        message.textContent = "End date must be on or after start date.";
        message.style.color = "#dc2626";
        return;
    }

    if (plan === "free" && days > 7) {
        message.textContent = "Free plan supports up to 7 days per export.";
        message.style.color = "#dc2626";
        return;
    }

    if (plan === "pro" && days > 365) {
        message.textContent = "Pro plan supports up to 365 days per export.";
        message.style.color = "#dc2626";
        return;
    }

    message.textContent = "Processing ZIP file...";
    message.style.color = "#4b5563";
    submitButton.disabled = true;
    submitButton.textContent = "Processing...";

    const formData = new FormData(form);

    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: formData
        });

        const contentType = response.headers.get("content-type") || "";

        if (!response.ok) {
            let errorMessage = "Something went wrong.";

            try {
                if (contentType.includes("application/json")) {
                    const err = await response.json();
                    errorMessage = err.detail || errorMessage;
                } else {
                    const text = await response.text();
                    if (text) {
                        errorMessage = text;
                    }
                }
            } catch (_) {
                errorMessage = "Request failed. Please check your input and try again.";
            }

            message.textContent = errorMessage;
            message.style.color = "#dc2626";
            return;
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.href = url;
        a.download = "train2ai_dataset.json";
        document.body.appendChild(a);
        a.click();
        a.remove();

        window.URL.revokeObjectURL(url);

        message.textContent = "Dataset downloaded.";
        message.style.color = "#16a34a";
    } catch (error) {
        message.textContent = "Network error. Please try again.";
        message.style.color = "#dc2626";
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = "Generate dataset";
    }
});
</script>

</body>
</html>
"""


def parse_input_date(date_str, field):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field}"
        )


def parse_garmin_datetime(dt):
    if not dt:
        return None

    try:
        return datetime.fromisoformat(dt).isoformat()
    except Exception:
        return None


def enforce_plan_limit(plan, start, end):
    days = (end - start).days + 1

    if plan == "free" and days > 7:
        raise HTTPException(
            status_code=400,
            detail="Free plan supports up to 7 days per export."
        )

    if plan == "pro" and days > 365:
        raise HTTPException(
            status_code=400,
            detail="Pro plan supports up to 365 days."
        )


def check_usage_limit(ip, plan):
    if plan != "free":
        return

    now = datetime.utcnow()
    month = now.strftime("%Y-%m")

    if Path(USAGE_FILE).exists():
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}

    if month not in data:
        data[month] = {}

    count = data[month].get(ip, 0)

    if count >= FREE_MONTHLY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Free plan monthly limit reached (3 exports)."
        )

    data[month][ip] = count + 1

    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


@app.post("/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    plan: str = Form("free")
):
    ip = request.client.host

    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload a Garmin export zip")

    start = parse_input_date(start_date, "start_date")
    end = parse_input_date(end_date, "end_date")

    if start > end:
        raise HTTPException(status_code=400, detail="Invalid date range")

    enforce_plan_limit(plan, start, end)
    check_usage_limit(ip, plan)

    try:
        with tempfile.TemporaryDirectory() as temp:
            zip_path = os.path.join(temp, file.filename)

            with open(zip_path, "wb") as f:
                f.write(await file.read())

            with zipfile.ZipFile(zip_path) as zip_ref:
                zip_ref.extractall(temp)

            uds = []
            sleep_files = []
            workout_files = []

            for root, dirs, files in os.walk(temp):
                for name in files:
                    lower = name.lower()
                    path = os.path.join(root, name)

                    if lower.startswith("udsfile_") and lower.endswith(".json"):
                        uds.append(path)

                    if lower.endswith("_sleepdata.json"):
                        sleep_files.append(path)

                    if "summarizedactivities" in lower and lower.endswith(".json"):
                        workout_files.append(path)

            daily = []

            for file_path in uds:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    continue

                if not isinstance(data, list):
                    continue

                for item in data:
                    date = item.get("calendarDate")
                    if not date:
                        continue

                    try:
                        d = datetime.strptime(date, "%Y-%m-%d").date()
                    except ValueError:
                        continue

                    if start <= d <= end:
                        dist = item.get("totalDistanceMeters")

                        daily.append({
                            "date": date,
                            "steps": item.get("totalSteps"),
                            "distance_km": round(dist / 1000, 2) if dist is not None else None,
                            "resting_hr": item.get("restingHeartRate")
                        })

            sleep_out = []

            for file_path in sleep_files:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    continue

                if not isinstance(data, list):
                    continue

                for item in data:
                    date = item.get("calendarDate")
                    if not date:
                        continue

                    try:
                        d = datetime.strptime(date, "%Y-%m-%d").date()
                    except ValueError:
                        continue

                    if start <= d <= end:
                        sleep_out.append({
                            "date": date,
                            "sleep_start": parse_garmin_datetime(item.get("sleepStartTimestampGMT")),
                            "sleep_end": parse_garmin_datetime(item.get("sleepEndTimestampGMT"))
                        })

            workouts_out = []

            for file_path in workout_files:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
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

                    date = datetime.fromtimestamp(start_time / 1000, tz=timezone.utc).date()

                    if start <= date <= end:
                        dist = act.get("distance")
                        dur = act.get("duration")

                        workouts_out.append({
                            "date": date.isoformat(),
                            "sport": act.get("sportType"),
                            "distance_km": round(dist / 100000, 2) if dist is not None else None,
                            "duration_min": round(dur / 60000, 1) if dur is not None else None
                        })

            result = {
                "source": "garmin",
                "plan": plan,
                "date_range": {
                    "start": start_date,
                    "end": end_date
                },
                "daily_summary": sorted(daily, key=lambda x: x["date"]),
                "sleep": sorted(sleep_out, key=lambda x: x["date"]),
                "workouts": sorted(workouts_out, key=lambda x: x["date"])
            }

            json_str = json.dumps(result, indent=2, ensure_ascii=False)

            return Response(
                content=json_str,
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=train2ai_dataset.json"}
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
