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
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>train2ai</title>

<style>

body{
font-family:Arial, sans-serif;
background:#f4f6fb;
margin:0;
}

.page{
max-width:1100px;
margin:auto;
padding:40px 24px 80px;
}

.hero{
display:grid;
grid-template-columns:1.2fr 0.8fr;
gap:40px;
}

h1{
font-size:60px;
margin:0 0 10px;
}

.subtitle{
color:#555;
font-size:18px;
margin-bottom:30px;
}

.code-box{
background:#05070b;
color:#eee;
border-radius:16px;
padding:20px;
margin-top:20px;
}

.form-card{
background:white;
padding:26px;
border-radius:20px;
box-shadow:0 12px 30px rgba(0,0,0,0.08);
}

label{
font-weight:bold;
display:block;
margin-top:16px;
}

input,select,button{
width:100%;
padding:12px;
margin-top:6px;
border-radius:10px;
border:1px solid #ccc;
}

button{
background:black;
color:white;
border:none;
margin-top:18px;
cursor:pointer;
font-weight:bold;
}

button:disabled{
opacity:0.6;
cursor:not-allowed;
}

.row{
display:grid;
grid-template-columns:1fr 1fr;
gap:14px;
}

.message{
margin-top:12px;
font-weight:bold;
min-height:22px;
}

.section{
margin-top:70px;
}

.steps{
display:grid;
grid-template-columns:repeat(3,1fr);
gap:20px;
}

.step{
background:white;
padding:20px;
border-radius:16px;
box-shadow:0 8px 20px rgba(0,0,0,0.05);
}

.step-num{
color:#2563eb;
font-weight:bold;
margin-bottom:6px;
}

@media (max-width:900px){

.hero{
grid-template-columns:1fr;
}

.steps{
grid-template-columns:1fr;
}

}

</style>
</head>

<body>

<div class="page">

<div class="hero">

<div>

<h1>train2ai</h1>

<div class="subtitle">
Turn Garmin exports into AI-ready datasets
</div>

<p>
Upload your Garmin export ZIP and get clean JSON for ChatGPT, Claude, or Gemini.
</p>

<div class="code-box">
<pre>{
"source":"garmin",
"daily_summary":[...],
"sleep":[...],
"workouts":[...]
}</pre>
</div>

</div>

<div class="form-card">

<h2>Generate dataset</h2>

<form id="uploadForm">

<label>Garmin export ZIP</label>
<input type="file" name="file" accept=".zip" required>

<div class="row">

<div>
<label>Start date</label>
<input type="date" name="start_date" required>
</div>

<div>
<label>End date</label>
<input type="date" name="end_date" required>
</div>

</div>

<label>Plan</label>

<select name="plan">
<option value="free">Free</option>
<option value="pro">Pro</option>
</select>

<button type="submit">Generate dataset</button>

</form>

<div id="message" class="message"></div>

<p style="color:#666;margin-top:12px;font-size:14px">
Garmin export ZIP files can be large (50–200MB). Processing may take up to about 1 minute.
</p>

</div>

</div>

<div class="section">

<h2>How it works</h2>

<div class="steps">

<div class="step">
<div class="step-num">1</div>
<h3>Export from Garmin Connect</h3>
<p>Download your Garmin data export ZIP.</p>
</div>

<div class="step">
<div class="step-num">2</div>
<h3>Upload ZIP</h3>
<p>Upload the ZIP file and choose your date range.</p>
</div>

<div class="step">
<div class="step-num">3</div>
<h3>Download JSON</h3>
<p>Use the dataset with ChatGPT or other AI tools.</p>
</div>

</div>

</div>


<div class="section">

<h2>How to export your Garmin data</h2>

<div class="steps">

<div class="step">
<div class="step-num">1</div>
<h3>Open Garmin Connect</h3>
<p>Go to Garmin Connect and open account settings.</p>
</div>

<div class="step">
<div class="step-num">2</div>
<h3>Request data export</h3>
<p>Navigate to Data Management and request a full export.</p>
</div>

<div class="step">
<div class="step-num">3</div>
<h3>Download ZIP</h3>
<p>Garmin sends a download link. Upload the ZIP here.</p>
</div>

</div>

</div>

</div>

<script>

const form=document.getElementById("uploadForm");
const message=document.getElementById("message");
const submitButton=form.querySelector("button");

form.addEventListener("submit",async(e)=>{

e.preventDefault();

const startDate=form.querySelector('input[name="start_date"]').value;
const endDate=form.querySelector('input[name="end_date"]').value;
const plan=form.querySelector('select[name="plan"]').value;

const start=new Date(startDate);
const end=new Date(endDate);

const days=Math.floor((end-start)/(1000*60*60*24))+1;

if(plan==="free" && days>7){

message.innerText="Free plan supports up to 7 days per export.";
message.style.color="red";
return;

}

message.innerHTML="Processing Garmin export...<br><span style='font-size:13px;color:#777'>This may take up to ~1 minute.</span>";

submitButton.disabled=true;

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

submitButton.disabled=false;

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

submitButton.disabled=false;

});

</script>

</body>
</html>
"""


def parse_input_date(date_str, field):

    try:
        return datetime.strptime(date_str,"%Y-%m-%d").date()
    except:
        raise HTTPException(status_code=400,detail=f"Invalid {field}")


def enforce_plan_limit(plan,start,end):

    days=(end-start).days+1

    if plan=="free" and days>7:
        raise HTTPException(status_code=400,detail="Free plan supports up to 7 days per export.")

    if plan=="pro" and days>365:
        raise HTTPException(status_code=400,detail="Pro plan supports up to 365 days.")


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
        raise HTTPException(status_code=429,detail="Free plan monthly limit reached (3 exports).")

    data[month][ip]=count+1

    with open(USAGE_FILE,"w") as f:
        json.dump(data,f)


@app.post("/upload")
async def upload(request:Request,
file:UploadFile=File(...),
start_date:str=Form(...),
end_date:str=Form(...),
plan:str=Form("free")):

    ip=request.client.host

    start=parse_input_date(start_date,"start_date")
    end=parse_input_date(end_date,"end_date")

    enforce_plan_limit(plan,start,end)
    check_usage_limit(ip,plan)

    try:

        with tempfile.TemporaryDirectory() as temp:

            zip_path=os.path.join(temp,file.filename)

            with open(zip_path,"wb") as f:
                f.write(await file.read())

            with zipfile.ZipFile(zip_path) as zip_ref:
                zip_ref.extractall(temp)

            result={
            "source":"garmin",
            "plan":plan,
            "date_range":{"start":start_date,"end":end_date}
            }

            json_str=json.dumps(result,indent=2)

            return Response(
            content=json_str,
            media_type="application/json",
            headers={"Content-Disposition":"attachment; filename=train2ai_dataset.json"}
            )

    except Exception as e:

        raise HTTPException(status_code=500,detail=str(e))
