from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
UTC_TZ = ZoneInfo("UTC")


def parse_mail_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None

    text = raw.strip()
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC_TZ)
            return dt
    except ValueError:
        return None


def to_beijing_time(raw: str | None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    dt = parse_mail_datetime(raw)
    if dt is None:
        return (raw or "").strip()

    return dt.astimezone(SHANGHAI_TZ).strftime(fmt)
