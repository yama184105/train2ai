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
async def upload_garmin_daily_summary(
    file: UploadFile = File(...),
    start_date: str = Form(...),
    end_date: str = Form(...)
):
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Please upload a .zip file")

    try:
        # 日付チェック
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

        if start_dt > end_dt:
            raise HTTPException(status_code=400, detail="start_date must be before or equal to end_date")

        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, file.filename)

            # zip保存
            with open(zip_path, "wb") as f:
                f.write(await file.read())

            # zip展開
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # UDSFile を全部探す
            uds_files = []
            for root_dir, dirs, files in os.walk(temp_dir):
                for name in files:
                    lower_name = name.lower()
                    if lower_name.startswith("udsfile_") and lower_name.endswith(".json"):
                        uds_files.append(os.path.join(root_dir, name))

            if not uds_files:
                raise HTTPException(status_code=404, detail="UDSFile json files not found in zip")

            # 全 UDS データを集める
            all_days = []
            for uds_file in uds_files:
                with open(uds_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, list):
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
                            all_days.append(clean_item)

            # 日付でソート
            all_days.sort(key=lambda x: x["date"])

            return {
                "source": "garmin",
                "date_range": {
                    "start": start_date,
                    "end": end_date
                },
                "included_data": ["daily_summary"],
                "daily_summary": all_days
            }

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip file")
    except ValueError:
        raise HTTPException(status_code=400, detail="Date format must be YYYY-MM-DD")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
