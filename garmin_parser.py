import json
import os

def load_garmin_activities(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    acts = data[0]["summarizedActivitiesExport"]

    results = []

    for a in acts:

        duration = a.get("duration", 0)
        distance = a.get("distance", 0)

        duration_s = duration / 1000 if duration > 100000 else duration

        pace = None
        if distance and duration_s:
            pace = duration_s / distance

        activity = {
            "sport": a.get("sportType"),
            "distance_m": distance,
            "duration_s": duration_s,
            "avg_speed": a.get("avgSpeed"),
            "avg_hr": a.get("avgHr"),
            "max_hr": a.get("maxHr"),
            "start_time": a.get("startTimeLocal"),
            "calories": a.get("calories"),
            "pace": pace
        }

        results.append(activity)

    return results


def save_ai_format(data, out_file):

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":

    garmin_file = "activities.json"

    data = load_garmin_activities(garmin_file)

    save_ai_format(data, "train2ai_output.json")

    print("converted", len(data), "activities")
