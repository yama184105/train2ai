# train2ai

train2ai converts your fitness export files into clean, AI-ready JSON datasets.
Upload a Garmin or Strava export ZIP and get back a structured dataset you can
feed directly into an LLM or training log analysis tool.

**Live:** https://train2ai.onrender.com

---

## What it does

| Source | Mode | Input | Output |
|---|---|---|---|
| Strava | Summary | `activities.csv` | Per-workout stats (distance, pace, HR, calories) over a date range |
| Strava | Analysis | FIT files + `activities.csv` | Compressed time-series streams (pace, HR, cadence, power, altitude) |
| Garmin | Export | Summarized activity JSON | Daily summary, sleep stages, and workout stats over a date range |

Each output is a single JSON file with explicit units, null semantics, and
sport-specific metadata included so an LLM can interpret the data without
additional context.

See [DATASET_SCHEMA.md](DATASET_SCHEMA.md) for the full schema reference.

---

## Run locally

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 in your browser.

---

## Project structure

```
app/
  main.py          # FastAPI app and upload endpoint
  config.py        # Constants and allowed values
  providers/
    garmin.py      # Garmin file scanning and dataset building
    strava.py      # Strava file scanning and dataset building
  utils/
    dates.py       # Date parsing helpers
    usage.py       # Usage tracking and rate limiting
```

---

## Notes

- Strava analysis mode compresses each FIT activity to ~200 averaged data points.
- Power and altitude streams are included only when present in the FIT file.
- Garmin exports use the official account export ZIP (summarized JSON, not raw FIT files).
- Running dynamics fields (vertical oscillation, ground contact time, etc.) are not
  available from the Garmin summarized export format.
