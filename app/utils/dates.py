from datetime import date, datetime
from fastapi import HTTPException


def parse_input_date(date_str: str, field: str) -> date:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field}.") from exc


def parse_iso_like_datetime(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).isoformat()
    except Exception:
        return None
