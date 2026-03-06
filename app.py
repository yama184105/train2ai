            workouts = []

            for workout_file in workout_files:
                with open(workout_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, list):
                    if len(data) > 0 and isinstance(data[0], dict) and "summarizedActivitiesExport" in data[0]:
                        activities = data[0].get("summarizedActivitiesExport", [])
                    else:
                        activities = data
                elif isinstance(data, dict):
                    activities = data.get("summarizedActivitiesExport", [])
                else:
                    activities = []

                for act in activities:
                    if not isinstance(act, dict):
                        continue

                    raw_start_time = act.get("startTimeLocal")
                    if raw_start_time is None:
                        continue

                    workout_date = None

                    # Garmin の startTimeLocal はミリ秒タイムスタンプのことがある
                    if isinstance(raw_start_time, (int, float)):
                        try:
                            workout_date = datetime.fromtimestamp(raw_start_time / 1000).date()
                        except Exception:
                            continue
                    else:
                        date_str = str(raw_start_time)
                        try:
                            workout_date = datetime.fromisoformat(date_str.replace("Z", "")).date()
                        except ValueError:
                            try:
                                workout_date = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
                            except ValueError:
                                continue

                    if start_dt <= workout_date <= end_dt:
                        clean_item = {
                            "date": workout_date.isoformat(),
                            "sport": act.get("sportType"),
                            "name": act.get("name"),
                            "distance_m": act.get("distance"),
                            "duration_s": act.get("duration"),
                            "avg_speed": act.get("avgSpeed"),
                            "max_speed": act.get("maxSpeed"),
                            "avg_hr": act.get("avgHr"),
                            "max_hr": act.get("maxHr"),
                            "calories": act.get("calories"),
                            "start_time_local": raw_start_time,
                            "activity_id": act.get("activityId"),
                        }
                        workouts.append(clean_item)
