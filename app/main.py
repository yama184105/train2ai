from __future__ import annotations

import json
import os
import tempfile
import zipfile

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response

from app.config import (
    ALLOWED_MODES,
    ALLOWED_SOURCES,
    ALLOWED_SPORTS,
    ANALYSIS_RECENT_CHOICES,
    FREE_MAX_DAYS,
    FREE_TOTAL_LIMIT,
    PRO_MAX_DAYS,
)
from app.providers import garmin, strava
from app.utils.dates import parse_input_date
from app.utils.usage import (
    check_usage_limit_only,
    get_client_ip,
    get_usage_count,
    increment_usage,
)

app = FastAPI(title="train2ai")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>train2ai</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 920px; margin: 40px auto; padding: 0 16px; color: #111827; }}
.card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 16px; padding: 20px; margin-bottom: 20px; }}
label {{ display: block; font-weight: 700; margin-top: 14px; margin-bottom: 6px; }}
input, select, button {{ width: 100%; padding: 12px; border-radius: 10px; border: 1px solid #d1d5db; }}
button {{ background: #111827; color: white; border: none; font-weight: 700; margin-top: 20px; cursor: pointer; }}
pre {{ overflow-x: auto; background: #0b1020; color: #f3f4f6; padding: 16px; border-radius: 12px; }}
.small {{ color: #6b7280; font-size: 14px; line-height: 1.6; }}
.row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
@media (max-width: 700px) {{ .row {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<h1>train2ai</h1>
<p class="small">Garmin summary export and Strava summary / analysis export in a cleaner modular codebase.</p>
<div class="card">
<form id="uploadForm">
<label for="source">Source</label>
<select id="source" name="source">
  <option value="garmin">Garmin</option>
  <option value="strava">Strava</option>
</select>

<label for="file">Export ZIP</label>
<input type="file" id="file" name="file" accept=".zip" required>

<div class="row">
  <div>
    <label for="plan">Plan</label>
    <select id="plan" name="plan">
      <option value="free" selected>Free</option>
      <option value="pro" disabled>Pro (coming soon)</option>
    </select>
  </div>
  <div>
    <label for="mode">Mode</label>
    <select id="mode" name="mode">
      <option value="summary" selected>Summary</option>
      <option value="analysis">Analysis (Strava only)</option>
    </select>
  </div>
</div>

<div class="row">
  <div>
    <label for="sport">Sport (Strava analysis)</label>
    <select id="sport" name="sport">
      <option value="run" selected>Run</option>
      <option value="ride">Ride</option>
    </select>
  </div>
  <div>
    <label for="recent_count">Recent workouts</label>
    <select id="recent_count" name="recent_count">
      <option value="3">3</option>
      <option value="5" selected>5</option>
      <option value="10">10</option>
    </select>
  </div>
</div>

<div class="row">
  <div>
    <label for="start_date">Start date (Garmin)</label>
    <input type="date" id="start_date" name="start_date">
  </div>
  <div>
    <label for="end_date">End date (Garmin)</label>
    <input type="date" id="end_date" name="end_date">
  </div>
</div>

<label>Garmin data types</label>
<div class="small">
  <label><input type="checkbox" name="included_data" value="daily_summary" checked> daily_summary</label><br>
  <label><input type="checkbox" name="included_data" value="sleep" checked> sleep</label><br>
  <label><input type="checkbox" name="included_data" value="workouts" checked> workouts</label>
</div>

<button type="submit">Generate dataset</button>
</form>
<div id="message" class="small" style="margin-top:12px;"></div>
</div>
<div class="card">
<h2>Sample analysis payload shape</h2>
<pre>{json.dumps(build_sample_analysis_dataset(), indent=2)}</pre>
</div>
<script>
const form = document.getElementById('uploadForm');
const message = document.getElementById('message');
form.addEventListener('submit', async (e) => {{
  e.preventDefault();
  message.textContent = 'Processing...';
  const formData = new FormData(form);
  const res = await fetch('/upload', {{ method: 'POST', body: formData }});
  if (!res.ok) {{
    let text = 'Request failed';
    try {{
      const data = await res.json();
      text = data.detail || text;
    }} catch (_) {{}}
    message.textContent = text;
    return;
  }}
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'train2ai_dataset.json';
  a.click();
  URL.revokeObjectURL(url);
  message.textContent = 'Dataset downloaded.';
}});
</script>
</body>
</html>
"""


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/sample")
def sample() -> Response:
    data = build_sample_analysis_dataset()
    return Response(
        content=json.dumps(data, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=train2ai_sample.json"},
    )


def build_sample_analysis_dataset() -> dict:
    return {
        "source": "strava",
        "schema_version": "2.0",
        "plan": "free",
        "mode": "analysis",
        "sport": "run",
        "recent_count": 5,
        "target_stream_points": 200,
        "workouts": [
            {
                "date": "2026-03-01",
                "sport": "run",
                "distance_km": 10.2,
                "duration_min": 49.8,
                "avg_hr": 152,
                "max_hr": 178,
                "compressed_streams": {
                    "elapsed_sec": [0, 300, 600, 900],
                    "pace_min_per_km": [4.9, 5.0, 5.1, 5.3],
                    "heart_rate": [138.0, 149.0, 156.0, 162.0],
                    "cadence": [172.0, 173.0, 171.0, 169.0],
                },
            }
        ],
        "record_counts": {"workouts": 1},
    }


def validate_plan(plan: str) -> None:
    if plan not in {"free", "pro"}:
        raise HTTPException(status_code=400, detail="Invalid plan.")
    if plan == "pro":
        raise HTTPException(status_code=403, detail="Pro is coming soon. Please use Free for now.")


def enforce_plan_limit(plan: str, start, end) -> None:
    days = (end - start).days + 1
    if plan == "free" and days > FREE_MAX_DAYS:
        raise HTTPException(status_code=400, detail=f"Free plan supports up to {FREE_MAX_DAYS} days per export.")
    if plan == "pro" and days > PRO_MAX_DAYS:
        raise HTTPException(status_code=400, detail=f"Pro plan supports up to {PRO_MAX_DAYS} days per export.")


@app.post("/precheck")
async def precheck(
    request: Request,
    source: str = Form("garmin"),
    mode: str = Form("summary"),
    start_date: str | None = Form(None),
    end_date: str | None = Form(None),
    plan: str = Form("free"),
):
    ip = get_client_ip(request)
    validate_plan(plan)
    if source not in ALLOWED_SOURCES:
        raise HTTPException(status_code=400, detail="Invalid source.")
    if mode not in ALLOWED_MODES:
        raise HTTPException(status_code=400, detail="Invalid mode.")

    if source == "garmin":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Garmin requires start_date and end_date.")
        start = parse_input_date(start_date, "start_date")
        end = parse_input_date(end_date, "end_date")
        if start > end:
            raise HTTPException(status_code=400, detail="End date must be on or after start date.")
        enforce_plan_limit(plan, start, end)

    if source == "strava" and mode == "analysis":
        # No date range limit; recent_count keeps payload small.
        pass

    check_usage_limit_only(ip, plan)
    used = get_usage_count(ip, plan)
    return {"ok": True, "used_exports": used, "remaining_exports": max(FREE_TOTAL_LIMIT - used, 0)}


@app.post("/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    source: str = Form("garmin"),
    plan: str = Form("free"),
    mode: str = Form("summary"),
    start_date: str | None = Form(None),
    end_date: str | None = Form(None),
    included_data: list[str] | None = Form(None),
    sport: str = Form("run"),
    recent_count: int = Form(5),
):
    ip = get_client_ip(request)

    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload a ZIP file.")
    if source not in ALLOWED_SOURCES:
        raise HTTPException(status_code=400, detail="Invalid source.")
    if mode not in ALLOWED_MODES:
        raise HTTPException(status_code=400, detail="Invalid mode.")
    if sport not in ALLOWED_SPORTS:
        raise HTTPException(status_code=400, detail="sport must be run or ride.")
    if recent_count not in ANALYSIS_RECENT_CHOICES:
        raise HTTPException(status_code=400, detail="recent_count must be 3, 5, or 10.")

    validate_plan(plan)
    check_usage_limit_only(ip, plan)

    if source == "garmin":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Garmin requires start_date and end_date.")
        selected = garmin.normalize_included_data(included_data or [])
        if not selected:
            raise HTTPException(status_code=400, detail="Please select at least one Garmin data type.")

        start = parse_input_date(start_date, "start_date")
        end = parse_input_date(end_date, "end_date")
        if start > end:
            raise HTTPException(status_code=400, detail="End date must be on or after start date.")
        enforce_plan_limit(plan, start, end)

    if source == "strava" and mode == "analysis" and file.filename.lower().endswith(".zip") is False:
        raise HTTPException(status_code=400, detail="Upload a Strava export ZIP.")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, file.filename)
            with open(zip_path, "wb") as f:
                f.write(await file.read())

            try:
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(temp_dir)
            except zipfile.BadZipFile as exc:
                raise HTTPException(status_code=400, detail="Invalid ZIP file.") from exc

            if source == "garmin":
                found = garmin.scan_garmin_files(temp_dir)
                garmin.validate_detected_files(found, selected)
                daily_summary = garmin.collect_daily_summary(found["daily_summary"], start, end) if "daily_summary" in selected else []
                sleep = garmin.collect_sleep(found["sleep"], start, end) if "sleep" in selected else []
                workouts = garmin.collect_workouts(found["workouts"], start, end) if "workouts" in selected else []
                collected = {"daily_summary": daily_summary, "sleep": sleep, "workouts": workouts}
                garmin.validate_collected_results(collected, selected, start_date, end_date)
                result = garmin.build_output(plan, start_date, end_date, selected, daily_summary, sleep, workouts)
            else:
                found = strava.scan_strava_files(temp_dir)
                csv_path = found.get("activities_csv")
                fit_files = found.get("fit_files") or []

                if mode == "summary":
                    if not csv_path:
                        raise HTTPException(status_code=400, detail="activities.csv was not found in the Strava export ZIP.")
                    workouts = strava.collect_strava_summary(csv_path, sport=sport, recent_count=recent_count)
                    if not workouts:
                        raise HTTPException(status_code=400, detail=f"No {sport} activities found in activities.csv.")
                    result = strava.build_summary_output(plan, sport, recent_count, workouts)
                else:
                    if not fit_files:
                        raise HTTPException(status_code=400, detail="No FIT files were found in the Strava export ZIP.")
                    workouts = strava.build_analysis_workouts(fit_files, sport=sport, recent_count=recent_count)
                    result = strava.build_analysis_output(plan, sport, recent_count, workouts)

            increment_usage(ip, plan)
            return Response(
                content=json.dumps(result, indent=2, ensure_ascii=False, default=str),
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=train2ai_dataset.json"},
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}") from exc
