from __future__ import annotations

from datetime import datetime
from typing import Optional


def parse_iso_date(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def trip_days(start_date: str, end_date: str) -> int:
    start = parse_iso_date(start_date)
    end = parse_iso_date(end_date)
    if not start or not end or end < start:
        return 0

    return (end - start).days + 1
