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

        # zipを保存
        with open(zip_path, "wb") as f:
            f.write(await file.read())

        # zip展開
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        # summarizedActivities.json を探す
        target_file = None

        for root, dirs, files in os.walk(temp_dir):
            for name in files:
                lower_name = name.lower()
                if "summarizedactivities" in lower_name and lower_name.endswith(".json"):
                    target_file = os.path.join(root, name)
                    break
            if target_file:
                break

        if not target_file:
            raise HTTPException(
                status_code=404,
                detail="summarizedActivities json file not found in zip"
            )

        # JSON読み込み
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Garmin JSON構造対応
        if isinstance(data, list):
            if (
                len(data) > 0
                and isinstance(data[0], dict)
                and "summarizedActivitiesExport" in data[0]
            ):
                activities = data[0].get("summarizedActivitiesExport", [])
            else:
                activities = data
        elif isinstance(data, dict):
            activities = data.get("summ
```
