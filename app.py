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

FREE_TOTAL_LIMIT = 3
FREE_MAX_DAYS = 7
PRO_MAX_DAYS = 365

ALLOWED_DATA = {"daily_summary", "sleep", "workouts"}


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
    * { box-sizing: border-box; }

    body {
        margin: 0;
        font-family: Arial, sans-serif;
        background: #f4f6fb;
        color: #111827;
    }

    .page {
        max-width: 1120px;
        margin: 0 auto;
        padding: 40px 20px 80px;
    }

    .hero {
        display: grid;
        grid-template-columns: 1.2fr 0.8fr;
        gap: 36px;
        align-items: start;
    }

    h1 {
        font-size: 60px;
        margin: 0 0 10px;
        line-height: 1;
    }

    .subtitle {
        color: #4b5563;
        font-size: 20px;
        margin-bottom: 24px;
    }

    .lead {
        font-size: 18px;
        line-height: 1.65;
        color: #374151;
        margin-bottom: 24px;
        max-width: 720px;
    }

    .chips {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-bottom: 24px;
    }

    .chip {
        background: white;
        border: 1px solid #dbe1ea;
        border-radius: 999px;
        padding: 8px 12px;
        font-size: 14px;
        color: #374151;
    }

    .code-box {
        background: #05070b;
        color: #f3f4f6;
        border-radius: 18px;
        padding: 22px;
        overflow-x: auto;
        box-shadow: 0 10px 28px rgba(0,0,0,0.16);
    }

    .code-box pre {
        margin: 0;
        font-size: 14px;
        line-height: 1.5;
        white-space: pre-wrap;
    }

    .form-card {
        background: white;
        padding: 26px;
        border-radius: 22px;
        box-shadow: 0 12px 30px rgba(0,0,0,0.08);
    }

    .form-card h2 {
        margin: 0 0 10px;
        font-size: 28px;
    }

    .form-card p {
        margin: 0 0 18px;
        color: #6b7280;
        line-height: 1.6;
        font-size: 14px;
    }

    label {
        display: block;
        font-weight: 700;
        margin-top: 16px;
        margin-bottom: 8px;
        font-size: 14px;
    }

    input, select, button {
        width: 100%;
        padding: 13px 14px;
        border-radius: 12px;
        border: 1px solid #d1d5db;
        font-size: 15px;
        background: white;
    }

    input[type="checkbox"] {
        width: auto;
        padding: 0;
        border: none;
        border-radius: 0;
        margin: 0;
    }

    .row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 14px;
    }

    .checkbox-group {
        margin-top: 8px;
        display: grid;
        gap: 10px;
    }

    .checkbox-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 12px;
        border: 1px solid #dbe1ea;
        border-radius: 12px;
        background: #fafbfc;
    }

    .checkbox-item label {
        margin: 0;
        font-weight: 600;
        font-size: 14px;
        cursor: pointer;
    }

    .plan-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        margin-top: 8px;
    }

    .plan-card {
        border: 1px solid #dbe1ea;
        border-radius: 16px;
        padding: 14px;
        background: #fafbfc;
    }

    .plan-card.active {
        border: 2px solid #111827;
        background: #ffffff;
    }

    .plan-title {
        font-weight: 700;
        margin-bottom: 6px;
    }

    .plan-meta {
        font-size: 13px;
        color: #6b7280;
        line-height: 1.6;
    }

    .coming-soon {
        display: inline-block;
        margin-left: 8px;
        font-size: 12px;
        color: #2563eb;
        font-weight: 700;
    }

    button {
        margin-top: 18px;
        background: #111827;
        color: white;
        border: none;
        cursor: pointer;
        font-weight: 700;
    }

    button:hover { opacity: 0.95; }

    button:disabled {
        opacity: 0.65;
        cursor: not-allowed;
    }

    .message {
        margin-top: 14px;
        min-height: 22px;
        font-size: 14px;
        font-weight: 700;
    }

    .plan-note {
        margin-top: 14px;
        font-size: 14px;
        color: #6b7280;
        line-height: 1.7;
    }

    .small-note {
        margin-top: 10px;
        font-size: 12px;
        color: #6b7280;
        line-height: 1.6;
    }

    .section {
        margin-top: 72px;
    }

    .section h2 {
        font-size: 34px;
        margin: 0 0 18px;
    }

    .section p.section-lead {
        color: #4b5563;
        line-height: 1.7;
        max-width: 780px;
        margin-bottom: 22px;
    }

    .steps {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
    }

    .step {
        background: white;
        padding: 22px;
        border-radius: 18px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.05);
    }

    .step-num {
        color: #2563eb;
        font-weight: 700;
        margin-bottom: 8px;
        font-size: 14px;
    }

    .step h3 {
        margin: 0 0 10px;
        font-size: 20px;
    }

    .step p {
        margin: 0;
        color: #4b5563;
        line-height: 1.65;
        font-size: 15px;
    }

    .grid-3 {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
    }

    .info-card {
        background: white;
        padding: 22px;
        border-radius: 18px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.05);
    }

    .info-card h3 {
        margin: 0 0 12px;
        font-size: 22px;
    }

    .info-card ul {
        margin: 0;
        padding-left: 20px;
        color: #4b5563;
        line-height: 1.9;
    }

    .grid-2 {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
    }

    .privacy-box {
        background: white;
        padding: 22px;
        border-radius: 18px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.05);
        color: #4b5563;
        line-height: 1.8;
    }

    footer {
        margin-top: 72px;
        padding-top: 22px;
        border-top: 1px solid #dbe1ea;
        color: #6b7280;
        font-size: 14px;
    }

    @media (max-width: 960px) {
        .hero, .steps, .grid-2, .grid-3, .plan-grid {
            grid-template-columns: 1fr;
        }

        h1 { font-size: 46px; }
    }

    @media (max-width: 640px) {
        .row {
            grid-template-columns: 1fr;
        }

        .page {
            padding: 28px 16px 56px;
        }

        h1 { font-size: 40px; }
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
                train2ai does not analyze your data. It prepares your Garmin data for AI tools.
            </p>

            <div class="chips">
                <div class="chip">Daily summary</div>
                <div class="chip">Sleep</div>
                <div class="chip">Workouts</div>
                <div class="chip">Free: 7 days</div>
                <div class="chip">3 exports total</div>
                <div class="chip">Garmin supported</div>
                <div class="chip">Strava coming soon</div>
            </div>

            <div class="code-box">
<pre>{
  "source": "garmin",
  "schema_version": "1.1",
  "plan": "free",
  "date_range": {
    "start": "2026-01-01",
    "end": "2026-01-06"
  },
  "included_data": [
    "daily_summary",
    "sleep",
    "workouts"
  ],
  "daily_summary": [
    {
      "date": "2026-01-01",
      "steps": 8120,
      "total_calories": 2410.0,
      "active_calories": 534.0,
      "distance_km": 6.3,
      "resting_hr": 41
    }
  ],
  "sleep": [
    {
      "date": "2026-01-01",
      "sleep_start": "2025-12-31T14:12:00",
      "sleep_end": "2026-01-01T00:48:00",
      "deep_sleep_min": 72,
      "light_sleep_min": 248,
      "rem_sleep_min": 88
    }
  ],
  "workouts": [
    {
      "date": "2026-01-04",
      "sport": "CYCLING",
      "distance_km": 40.01,
      "duration_min": 205.3,
      "avg_hr": 128.0,
      "max_hr": 168.0
    }
  ],
  "record_counts": {
    "daily_summary": 6,
    "sleep": 6,
    "workouts": 4
  }
}</pre>
            </div>
        </div>

        <div class="form-card">
            <h2>Generate dataset</h2>
            <p>
                Upload your Garmin export ZIP, choose a date range, and download AI-ready JSON.
            </p>

            <div class="plan-grid">
                <div class="plan-card active">
                    <div class="plan-title">Free</div>
                    <div class="plan-meta">
                        Up to 7 days per export<br>
                        3 exports total
                    </div>
                </div>
                <div class="plan-card">
                    <div class="plan-title">Pro <span class="coming-soon">Coming soon</span></div>
                    <div class="plan-meta">
                        Up to 365 days per export<br>
                        More sources and more data
                    </div>
                </div>
            </div>

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
                    <option value="free" selected>Free</option>
                    <option value="pro" disabled>Pro (coming soon)</option>
                </select>

                <label>Choose data to include</label>
                <div class="checkbox-group">
                    <div class="checkbox-item">
                        <input type="checkbox" id="daily_summary" name="included_data" value="daily_summary" checked>
                        <label for="daily_summary">Daily summary</label>
                    </div>

                    <div class="checkbox-item">
                        <input type="checkbox" id="sleep" name="included_data" value="sleep" checked>
                        <label for="sleep">Sleep</label>
                    </div>

                    <div class="checkbox-item">
                        <input type="checkbox" id="workouts" name="included_data" value="workouts" checked>
                        <label for="workouts">Workouts</label>
                    </div>
                </div>

                <button type="submit">Generate dataset</button>
            </form>

            <div id="message" class="message"></div>

            <div class="plan-note">
                <strong>Free plan</strong><br>
                • Up to 7 days per export<br>
                • 3 exports total<br><br>
                <strong>Pro plan</strong><br>
                • Coming soon
            </div>

            <div class="small-note">
                This tool prepares structured JSON only. It does not provide in-app coaching or AI analysis.
            </div>
        </div>
    </div>

    <div class="section">
        <h2>How it works</h2>
        <p class="section-lead">
            train2ai is for athletes and data-focused users who want structured Garmin data for AI analysis.
        </p>

        <div class="steps">
            <div class="step">
                <div class="step-num">Step 1</div>
                <h3>Export from Garmin Connect</h3>
                <p>Request and download your Garmin data export as a ZIP file.</p>
            </div>

            <div class="step">
                <div class="step-num">Step 2</div>
                <h3>Choose data and date range</h3>
                <p>Select the period and the data types you want in the output.</p>
            </div>

            <div class="step">
                <div class="step-num">Step 3</div>
                <h3>Download clean JSON</h3>
                <p>Use the resulting dataset with ChatGPT, Claude, Gemini, or other AI tools.</p>
            </div>
        </div>
    </div>

    <div class="section">
        <h2>How to export your Garmin data</h2>
        <p class="section-lead">
            train2ai works with the official Garmin Connect export.
        </p>

        <div class="steps">
            <div class="step">
                <div class="step-num">1</div>
                <h3>Open Garmin Connect</h3>
                <p>Go to Garmin Connect and open your account settings.</p>
            </div>

            <div class="step">
                <div class="step-num">2</div>
                <h3>Request data export</h3>
                <p>Navigate to Data Management and request a full export ZIP.</p>
            </div>

            <div class="step">
                <div class="step-num">3</div>
                <h3>Download ZIP</h3>
                <p>Garmin sends a download link. Download the ZIP and upload it here.</p>
            </div>
        </div>
    </div>

    <div class="section">
        <h2>What you get</h2>
        <p class="section-lead">
            train2ai extracts structured Garmin data and returns it in a format that is easy for both humans and AI tools to read.
        </p>

        <div class="grid-3">
            <div class="info-card">
                <h3>Daily summary</h3>
                <ul>
                    <li>date</li>
                    <li>steps</li>
                    <li>total_calories</li>
                    <li>active_calories</li>
                    <li>distance_km</li>
                    <li>resting_hr</li>
                </ul>
            </div>

            <div class="info-card">
                <h3>Sleep</h3>
                <ul>
                    <li>date</li>
                    <li>sleep_start</li>
                    <li>sleep_end</li>
                    <li>deep_sleep_min</li>
                    <li>light_sleep_min</li>
                    <li>rem_sleep_min</li>
                </ul>
            </div>

            <div class="info-card">
                <h3>Workouts</h3>
                <ul>
                    <li>date</li>
                    <li>sport</li>
                    <li>distance_km</li>
                    <li>duration_min</li>
                    <li>avg_hr</li>
                    <li>max_hr</li>
                </ul>
            </div>
        </div>
    </div>

    <div class="section">
        <h2>Supported data</h2>
        <div class="grid-2">
            <div class="info-card">
                <h3>Included</h3>
                <ul>
                    <li>Daily summary</li>
                    <li>Sleep totals</li>
                    <li>Workout summaries</li>
                    <li>included_data in output JSON</li>
                    <li>record_counts in output JSON</li>
                </ul>
            </div>

            <div class="info-card">
                <h3>Not included</h3>
                <ul>
                    <li>No workout GPS track</li>
                    <li>No second-by-second workout time series</li>
                    <li>No sleep stage timeline</li>
                    <li>No in-app AI analysis</li>
                    <li>No coaching inside the app</li>
                </ul>
            </div>
        </div>
    </div>

    <div class="section">
        <h2>Example output</h2>
        <div class="code-box">
<pre>{
  "source": "garmin",
  "schema_version": "1.1",
  "plan": "free",
  "date_range": {
    "start": "2026-01-01",
    "end": "2026-01-06"
  },
  "included_data": [
    "daily_summary",
    "sleep",
    "workouts"
  ],
  "daily_summary": [
    {
      "date": "2026-01-01",
      "steps": 8120,
      "total_calories": 2410.0,
      "active_calories": 534.0,
      "distance_km": 6.3,
      "resting_hr": 41
    }
  ],
  "sleep": [
    {
      "date": "2026-01-01",
      "sleep_start": "2025-12-31T14:12:00",
      "sleep_end": "2026-01-01T00:48:00",
      "deep_sleep_min": 72,
      "light_sleep_min": 248,
      "rem_sleep_min": 88
    }
  ],
  "workouts": [
    {
      "date": "2026-01-04",
      "sport": "CYCLING",
      "distance_km": 40.01,
      "duration_min": 205.3,
      "avg_hr": 128.0,
      "max_hr": 168.0
    }
  ],
  "record_counts": {
    "daily_summary": 6,
    "sleep": 6,
    "workouts": 4
  }
}</pre>
        </div>
    </div>

    <div class="section">
        <h2>Privacy</h2>
        <div class="privacy-box">
            Uploaded files are processed temporarily to generate the dataset.
            train2ai is a data-preparation tool, not a coaching platform.
            The service prepares your Garmin data for AI use and does not perform in-app analysis.
        </div>
    </div>

    <footer>
        train2ai — Fitness data → AI-ready dataset
    </footer>

</div>

<script>
function parseDateOnly(value) {
    const parts = value.split("-");
    if (parts.length !== 3) return null;
    const y = Number(parts[0]);
    const m = Number(parts[1]);
    const d = Number(parts[2]);
    if (!y || !m || !d) return null;
    return { y, m, d };
}

function diffDaysInclusive(startStr, endStr) {
    const s = parseDateOnly(startStr);
    const e = parseDateOnly(endStr);
    if (!s || !e) return null;

    const startUTC = Date.UTC(s.y, s.m - 1, s.d);
    const endUTC = Date.UTC(e.y, e.m - 1, e.d);

    return Math.floor((endUTC - startUTC) / (1000 * 60 * 60 * 24)) + 1;
}

const form = document.getElementById("uploadForm");
const message = document.getElementById("message");
const submitButton = form.querySelector("button[type='submit']");

form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const startDate = form.querySelector('input[name="start_date"]').value;
    const endDate = form.querySelector('input[name="end_date"]').value;
    const plan = form.querySelector('select[name="plan"]').value;
    const checkedData = Array.from(form.querySelectorAll('input[name="included_data"]:checked')).map(el => el.value);

    if (!startDate || !endDate) {
        message.textContent = "Please select both start date and end date.";
        message.style.color = "#dc2626";
        return;
    }

    if (checkedData.length === 0) {
        message.textContent = "Please select at least one data type.";
        message.style.color = "#dc2626";
        return;
    }

    const days = diffDaysInclusive(startDate, endDate);
    if (days === null) {
        message.textContent = "Invalid date format.";
        message.style.color = "#dc2626";
        return;
    }

    if (days < 1) {
        message.textContent = "End date must be on or after start date.";
        message.style.color = "#dc2626";
        return;
    }

    if (plan === "free" && days > 7) {
        message.textContent = "Free plan supports up to 7 days per export.";
        message.style.color = "#dc2626";
        return;
    }

    if (plan === "pro") {
        message.textContent = "Pro is coming soon. Please use Free for now.";
        message.style.color = "#dc2626";
        return;
    }

    message.innerHTML = "Processing Garmin export...<br><span style='font-size:13px;color:#6b7280;font-weight:400;'>This may take up to ~1 minute depending on file size.</span>";
    message.style.color = "#374151";

    submitButton.disabled = true;
    submitButton.textContent = "Processing...";

    const formData = new FormData(form);

    try {
        const res = await fetch("/upload", {
            method: "POST",
            body: formData
        });

        const contentType = res.headers.get("content-type") || "";

        if (!res.ok) {
            let errorMessage = "Something went wrong.";

            try {
                if (contentType.includes("application/json")) {
                    const err = await res.json();
                    errorMessage = err.detail || errorMessage;
                } else {
                    const text = await res.text();
                    if (text) errorMessage = text;
                }
            } catch (_) {
                errorMessage = "Request failed. Please check your input and try again.";
            }

            message.textContent = errorMessage;
            message.style.color = "#dc2626";
            return;
        }

        const blob = await res.blob();
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


@app.get("/health")
def health():
    return {"status": "ok"}


def parse_input_date(date_str: str, field: str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {field}.")


def parse_garmin_datetime(dt):
    if not dt:
        return None
    try:
        return datetime.fromisoformat(dt).isoformat()
    except Exception:
        return None


def normalize_included_data(values):
    cleaned = []
    for v in values:
        if v in ALLOWED_DATA and v not in cleaned:
            cleaned.append(v)
    return cleaned


def validate_plan(plan: str):
    if plan not in {"free", "pro"}:
        raise HTTPException(status_code=400, detail="Invalid plan.")

    if plan == "pro":
        raise HTTPException(status_code=403, detail="Pro is coming soon. Please use Free for now.")


def enforce_plan_limit(plan, start, end):
    days = (end - start).days + 1

    if plan == "free" and days > FREE_MAX_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Free plan supports up to {FREE_MAX_DAYS} days per export."
        )

    if plan == "pro" and days > PRO_MAX_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Pro plan supports up to {PRO_MAX_DAYS} days per export."
        )


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def load_usage():
    if Path(USAGE_FILE).exists():
        try:
            with open(USAGE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {"free_total_by_ip": {}}


def save_usage(data):
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def check_usage_limit(ip, plan):
    if plan != "free":
        return

    data = load_usage()
    totals = data.get("free_total_by_ip", {})
    count = totals.get(ip, 0)

    if count >= FREE_TOTAL_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Free plan total limit reached ({FREE_TOTAL_LIMIT} exports)."
        )

    totals[ip] = count + 1
    data["free_total_by_ip"] = totals
    save_usage(data)


def collect_daily_summary(uds_files, start, end):
    daily_summary = []

    for file_path in uds_files:
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
                daily_summary.append({
                    "date": date,
                    "steps": item.get("totalSteps"),
                    "total_calories": item.get("totalKilocalories"),
                    "active_calories": item.get("activeKilocalories"),
                    "distance_km": round(dist / 1000, 2) if dist is not None else None,
                    "resting_hr": item.get("restingHeartRate")
                })

    return sorted(daily_summary, key=lambda x: x["date"])


def collect_sleep(sleep_files, start, end):
    sleep = []

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
                sleep.append({
                    "date": date,
                    "sleep_start": parse_garmin_datetime(item.get("sleepStartTimestampGMT")),
                    "sleep_end": parse_garmin_datetime(item.get("sleepEndTimestampGMT")),
                    "deep_sleep_min": round((item.get("deepSleepSeconds") or 0) / 60),
                    "light_sleep_min": round((item.get("lightSleepSeconds") or 0) / 60),
                    "rem_sleep_min": round((item.get("remSleepSeconds") or 0) / 60)
                })

    return sorted(sleep, key=lambda x: x["date"])


def collect_workouts(workout_files, start, end):
    workouts = []

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

                workouts.append({
                    "date": date.isoformat(),
                    "sport": act.get("sportType"),
                    "distance_km": round(dist / 100000, 2) if dist is not None else None,
                    "duration_min": round(dur / 60000, 1) if dur is not None else None,
                    "avg_hr": act.get("avgHr"),
                    "max_hr": act.get("maxHr")
                })

    return sorted(workouts, key=lambda x: x["date"])


@app.post("/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    plan: str = Form("free"),
    included_data: list[str] = Form(...)
):
    ip = get_client_ip(request)

    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload a Garmin export ZIP.")

    validate_plan(plan)

    selected = normalize_included_data(included_data)
    if len(selected) == 0:
        raise HTTPException(status_code=400, detail="Please select at least one data type.")

    start = parse_input_date(start_date, "start_date")
    end = parse_input_date(end_date, "end_date")

    if start > end:
        raise HTTPException(status_code=400, detail="End date must be on or after start date.")

    enforce_plan_limit(plan, start, end)
    check_usage_limit(ip, plan)

    try:
        with tempfile.TemporaryDirectory() as temp:
            zip_path = os.path.join(temp, file.filename)

            with open(zip_path, "wb") as f:
                f.write(await file.read())

            with zipfile.ZipFile(zip_path) as zip_ref:
                zip_ref.extractall(temp)

            uds_files = []
            sleep_files = []
            workout_files = []

            for root, _, files in os.walk(temp):
                for name in files:
                    lower = name.lower()
                    path = os.path.join(root, name)

                    if lower.startswith("udsfile_") and lower.endswith(".json"):
                        uds_files.append(path)
                    elif lower.endswith("_sleepdata.json"):
                        sleep_files.append(path)
                    elif "summarizedactivities" in lower and lower.endswith(".json"):
                        workout_files.append(path)

            daily_summary = collect_daily_summary(uds_files, start, end) if "daily_summary" in selected else []
            sleep = collect_sleep(sleep_files, start, end) if "sleep" in selected else []
            workouts = collect_workouts(workout_files, start, end) if "workouts" in selected else []

            result = {
                "source": "garmin",
                "schema_version": "1.1",
                "plan": plan,
                "date_range": {
                    "start": start_date,
                    "end": end_date
                },
                "included_data": selected,
                "daily_summary": daily_summary if "daily_summary" in selected else [],
                "sleep": sleep if "sleep" in selected else [],
                "workouts": workouts if "workouts" in selected else [],
                "record_counts": {
                    "daily_summary": len(daily_summary) if "daily_summary" in selected else 0,
                    "sleep": len(sleep) if "sleep" in selected else 0,
                    "workouts": len(workouts) if "workouts" in selected else 0
                }
            }

            json_str = json.dumps(result, indent=2, ensure_ascii=False)

            return Response(
                content=json_str,
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=train2ai_dataset.json"}
            )

    except HTTPException:
        raise
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
