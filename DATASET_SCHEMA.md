# train2ai Dataset Schema

This document defines the official schema for datasets produced by train2ai.
All fields listed here reflect the current implementation. Do not change output
structure without updating this document.

---

## Table of Contents

1. [Overview](#overview)
2. [Top-Level Fields — All Outputs](#top-level-fields--all-outputs)
3. [Strava — Summary Mode](#strava--summary-mode)
4. [Strava — Analysis Mode](#strava--analysis-mode)
5. [Garmin — Export Mode](#garmin--export-mode)
6. [Compressed Streams](#compressed-streams)
7. [Metadata Sections](#metadata-sections)
8. [Units](#units)
9. [Null Semantics](#null-semantics)
10. [Source and Mode Differences](#source-and-mode-differences)

---

## Overview

train2ai produces a single JSON file per export. The top-level structure differs
by source (`strava` / `garmin`) and mode (`summary` / `analysis`).

All outputs share a common envelope. Source-specific sections are described
separately below.

---

## Top-Level Fields — All Outputs

These fields are present in every dataset regardless of source or mode.

| Field | Type | Required | Description |
|---|---|---|---|
| `source` | string | yes | `"strava"` or `"garmin"` |
| `schema_version` | string | yes | Schema version string. Strava: `"2.3"`. Garmin: `"1.2"`. |
| `plan` | string | yes | `"free"` or `"pro"` |
| `mode` | string | yes (Strava only) | `"summary"` or `"analysis"` |
| `sport` | string | yes (Strava only) | `"run"`, `"ride"`, or `"all"` (summary only) |
| `date_range` | object | yes | `{ "start": "YYYY-MM-DD", "end": "YYYY-MM-DD" }` |
| `dataset_info` | object | yes (Strava only) | Unit definitions for every field. See [Metadata Sections](#metadata-sections). |
| `null_policy` | object | yes (Strava only) | Null semantics per field. See [Metadata Sections](#metadata-sections). |
| `sport_semantics` | object | yes (Strava only) | Sport-specific interpretation of pace, cadence, and power. |
| `workouts` | array | yes | Array of workout objects. May be empty. |
| `record_counts` | object | yes | Count of records per data type included in this export. |

---

## Strava — Summary Mode

**When:** `source = "strava"`, `mode = "summary"`

### Additional top-level fields

| Field | Type | Description |
|---|---|---|
| `sport` | string | `"run"`, `"ride"`, or `"all"` |
| `date_range.start` | string | Inclusive start date, `YYYY-MM-DD` |
| `date_range.end` | string | Inclusive end date, `YYYY-MM-DD` |

### Workout object

Each element of `workouts` contains:

| Field | Type | Required | Description |
|---|---|---|---|
| `date` | string | yes | Activity date, `YYYY-MM-DD` |
| `title` | string\|null | yes | Activity name from Strava CSV |
| `sport` | string\|null | yes | Normalised sport: `"run"`, `"ride"`, or raw type if unrecognised |
| `distance_km` | number\|null | yes | Distance in kilometres |
| `duration_min` | number\|null | yes | Moving time in minutes |
| `elapsed_min` | number\|null | yes | Elapsed (wall-clock) time in minutes |
| `avg_hr` | number\|null | yes | Average heart rate in bpm |
| `max_hr` | number\|null | yes | Maximum heart rate in bpm |
| `calories` | number\|null | yes | Kilocalories |

### Example (abridged)

```json
{
  "source": "strava",
  "schema_version": "2.3",
  "plan": "free",
  "mode": "summary",
  "sport": "run",
  "date_range": { "start": "2024-01-01", "end": "2024-03-31" },
  "dataset_info": { ... },
  "null_policy": { ... },
  "sport_semantics": { ... },
  "workouts": [
    {
      "date": "2024-01-14",
      "title": "Morning Run",
      "sport": "run",
      "distance_km": 10.2,
      "duration_min": 52.3,
      "elapsed_min": 54.1,
      "avg_hr": 148,
      "max_hr": 172,
      "calories": 620
    }
  ],
  "record_counts": { "workouts": 1 }
}
```

---

## Strava — Analysis Mode

**When:** `source = "strava"`, `mode = "analysis"`

### Additional top-level fields

| Field | Type | Description |
|---|---|---|
| `analysis_scope` | string | `"recent"` or `"date"` |
| `target_stream_points` | number | Target number of compressed points per stream. Always `200`. |
| `recent_count` | number | Present only when `analysis_scope = "recent"`. Number of workouts requested. |
| `activity_date` | string | Present only when `analysis_scope = "date"`. `YYYY-MM-DD`. |

### Workout object

Each element of `workouts` contains:

| Field | Type | Required | Description |
|---|---|---|---|
| `date` | string\|null | yes | Activity date derived from FIT session start time, `YYYY-MM-DD` |
| `sport` | string | yes | Normalised sport passed through from the request: `"run"` or `"ride"` |
| `title` | string\|null | yes | Activity name from Strava CSV |
| `distance_km` | number\|null | yes | Total distance in kilometres from FIT session |
| `duration_min` | number\|null | yes | Timer time in minutes from FIT session |
| `avg_hr` | number\|null | yes | Average heart rate in bpm from FIT session |
| `max_hr` | number\|null | yes | Maximum heart rate in bpm from FIT session |
| `compressed_streams` | object | yes | Down-sampled time-series streams. See [Compressed Streams](#compressed-streams). |
| `analysis_features` | object | yes | Stream availability summary. See below. |

### `analysis_features` object

Injected into each workout automatically. Tells consumers which streams have
at least one non-null value without requiring them to scan the arrays.

| Field | Type | Description |
|---|---|---|
| `available_streams` | string[] | Names of stream keys that contain at least one non-null value |
| `stream_point_count` | number | Length of `elapsed_sec` (all streams have the same length) |

### Example (abridged)

```json
{
  "source": "strava",
  "schema_version": "2.3",
  "plan": "free",
  "mode": "analysis",
  "analysis_scope": "recent",
  "sport": "run",
  "target_stream_points": 200,
  "recent_count": 5,
  "dataset_info": { ... },
  "null_policy": { ... },
  "sport_semantics": { ... },
  "workouts": [
    {
      "date": "2024-03-10",
      "sport": "run",
      "title": "Long Run",
      "distance_km": 21.1,
      "duration_min": 112.5,
      "avg_hr": 151,
      "max_hr": 174,
      "compressed_streams": {
        "elapsed_sec": [0, 34, 68, ...],
        "pace_min_per_km": [5.21, 5.18, 5.24, ...],
        "heart_rate": [132, 138, 144, ...],
        "cadence": [166, 168, 170, ...],
        "altitude_m": [84.2, 85.0, 86.1, ...]
      },
      "analysis_features": {
        "available_streams": ["elapsed_sec", "pace_min_per_km", "heart_rate", "cadence", "altitude_m"],
        "stream_point_count": 198
      }
    }
  ],
  "record_counts": { "workouts": 5 }
}
```

---

## Garmin — Export Mode

**When:** `source = "garmin"`

Garmin exports are sourced from the official Garmin account export ZIP.
The data comes from pre-aggregated summary JSON files, **not raw FIT files**.
Running dynamics fields (vertical oscillation, ground contact time, etc.) are
not available from this source.

### Additional top-level fields

| Field | Type | Description |
|---|---|---|
| `included_data` | string[] | Which data types were requested: any of `"daily_summary"`, `"sleep"`, `"workouts"` |
| `field_notes` | object | Human-readable notes on field normalization and known limitations |

### `daily_summary` array

Present when `"daily_summary"` is in `included_data`. One entry per calendar day.

| Field | Type | Required | Description |
|---|---|---|---|
| `date` | string | yes | Calendar date, `YYYY-MM-DD` |
| `steps` | number\|null | yes | Total step count |
| `total_calories` | number\|null | yes | Total kilocalories burned |
| `active_calories` | number\|null | yes | Active kilocalories burned |
| `distance_km` | number\|null | yes | Total distance in kilometres |
| `resting_hr` | number\|null | yes | Resting heart rate in bpm |

### `sleep` array

Present when `"sleep"` is in `included_data`. One entry per night.

| Field | Type | Required | Description |
|---|---|---|---|
| `date` | string | yes | Calendar date the sleep is attributed to, `YYYY-MM-DD` |
| `sleep_start` | string\|null | yes | Sleep start timestamp (ISO 8601, GMT) |
| `sleep_end` | string\|null | yes | Sleep end timestamp (ISO 8601, GMT) |
| `deep_sleep_min` | number | yes | Deep sleep in minutes (0 if not recorded) |
| `light_sleep_min` | number | yes | Light sleep in minutes (0 if not recorded) |
| `rem_sleep_min` | number | yes | REM sleep in minutes (0 if not recorded) |

### `workouts` array

Present when `"workouts"` is in `included_data`. One entry per activity.

| Field | Type | Required | Description |
|---|---|---|---|
| `date` | string | yes | Activity date derived from `startTimeLocal`, `YYYY-MM-DD` |
| `sport` | string\|null | yes | Raw `sportType` string from Garmin (not normalised) |
| `distance_km` | number\|null | yes | Distance in kilometres (source unit: centimetres) |
| `duration_min` | number\|null | yes | Duration in minutes (source unit: milliseconds) |
| `avg_hr` | number\|null | yes | Average heart rate in bpm |
| `max_hr` | number\|null | yes | Maximum heart rate in bpm |

### `record_counts` object

| Field | Description |
|---|---|
| `daily_summary` | Number of daily summary records included |
| `sleep` | Number of sleep records included |
| `workouts` | Number of workout records included |

### Example (abridged)

```json
{
  "source": "garmin",
  "schema_version": "1.2",
  "plan": "free",
  "date_range": { "start": "2024-01-01", "end": "2024-01-07" },
  "included_data": ["daily_summary", "sleep", "workouts"],
  "field_notes": {
    "daily_summary.distance_km": "Distance in kilometers.",
    "workouts.distance_km": "Distance in kilometers, normalized from Garmin summarized activity export.",
    "limitations": [
      "No second-by-second workout time series.",
      "No GPS track in output JSON.",
      "No in-app AI coaching."
    ]
  },
  "daily_summary": [
    {
      "date": "2024-01-01",
      "steps": 9842,
      "total_calories": 2310,
      "active_calories": 480,
      "distance_km": 7.4,
      "resting_hr": 52
    }
  ],
  "sleep": [
    {
      "date": "2024-01-01",
      "sleep_start": "2023-12-31T22:14:00",
      "sleep_end": "2024-01-01T06:32:00",
      "deep_sleep_min": 74,
      "light_sleep_min": 188,
      "rem_sleep_min": 62
    }
  ],
  "workouts": [
    {
      "date": "2024-01-03",
      "sport": "running",
      "distance_km": 10.1,
      "duration_min": 51.2,
      "avg_hr": 145,
      "max_hr": 169
    }
  ],
  "record_counts": {
    "daily_summary": 7,
    "sleep": 7,
    "workouts": 3
  }
}
```

---

## Compressed Streams

Streams appear only in Strava analysis mode, inside each workout's
`compressed_streams` object.

Each stream is a flat array. All arrays within one workout have the same length
(up to `target_stream_points`, default 200). Values are averaged within buckets
of raw FIT records.

### Always-present stream keys

| Key | Unit | Description |
|---|---|---|
| `elapsed_sec` | seconds | Elapsed time from activity start at the midpoint of each bucket |
| `pace_min_per_km` | min/km | Average pace derived from speed (lower = faster). Null when no speed data is available in the FIT file. |
| `heart_rate` | bpm | Average heart rate. Null when no HR monitor was paired. |
| `cadence` | spm or rpm | Average cadence. Steps per minute for runs; revolutions per minute for rides. Null when no cadence sensor was paired. |

### Optional stream keys

These keys are present at the workout level only if at least one bucket in that
workout produced a non-null value. They are omitted entirely otherwise.

| Key | Unit | Description |
|---|---|---|
| `power` | watts | Average power. Runs: running power meter. Rides: cycling power meter. |
| `altitude_m` | metres | GPS altitude above sea level. |

### Speed resolution order for `pace_min_per_km`

Speed is resolved per FIT record using this priority:

1. `speed` field
2. `enhanced_speed` field (used by newer Garmin devices)
3. Derived from consecutive `distance` and `timestamp` deltas

If none of these are available for a record, that record contributes `null` to
the bucket average.

---

## Metadata Sections

These three objects appear at the top level of every Strava output (both modes).

### `dataset_info`

```json
{
  "dataset_info": {
    "units": {
      "distance_km": "kilometers",
      "duration_min": "minutes",
      "elapsed_min": "minutes",
      "avg_hr": "beats per minute",
      "max_hr": "beats per minute",
      "calories": "kilocalories",
      "pace_min_per_km": "minutes per kilometer (lower = faster)",
      "cadence": "steps or revolutions per minute (see sport_semantics)",
      "power": "watts",
      "altitude_m": "meters above sea level",
      "elapsed_sec": "seconds from activity start"
    }
  }
}
```

### `null_policy`

```json
{
  "null_policy": {
    "meaning": "null indicates the value was not recorded or could not be derived",
    "pace_min_per_km": "null when speed, enhanced_speed, and distance/time deltas are all absent in the FIT data",
    "heart_rate": "null when no HR monitor was paired during the activity",
    "cadence": "null when no cadence sensor was paired during the activity",
    "power": "null when no power meter was paired; key omitted entirely if no activity in the dataset has power data",
    "altitude_m": "null when GPS altitude was unavailable; key omitted entirely if no activity has altitude data"
  }
}
```

### `sport_semantics`

For `sport = "run"`:

```json
{
  "sport_semantics": {
    "sport": "run",
    "pace_interpretation": "pace_min_per_km is the primary intensity metric; lower values indicate faster running",
    "cadence_interpretation": "cadence is steps per minute; typical range 150-200 spm",
    "power_interpretation": "running power in watts if a running power meter was used"
  }
}
```

For `sport = "ride"`:

```json
{
  "sport_semantics": {
    "sport": "ride",
    "pace_interpretation": "pace_min_per_km is derived from cycling speed; speed in km/h = 60 / pace_min_per_km",
    "cadence_interpretation": "cadence is pedaling revolutions per minute; typical range 70-110 rpm",
    "power_interpretation": "cycling power in watts from a power meter; primary intensity metric when available"
  }
}
```

---

## Units

| Field | Unit | Notes |
|---|---|---|
| `distance_km` | km | All sources |
| `duration_min` | min | All sources |
| `elapsed_min` | min | Strava summary only |
| `avg_hr` | bpm | All sources |
| `max_hr` | bpm | All sources |
| `calories` | kcal | Strava summary only |
| `pace_min_per_km` | min/km | Strava analysis streams only |
| `cadence` | spm (run) / rpm (ride) | Strava analysis streams only |
| `power` | watts | Strava analysis streams, optional |
| `altitude_m` | metres | Strava analysis streams, optional |
| `elapsed_sec` | seconds | Strava analysis streams only |
| `deep_sleep_min` | min | Garmin sleep only |
| `light_sleep_min` | min | Garmin sleep only |
| `rem_sleep_min` | min | Garmin sleep only |
| `steps` | count | Garmin daily summary only |
| `total_calories` | kcal | Garmin daily summary only |
| `active_calories` | kcal | Garmin daily summary only |
| `resting_hr` | bpm | Garmin daily summary only |

---

## Null Semantics

| Value | Meaning |
|---|---|
| `null` | The value was not recorded, not available in the source file, or could not be derived |
| `0` | A genuine zero measurement (e.g. 0 steps, 0 rem sleep seconds) |
| Key absent | For optional stream keys (`power`, `altitude_m`): no data existed anywhere in the dataset for that field |

`null` never means zero. `0` is always a real value.

Sleep duration fields (`deep_sleep_min`, `light_sleep_min`, `rem_sleep_min`) are
set to `0` rather than `null` when the source field is absent, because Garmin
exports omit stages rather than writing `null`.

---

## Source and Mode Differences

| Feature | Strava Summary | Strava Analysis | Garmin |
|---|---|---|---|
| Schema version | `2.3` | `2.3` | `1.2` |
| Data source | `activities.csv` | FIT files (`.fit.gz`) + `activities.csv` | Summarized activity JSON + UDS JSON |
| Time series streams | No | Yes (`compressed_streams`) | No |
| Per-workout pace | No | Yes | No |
| Per-workout cadence | No | Yes | No |
| Per-workout power | No | Optional | No |
| Calories per workout | Yes | No | No |
| Elapsed time | Yes (`elapsed_min`) | No | No |
| Daily step count | No | No | Yes |
| Sleep data | No | No | Yes |
| Running dynamics | No | No | Not available in source |
| Sport filter | Yes (`run`, `ride`, `all`) | Yes (`run`, `ride`) | No (all sport types included) |
| Date filter | Yes (range) | Yes (recent N or specific date) | Yes (range) |
| `dataset_info` | Yes | Yes | No |
| `null_policy` | Yes | Yes | No |
| `sport_semantics` | Yes | Yes | No |
| `analysis_features` per workout | No | Yes | No |
