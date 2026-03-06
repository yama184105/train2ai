from fastapi import FastAPI, UploadFile, File, HTTPException
import zipfile
import tempfile
import os
import json

app = FastAPI()

@app.get("/")
def root():
return {"message": "train2ai API running"}

@app.post("/upload")
async def upload_garmin_zip(file: UploadFile = File(...)):
if not file.filename.endswith(".zip"):
raise HTTPException(status_code=400, detail="Please upload a .zip file")

```
try:
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, file.filename)

        # zip保存
        with open(zip_path, "wb") as f:
            f.write(await file.read())

        # zip展開
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        # summarizedActivities json を探す
        target_file = None

        for root_dir, dirs, files in os.walk(temp_dir):
            for name in files:
                lower_name = name.lower()
                if "summarizedactivities" in lower_name and lower_name.endswith(".json"):
                    target_file = os.path.join(root_dir, name)
                    break
            if target_file:
                break

        if not target_file:
            raise HTTPException(status_code=404, detail="summarizedActivities json not found")

        # JSON読み込み
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Garmin JSON構造対応
        if isinstance(data, list):
            if len(data) > 0 and isinstance(data[0], dict) and "summarizedActivitiesExport" in data[0]:
                activities = data[0].get("summarizedActivitiesExport", [])
            else:
                activities = data
        elif isinstance(data, dict):
            activities = data.get("summarizedActivitiesExport", [])
        else:
            activities = []

        runs = []
        rides = []
        swims = []

        for act in activities:
            if not isinstance(act, dict):
                continue

            item = {
                "activityId": act.get("activityId"),
                "sportType": act.get("sportType"),
                "startTimeLocal": act.get("startTimeLocal"),
                "distance": act.get("distance"),
                "duration": act.get("duration"),
                "avgSpeed": act.get("avgSpeed"),
                "avgHr": act.get("avgHr"),
                "maxHr": act.get("maxHr"),
                "calories": act.get("calories"),
            }

            sport = str(act.get("sportType", "")).lower()

            if "run" in sport:
                runs.append(item)
            elif "cycl" in sport or "bike" in sport:
                rides.append(item)
            elif "swim" in sport:
                swims.append(item)

        return {
            "found_file": os.path.basename(target_file),
            "summary": {
                "total_activities": len(activities),
                "runs": len(runs),
                "rides": len(rides),
                "swims": len(swims),
            },
            "runs": runs[:5],
            "rides": rides[:5],
            "swims": swims[:5],
        }

except zipfile.BadZipFile:
    raise HTTPException(status_code=400, detail="Invalid zip file")
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```
