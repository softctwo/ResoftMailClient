from datetime import datetime as real_datetime

import mail_assistant


class FrozenDateTime:
    @classmethod
    def now(cls, tz=None) -> real_datetime:
        value = real_datetime(2026, 4, 1, 10, 30, 0)
        if tz is not None:
            return value.replace(tzinfo=tz)
        return value

    @classmethod
    def fromisoformat(cls, value: str) -> real_datetime:
        return real_datetime.fromisoformat(value)


def test_build_digest_uses_raw_utc_timestamp_in_local_window(monkeypatch) -> None:
    monkeypatch.setattr(mail_assistant, "datetime", FrozenDateTime)

    digest = mail_assistant.build_digest(
        [
            {
                "server_id": "m1",
                "subject": "审批提醒",
                "sender": "bot@example.com",
                "received_at": "2026-04-01 09:00:00",
                "received_at_raw": "2026-04-01T01:00:00Z",
                "category": "其他",
                "priority": "🔴",
                "needs_attention": True,
            }
        ],
        hours=2,
    )

    assert digest["total_recent"] == 1
