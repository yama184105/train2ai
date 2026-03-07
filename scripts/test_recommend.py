"""
Smoke test for recommend_next_workout().

Run from the project root:

    python scripts/test_recommend.py
"""
import json

from app.utils.coaching import build_coaching_context, recommend_next_workout

context = build_coaching_context()
recommendation = recommend_next_workout(context)

print(json.dumps(recommendation, indent=2, ensure_ascii=False))
