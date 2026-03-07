from __future__ import annotations

import json
from fastapi import HTTPException, Request

from app.config import FREE_TOTAL_LIMIT, USAGE_FILE


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def load_usage() -> dict:
    if USAGE_FILE.exists():
        try:
            data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {"free_total_by_ip": {}}


def save_usage(data: dict) -> None:
    USAGE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_usage_count(ip: str, plan: str) -> int:
    if plan != "free":
        return 0
    data = load_usage()
    return int(data.get("free_total_by_ip", {}).get(ip, 0))


def check_usage_limit_only(ip: str, plan: str) -> None:
    if plan != "free":
        return
    count = get_usage_count(ip, plan)
    if count >= FREE_TOTAL_LIMIT:
        raise HTTPException(status_code=429, detail=f"Free plan total limit reached ({FREE_TOTAL_LIMIT} exports).")


def increment_usage(ip: str, plan: str) -> None:
    if plan != "free":
        return
    data = load_usage()
    totals = data.get("free_total_by_ip", {})
    totals[ip] = int(totals.get(ip, 0)) + 1
    data["free_total_by_ip"] = totals
    save_usage(data)
