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
    ALLOWED_SPORTS,
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

ANALYSIS_RECENT_CHOICES = {1, 3, 5, 10}
STRAVA_SUMMARY_SPORTS = {"all", "run", "ride"}
ANALYSIS_SCOPES = {"recent", "date"}


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
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    included_data: Optional[list[str]] = Form(None),
    sport: str = Form("run"),
    recent_count: int = Form(5),
    analysis_scope: str = Form("recent"),
    activity_date: Optional[str] = Form(None),
):

    ip = get_client_ip(request)

    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload a ZIP file.")

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

            if source == "garmin":

                if not start_date or not end_date:
                    raise HTTPException(status_code=400, detail="Garmin requires start_date and end_date.")

                selected = garmin.normalize_included_data(included_data or [])

                start = parse_input_date(start_date, "start_date")
                end = parse_input_date(end_date, "end_date")

                found = garmin.scan_garmin_files(temp_dir)

                daily_summary = (
                    garmin.collect_daily_summary(found["daily_summary"], start, end)
                    if "daily_summary" in selected
                    else []
                )

                sleep = (
                    garmin.collect_sleep(found["sleep"], start, end)
                    if "sleep" in selected
                    else []
                )

                workouts = (
                    garmin.collect_workouts(found["workouts"], start, end)
                    if "workouts" in selected
                    else []
                )

                result = garmin.build_output(
                    plan,
                    start_date,
                    end_date,
                    selected,
                    daily_summary,
                    sleep,
                    workouts,
                )

            else:

                found = strava.scan_strava_files(temp_dir)

                csv_path = found.get("activities_csv")
                fit_files = found.get("fit_files") or []

                if mode == "summary":

                    if not csv_path:
                        raise HTTPException(
                            status_code=400,
                            detail="activities.csv not found in Strava export.",
                        )

                    workouts = strava.collect_strava_summary(
                        csv_path,
                        sport=sport,
                        start_date=start_date,
                        end_date=end_date,
                    )

                    result = strava.build_summary_output(
                        plan=plan,
                        sport=sport,
                        start_date=start_date,
                        end_date=end_date,
                        workouts=workouts,
                    )

                else:

                    if not fit_files:
                        raise HTTPException(
                            status_code=400,
                            detail="No FIT files found in Strava export.",
                        )

                    if analysis_scope == "recent":

                        if recent_count not in ANALYSIS_RECENT_CHOICES:
                            raise HTTPException(status_code=400, detail="Invalid recent_count")

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

                        if not csv_path:
                            raise HTTPException(
                                status_code=400,
                                detail="activities.csv required for date analysis.",
                            )

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
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}")
