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

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, file.filename)

            # アップロードされたzipを保存
            with open(zip_path, "wb") as f:
                f.write(await file.read())

            # zip展開
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # summarizedActivities.json を探す
            target_file = None
            for root, dirs, files in os.walk(temp_dir):
                for name in files:
                    if name == "summarizedActivities.json":
                        target_file = os.path.join(root, name)
                        break
                if target_file:
                    break

            if not target_file:
                raise HTTPException(status_code=404, detail="summarizedActivities.json not found in zip")

            # JSONを読む
            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            activities = data[0].get("summarizedActivitiesExport", [])

            runs = []
            rides = []
            swims = []

            for act in activities:
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
