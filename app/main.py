from __future__ import annotations

import json
import os
import tempfile
import zipfile
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response

from app.config import (
    ALLOWED_MODES,
    ALLOWED_SOURCES,
)
from app.providers import garmin, strava
from app.utils.dates import parse_input_date
from app.utils.usage import (
    check_usage_limit_only,
    get_client_ip,
    increment_usage,
)

app = FastAPI(title="train2ai")


# -------------------------------
# UI
# -------------------------------

@app.get("/", response_class=HTMLResponse)
def home():

    return """
<!DOCTYPE html>
<html>
<head>

<meta charset="utf-8">
<title>train2ai</title>

<style>

body{
font-family: Arial;
max-width:900px;
margin:auto;
padding:40px;
}

h1{
font-size:34px;
}

label{
display:block;
margin-top:20px;
}

select,input{
padding:8px;
font-size:15px;
margin-top:5px;
}

button{
margin-top:30px;
padding:14px 22px;
font-size:18px;
}

</style>

</head>

<body>

<h1>train2ai</h1>

<p>
Garmin summary export and Strava summary / analysis export.
</p>

<form action="/upload" method="post" enctype="multipart/form-data">

<label>Source</label>

<select name="source">
<option value="garmin">Garmin</option>
<option value="strava">Strava</option>
</select>

<label>Export ZIP</label>

<input type="file" name="file" required>

<label>Plan</label>

<select name="plan">
<option value="free">Free</option>
<option value="pro">Pro</option>
</select>

<label>Mode</label>

<select name="mode">
<option value="summary">Summary</option>
<option value="analysis">Analysis</option>
</select>

<label>Sport</label>

<select name="sport">
<option value="run">Run</option>
<option value="ride">Ride</option>
</select>

<label>Recent workouts</label>

<select name="recent_count">
<option value="1">1</option>
<option value="3">3</option>
<option value="5" selected>5</option>
<option value="10">10</option>
</select>

<label>Analysis scope</label>

<select name="analysis_scope">
<option value="recent">Recent</option>
<option value="date">Specific date</option>
</select>

<label>Activity date</label>

<input type="date" name="activity_date">

<br>

<button type="submit">Generate dataset</button>

</form>

</body>
</html>
"""


# -------------------------------
# Health check
# -------------------------------

@app.get("/health")
def health():

    return {"status": "ok"}


# -------------------------------
# Upload endpoint
# -------------------------------

@app.post("/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    source: str = Form("garmin"),
    plan: str = Form("free"),
    mode: str = Form("summary"),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    sport: str = Form("run"),
    recent_count: int = Form(5),
    analysis_scope: str = Form("recent"),
    activity_date: Optional[str] = Form(None),
):

    ip = get_client_ip(request)

    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload ZIP file.")

    if source not in ALLOWED_SOURCES:
        raise HTTPException(status_code=400, detail="Invalid source.")

    if mode not in ALLOWED_MODES:
        raise HTTPException(status_code=400, detail="Invalid mode.")

    check_usage_limit_only(ip, plan)

    try:

        with tempfile.TemporaryDirectory() as temp_dir:

            zip_path = os.path.join(temp_dir, file.filename)

            with open(zip_path, "wb") as f:
                f.write(await file.read())

            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(temp_dir)

            # -------------------------
            # Garmin
            # -------------------------

            if source == "garmin":

                start = parse_input_date(start_date, "start_date")
                end = parse_input_date(end_date, "end_date")

                found = garmin.scan_garmin_files(temp_dir)

                daily_summary = garmin.collect_daily_summary(
                    found["daily_summary"], start, end
                )

                sleep = garmin.collect_sleep(
                    found["sleep"], start, end
                )

                workouts = garmin.collect_workouts(
                    found["workouts"], start, end
                )

                result = garmin.build_output(
                    plan,
                    start_date,
                    end_date,
                    ["daily_summary", "sleep", "workouts"],
                    daily_summary,
                    sleep,
                    workouts,
                )

            # -------------------------
            # Strava
            # -------------------------

            else:

                found = strava.scan_strava_files(temp_dir)

                csv_path = found.get("activities_csv")
                fit_files = found.get("fit_files") or []

                if mode == "summary":

                    workouts = strava.collect_strava_summary(
                        csv_path,
                        sport=sport,
                        start_date=start_date,
                        end_date=end_date,
                    )

                    result = strava.build_summary_output(
                        plan,
                        sport,
                        start_date,
                        end_date,
                        workouts,
                    )

                else:

                    if analysis_scope == "recent":

                        workouts = strava.build_analysis_workouts(
                            fit_files,
                            sport=sport,
                            recent_count=recent_count,
                        )

                        result = strava.build_analysis_output(
                            plan=plan,
                            sport=sport,
                            recent_count=recent_count,
                            workouts=workouts,
                            analysis_scope="recent",
                        )

                    else:

                        workouts = strava.build_analysis_workouts_for_date(
                            csv_path=csv_path,
                            fit_files=fit_files,
                            sport=sport,
                            activity_date=activity_date,
                        )

                        result = strava.build_analysis_output(
                            plan=plan,
                            sport=sport,
                            recent_count=None,
                            workouts=workouts,
                            analysis_scope="date",
                            activity_date=activity_date,
                        )

            increment_usage(ip, plan)

            return Response(
                content=json.dumps(result, indent=2, ensure_ascii=False),
                media_type="application/json",
                headers={
                    "Content-Disposition": "attachment; filename=train2ai_dataset.json"
                },
            )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {exc}",
        )
