# train2ai refactor

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## What changed

- Split the original single `app.py` into modules.
- Kept Garmin summary behavior.
- Added Strava support:
  - `summary` mode: `activities.csv -> JSON`
  - `analysis` mode: recent run/ride FIT files -> compressed streams JSON

## Structure

```text
app/
  main.py
  config.py
  providers/
    garmin.py
    strava.py
  utils/
    dates.py
    usage.py
```

## Notes

- Strava `analysis` mode needs `fitparse`.
- Each FIT activity is compressed to about 200 averaged points.
- Power and altitude are optional; they are only included when available.
