from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
UTC_TZ = ZoneInfo("UTC")


def to_beijing_time(raw: str | None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    if not raw:
        return ""

    text = raw.strip()
    try:
        if text.endswith("Z"):
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC_TZ)
        return dt.astimezone(SHANGHAI_TZ).strftime(fmt)
    except ValueError:
        return text
