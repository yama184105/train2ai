from __future__ import annotations

import json
import os
import tempfile
import zipfile
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response

from app.config import ALLOWED_MODES, ALLOWED_SOURCES
from app.providers import garmin, strava
from app.utils.dates import parse_input_date
from app.utils.usage import (
    check_usage_limit_only,
    get_client_ip,
    increment_usage,
)

app = FastAPI(title="train2ai")

ANALYSIS_RECENT_CHOICES = {1, 3, 5, 10}
STRAVA_SUMMARY_SPORTS = {"all", "run", "ride"}
STRAVA_ANALYSIS_SPORTS = {"run", "ride"}
ANALYSIS_SCOPES = {"recent", "date"}


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>train2ai</title>
<style>
body {
    font-family: Arial, sans-serif;
    max-width: 980px;
    margin: 40px auto;
    padding: 0 16px;
    color: #111827;
    background: #f9fafb;
}
.card {
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 20px;
}
h1 {
    font-size: 34px;
    margin-bottom: 10px;
}
p.lead {
    color: #6b7280;
    margin-bottom: 24px;
}
label {
    display: block;
    font-weight: 700;
    margin-top: 16px;
    margin-bottom: 6px;
}
input, select, button {
    width: 100%;
    padding: 12px;
    border-radius: 10px;
    border: 1px solid #d1d5db;
    box-sizing: border-box;
    font-size: 16px;
}
input[type="checkbox"] {
    width: auto;
    margin-right: 8px;
}
button {
    background: #111827;
    color: white;
    border: none;
    font-weight: 700;
    margin-top: 24px;
    cursor: pointer;
}
button:disabled {
    opacity: 0.65;
    cursor: not-allowed;
}
.row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}
.checkbox-group {
    display: grid;
    gap: 10px;
    margin-top: 8px;
}
.small {
    color: #6b7280;
    font-size: 14px;
    line-height: 1.6;
}
.hidden {
    display: none;
}
@media (max-width: 700px) {
    .row {
        grid-template-columns: 1fr;
    }
}
</style>
</head>
<body>

<h1>train2ai</h1>
<p class="lead">Garmin summary export and Strava summary / analysis export in a cleaner modular codebase.</p>

<div class="card">
<form id="uploadForm">
    <label for="source">Source</label>
    <select id="source" name="source">
        <option value="garmin" selected>Garmin</option>
        <option value="strava">Strava</option>
    </select>

    <label for="file">Export ZIP</label>
    <input type="file" id="file" name="file" accept=".zip" required>

    <div class="row">
        <div>
            <label for="plan">Plan</label>
            <select id="plan" name="plan">
                <option value="free" selected>Free</option>
                <option value="pro">Pro</option>
            </select>
        </div>

        <div id="strava-mode-wrap" class="hidden">
            <label for="mode">Strava output</label>
            <select id="mode" name="mode">
                <option value="summary" selected>Summary</option>
                <option value="analysis">Analysis</option>
            </select>
        </div>
    </div>

    <div id="garmin-fields">
        <div class="row">
            <div>
                <label for="garmin_start_date">Start date (Garmin)</label>
                <input type="date" id="garmin_start_date" name="garmin_start_date">
            </div>
            <div>
                <label for="garmin_end_date">End date (Garmin)</label>
                <input type="date" id="garmin_end_date" name="garmin_end_date">
            </div>
        </div>

        <label>Garmin data types</label>
        <div class="checkbox-group">
            <label><input type="checkbox" name="included_data" value="daily_summary" checked> daily_summary</label>
            <label><input type="checkbox" name="included_data" value="sleep" checked> sleep</label>
            <label><input type="checkbox" name="included_data" value="workouts" checked> workouts</label>
        </div>
    </div>

    <div id="strava-fields" class="hidden">
        <div id="strava-summary-fields">
            <div class="row">
                <div>
                    <label for="summary_sport">Sport (Strava summary)</label>
                    <select id="summary_sport" name="summary_sport">
                        <option value="all" selected>All</option>
                        <option value="run">Run</option>
                        <option value="ride">Ride</option>
                    </select>
                </div>
                <div></div>
            </div>

            <div class="row">
                <div>
                    <label for="summary_start_date">Start date (Strava summary)</label>
                    <input type="date" id="summary_start_date" name="summary_start_date">
                </div>
                <div>
                    <label for="summary_end_date">End date (Strava summary)</label>
                    <input type="date" id="summary_end_date" name="summary_end_date">
                </div>
            </div>
        </div>

        <div id="strava-analysis-fields" class="hidden">
            <div class="row">
                <div>
                    <label for="analysis_sport">Sport (Strava analysis)</label>
                    <select id="analysis_sport" name="analysis_sport">
                        <option value="run" selected>Run</option>
                        <option value="ride">Ride</option>
                    </select>
                </div>
                <div>
                    <label for="analysis_scope">Analysis scope</label>
                    <select id="analysis_scope" name="analysis_scope">
                        <option value="recent" selected>Recent workouts</option>
                        <option value="date">Specific date</option>
                    </select>
                </div>
            </div>

            <div id="analysis-recent-wrap" class="row">
                <div>
                    <label for="analysis_recent_count">Recent workouts</label>
                    <select id="analysis_recent_count" name="analysis_recent_count">
                        <option value="1">1</option>
                        <option value="3">3</option>
                        <option value="5" selected>5</option>
                        <option value="10">10</option>
                    </select>
                </div>
                <div></div>
            </div>

            <div id="analysis-date-wrap" class="row hidden">
                <div>
                    <label for="analysis_activity_date">Activity date</label>
                    <input type="date" id="analysis_activity_date" name="analysis_activity_date">
                </div>
                <div></div>
            </div>

            <p class="small" style="margin-top:12px;">
                Analysis mode uses FIT files from the Strava export and compresses each activity stream to around 200 points.
            </p>
        </div>
    </div>

    <button type="submit">Generate dataset</button>
</form>

<div id="message" class="small" style="margin-top:14px;"></div>
</div>

<script>
const form = document.getElementById("uploadForm");
const message = document.getElementById("message");

const sourceSelect = document.getElementById("source");
const modeSelect = document.getElementById("mode");
const planSelect = document.getElementById("plan");

const garminFields = document.getElementById("garmin-fields");
const stravaModeWrap = document.getElementById("strava-mode-wrap");
const stravaFields = document.getElementById("strava-fields");
const stravaSummaryFields = document.getElementById("strava-summary-fields");
const stravaAnalysisFields = document.getElementById("strava-analysis-fields");

const analysisScope = document.getElementById("analysis_scope");
const analysisRecentWrap = document.getElementById("analysis-recent-wrap");
const analysisDateWrap = document.getElementById("analysis-date-wrap");

function show(el) {
    el.classList.remove("hidden");
}

function hide(el) {
    el.classList.add("hidden");
}

function syncAnalysisScopeFields() {
    if (analysisScope.value === "recent") {
        show(analysisRecentWrap);
        hide(analysisDateWrap);
    } else {
        hide(analysisRecentWrap);
        show(analysisDateWrap);
    }
}

function toggleFields() {
    const source = sourceSelect.value;

    if (source === "garmin") {
        show(garminFields);
        hide(stravaModeWrap);
        hide(stravaFields);
    } else {
        hide(garminFields);
        show(stravaModeWrap);
        show(stravaFields);

        if (modeSelect.value === "summary") {
            show(stravaSummaryFields);
            hide(stravaAnalysisFields);
        } else {
            hide(stravaSummaryFields);
            show(stravaAnalysisFields);
            syncAnalysisScopeFields();
        }
    }
}

sourceSelect.addEventListener("change", toggleFields);
modeSelect.addEventListener("change", toggleFields);
analysisScope.addEventListener("change", syncAnalysisScopeFields);

toggleFields();

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    message.textContent = "Processing...";

    const formData = new FormData(form);

    try {
        const res = await fetch("/upload", {
            method: "POST",
            body: formData
        });

        if (!res.ok) {
            let text = "Request failed";
            try {
                const data = await res.json();
                text = data.detail || text;
            } catch (_) {}
            message.textContent = text;
            return;
        }

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "train2ai_dataset.json";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);

        message.textContent = "Dataset downloaded.";
    } catch (_) {
        message.textContent = "Network error. Please try again.";
    }
});
</script>

</body>
</html>
"""


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    source: str = Form("garmin"),
    plan: str = Form("free"),
    mode: str = Form("summary"),
    garmin_start_date: Optional[str] = Form(None),
    garmin_end_date: Optional[str] = Form(None),
    included_data: Optional[list[str]] = Form(None),
    summary_sport: Optional[str] = Form(None),
    summary_start_date: Optional[str] = Form(None),
    summary_end_date: Optional[str] = Form(None),
    analysis_sport: Optional[str] = Form(None),
    analysis_scope: Optional[str] = Form("recent"),
    analysis_recent_count: Optional[int] = Form(5),
    analysis_activity_date: Optional[str] = Form(None),
):
    ip = get_client_ip(request)

    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload ZIP file.")

    if source not in ALLOWED_SOURCES:
        raise HTTPException(status_code=400, detail="Invalid source.")

    if mode not in ALLOWED_MODES:
        raise HTTPException(status_code=400, detail="Invalid mode.")

    if plan == "pro":
        raise HTTPException(status_code=403, detail="Pro is coming soon. Please use Free for now.")

    check_usage_limit_only(ip, plan)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, file.filename)

            with open(zip_path, "wb") as f:
                f.write(await file.read())

            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(temp_dir)

            if source == "garmin":
                if not garmin_start_date or not garmin_end_date:
                    raise HTTPException(status_code=400, detail="Garmin requires start date and end date.")

                selected = garmin.normalize_included_data(included_data or [])
                if not selected:
                    raise HTTPException(status_code=400, detail="Select at least one Garmin data type.")

                start = parse_input_date(garmin_start_date, "garmin_start_date")
                end = parse_input_date(garmin_end_date, "garmin_end_date")

                found = garmin.scan_garmin_files(temp_dir)
                garmin.validate_detected_files(found, selected)

                daily_summary = (
                    garmin.collect_daily_summary(found["daily_summary"], start, end)
                    if "daily_summary" in selected else []
                )
                sleep = (
                    garmin.collect_sleep(found["sleep"], start, end)
                    if "sleep" in selected else []
                )
                workouts = (
                    garmin.collect_workouts(found["workouts"], start, end)
                    if "workouts" in selected else []
                )

                collected = {
                    "daily_summary": daily_summary,
                    "sleep": sleep,
                    "workouts": workouts,
                }
                garmin.validate_collected_results(collected, selected, garmin_start_date, garmin_end_date)

                result = garmin.build_output(
                    plan=plan,
                    start_date=garmin_start_date,
                    end_date=garmin_end_date,
                    selected=selected,
                    daily_summary=daily_summary,
                    sleep=sleep,
                    workouts=workouts,
                )

            else:
                found = strava.scan_strava_files(temp_dir)
                csv_path = found.get("activities_csv")
                fit_files = found.get("fit_files") or []

                if mode == "summary":
                    if not csv_path:
                        raise HTTPException(status_code=400, detail="activities.csv not found in Strava export.")

                    if summary_sport not in STRAVA_SUMMARY_SPORTS:
                        raise HTTPException(status_code=400, detail="Invalid Strava summary sport.")

                    if not summary_start_date or not summary_end_date:
                        raise HTTPException(status_code=400, detail="Strava summary requires start date and end date.")

                    workouts = strava.collect_strava_summary(
                        csv_path=csv_path,
                        sport=summary_sport,
                        start_date=summary_start_date,
                        end_date=summary_end_date,
                    )

                    result = strava.build_summary_output(
                        plan=plan,
                        sport=summary_sport,
                        start_date=summary_start_date,
                        end_date=summary_end_date,
                        workouts=workouts,
                    )

                else:
                    if analysis_sport not in STRAVA_ANALYSIS_SPORTS:
                        raise HTTPException(status_code=400, detail="Invalid Strava analysis sport.")

                    if not fit_files:
                        raise HTTPException(status_code=400, detail="No FIT files found in Strava export.")

                    if analysis_scope not in ANALYSIS_SCOPES:
                        raise HTTPException(status_code=400, detail="Invalid analysis scope.")

                    if analysis_scope == "recent":
                        if analysis_recent_count not in ANALYSIS_RECENT_CHOICES:
                            raise HTTPException(status_code=400, detail="Recent workouts must be 1, 3, 5, or 10.")

                        workouts = strava.build_analysis_workouts(
                            fit_files=fit_files,
                            sport=analysis_sport,
                            recent_count=analysis_recent_count,
                        )

                        result = strava.build_analysis_output(
                            plan=plan,
                            sport=analysis_sport,
                            recent_count=analysis_recent_count,
                            workouts=workouts,
                            analysis_scope="recent",
                        )

                    else:
                        if not csv_path:
                            raise HTTPException(status_code=400, detail="activities.csv required for date analysis.")

                        if not analysis_activity_date:
                            raise HTTPException(status_code=400, detail="Select an activity date.")

                        workouts = strava.build_analysis_workouts_for_date(
                            csv_path=csv_path,
                            fit_files=fit_files,
                            sport=analysis_sport,
                            activity_date=analysis_activity_date,
                        )

                        result = strava.build_analysis_output(
                            plan=plan,
                            sport=analysis_sport,
                            recent_count=None,
                            workouts=workouts,
                            analysis_scope="date",
                            activity_date=analysis_activity_date,
                        )

            increment_usage(ip, plan)

            return Response(
                content=json.dumps(result, indent=2, ensure_ascii=False),
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=train2ai_dataset.json"},
            )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}")
