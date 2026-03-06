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
<title>train2ai</title>
<style>

body{
font-family:Arial;
max-width:1100px;
margin:40px auto;
padding:20px;
background:#f7f8fb;
}

h1{
font-size:48px;
margin-bottom:10px;
}

.subtitle{
color:#555;
font-size:18px;
margin-bottom:30px;
}

.container{
display:grid;
grid-template-columns:1fr 420px;
gap:40px;
}

.card{
background:white;
border-radius:16px;
padding:24px;
box-shadow:0 10px 40px rgba(0,0,0,0.08);
}

label{
font-weight:bold;
display:block;
margin-top:14px;
}

input,select,button{
width:100%;
padding:10px;
margin-top:6px;
border-radius:8px;
border:1px solid #ccc;
}

button{
background:black;
color:white;
border:none;
margin-top:18px;
cursor:pointer;
}

button:hover{
opacity:0.9;
}

.message{
margin-top:10px;
font-size:14px;
}

.example{
background:#111;
color:#ddd;
padding:20px;
border-radius:12px;
font-size:13px;
margin-top:20px;
}

.section{
margin-top:60px;
}

.step{
margin-bottom:12px;
}

</style>
</head>

<body>

<h1>train2ai</h1>
<div class="subtitle">
Turn Garmin exports into AI-ready datasets
</div>

<div class="container">

<div>

<p>
Upload your Garmin export ZIP and get clean JSON for ChatGPT, Claude, or Gemini.
train2ai does not analyze your data — it prepares it for AI.
</p>

<div class="example">
<pre>
{
 "source": "garmin",
 "date_range": {
   "start": "2026-02-06",
   "end": "2026-02-12"
 },
 "daily_summary": [...],
 "sleep": [...],
 "workouts": [...]
}
</pre>
</div>

</div>

<div class="card">

<h2>Generate dataset</h2>

<form id="uploadForm">

<label>Garmin export ZIP</label>
<input type="file" name="file" accept=".zip" required>

<label>Start date</label>
<input type="date" name="start_date" required>

<label>End date</label>
<input type="date" name="end_date" required>

<label>Plan</label>
<select name="plan">
<option value="free">Free</option>
<option value="pro">Pro</option>
</select>

<button type="submit">Generate dataset</button>

</form>

<div id="message" class="message"></div>

<p style="margin-top:14px;font-size:13px;color:#666">
Free: 7 days per export · 3 exports per month
</p>

</div>

</div>

<div class="section">

<h2>How it works</h2>

<div class="step">1. Export your data from Garmin Connect</div>
<div class="step">2. Upload the ZIP file here</div>
<div class="step">3. Download an AI-ready dataset JSON</div>

</div>

<script>

const form=document.getElementById("uploadForm");
const message=document.getElementById("message");

form.addEventListener("submit",async(e)=>{

e.preventDefault();

message.innerText="Generating dataset...";
message.style.color="#555";

const formData=new FormData(form);

try{

const res=await fetch("/upload",{
method:"POST",
body:formData
});

if(!res.ok){

const err=await res.json();

message.innerText=err.detail;
message.style.color="red";
return;

}

const blob=await res.blob();
const url=window.URL.createObjectURL(blob);

const a=document.createElement("a");
a.href=url;
a.download="train2ai_dataset.json";
document.body.appendChild(a);
a.click();
a.remove();

message.innerText="Dataset downloaded";
message.style.color="green";

}catch{

message.innerText="Network error";
message.style.color="red";

}

});

</script>

</body>
</html>
"""


def parse_input_date(date_str, field):

    try:
        return datetime.strptime(date_str,"%Y-%m-%d").date()
    except:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field}"
        )


def parse_garmin_datetime(dt):

    if not dt:
        return None

    try:
        return datetime.fromisoformat(dt).isoformat()
    except:
        return None


def enforce_plan_limit(plan,start,end):

    days=(end-start).days+1

    if plan=="free" and days>7:
        raise HTTPException(
            status_code=400,
            detail="Free plan supports up to 7 days per export."
        )

    if plan=="pro" and days>365:
        raise HTTPException(
            status_code=400,
            detail="Pro plan supports up to 365 days."
        )


def check_usage_limit(ip,plan):

    if plan!="free":
        return

    now=datetime.utcnow()
    month=now.strftime("%Y-%m")

    if Path(USAGE_FILE).exists():
        with open(USAGE_FILE) as f:
            data=json.load(f)
    else:
        data={}

    if month not in data:
        data[month]={}

    count=data[month].get(ip,0)

    if count>=FREE_MONTHLY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Free plan monthly limit reached (3 exports)."
        )

    data[month][ip]=count+1

    with open(USAGE_FILE,"w") as f:
        json.dump(data,f)


@app.post("/upload")
async def upload(
request:Request,
file:UploadFile=File(...),
start_date:str=Form(...),
end_date:str=Form(...),
plan:str=Form("free")
):

    ip=request.client.host

    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400,detail="Upload a Garmin export zip")

    start=parse_input_date(start_date,"start_date")
    end=parse_input_date(end_date,"end_date")

    if start>end:
        raise HTTPException(status_code=400,detail="Invalid date range")

    enforce_plan_limit(plan,start,end)
    check_usage_limit(ip,plan)

    try:

        with tempfile.TemporaryDirectory() as temp:

            zip_path=os.path.join(temp,file.filename)

            with open(zip_path,"wb") as f:
                f.write(await file.read())

            with zipfile.ZipFile(zip_path) as zip_ref:
                zip_ref.extractall(temp)

            uds=[]
            sleep=[]
            workouts=[]

            for root,dirs,files in os.walk(temp):

                for name in files:

                    lower=name.lower()

                    path=os.path.join(root,name)

                    if lower.startswith("udsfile_") and lower.endswith(".json"):
                        uds.append(path)

                    if lower.endswith("_sleepdata.json"):
                        sleep.append(path)

                    if "summarizedactivities" in lower:
                        workouts.append(path)

            daily=[]

            for file_path in uds:

                data=json.load(open(file_path))

                if not isinstance(data,list):
                    continue

                for item in data:

                    date=item.get("calendarDate")

                    if not date:
                        continue

                    d=datetime.strptime(date,"%Y-%m-%d").date()

                    if start<=d<=end:

                        dist=item.get("totalDistanceMeters")

                        daily.append({
                        "date":date,
                        "steps":item.get("totalSteps"),
                        "distance_km":round(dist/1000,2) if dist else None,
                        "resting_hr":item.get("restingHeartRate")
                        })

            sleep_out=[]

            for file_path in sleep:

                data=json.load(open(file_path))

                if not isinstance(data,list):
                    continue

                for item in data:

                    date=item.get("calendarDate")

                    if not date:
                        continue

                    d=datetime.strptime(date,"%Y-%m-%d").date()

                    if start<=d<=end:

                        sleep_out.append({
                        "date":date,
                        "sleep_start":parse_garmin_datetime(item.get("sleepStartTimestampGMT")),
                        "sleep_end":parse_garmin_datetime(item.get("sleepEndTimestampGMT"))
                        })

            workouts_out=[]

            for file_path in workouts:

                data=json.load(open(file_path))

                if isinstance(data,list):

                    if len(data)>0 and "summarizedActivitiesExport" in data[0]:
                        activities=data[0]["summarizedActivitiesExport"]
                    else:
                        activities=data

                else:
                    activities=[]

                for act in activities:

                    start_time=act.get("startTimeLocal")

                    if not isinstance(start_time,(int,float)):
                        continue

                    date=datetime.fromtimestamp(start_time/1000,tz=timezone.utc).date()

                    if start<=date<=end:

                        dist=act.get("distance")
                        dur=act.get("duration")

                        workouts_out.append({

                        "date":date.isoformat(),
                        "sport":act.get("sportType"),
                        "distance_km":round(dist/100000,2) if dist else None,
                        "duration_min":round(dur/60000,1) if dur else None

                        })

            result={
            "source":"garmin",
            "plan":plan,
            "date_range":{"start":start_date,"end":end_date},
            "daily_summary":daily,
            "sleep":sleep_out,
            "workouts":workouts_out
            }

            json_str=json.dumps(result,indent=2)

            return Response(
            content=json_str,
            media_type="application/json",
            headers={"Content-Disposition":"attachment; filename=train2ai_dataset.json"}
            )

    except Exception as e:

        raise HTTPException(status_code=500,detail=str(e))
