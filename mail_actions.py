from __future__ import annotations

from datetime import datetime, timedelta

from analysis_rules import (
    calc_deadline_alert_level,
    detect_reimbursement_alert,
    detect_visit_reminder,
    extract_due_dates,
    extract_product_lines,
    extract_project_info,
    filter_recent,
    summarize_income_trend,
)


def build_alerts(messages: list[dict]) -> dict:
    recent = filter_recent(messages, hours=48)
    reimbursement = [m for m in recent if detect_reimbursement_alert(m)]
    project_structured = []
    for item in recent:
        if item.get("category") == "立项审批":
            project_structured.append(
                {
                    "subject": item.get("subject"),
                    "received_at": item.get("received_at"),
                    "sender": item.get("sender"),
                    "project": extract_project_info(item.get("subject", ""), item.get("body_preview", "")),
                }
            )
    return {
        "reimbursement_alerts": reimbursement,
        "project_structured": project_structured,
    }


def build_intelligence(messages: list[dict]) -> dict:
    income = summarize_income_trend(messages)
    regulatory = []
    for item in messages:
        if item.get("category") == "监管制度":
            regulatory.append(
                {
                    "subject": item.get("subject"),
                    "received_at": item.get("received_at"),
                    "sender": item.get("sender"),
                    "product_lines": extract_product_lines(item.get("subject", ""), item.get("body_preview", "")),
                }
            )
    return {
        "income_trend": income,
        "regulatory_impacts": regulatory,
    }


def build_reminders(messages: list[dict]) -> dict:
    now = datetime.now()
    visit_reminders = []
    deadline_alerts = []

    for item in messages:
        subject = item.get("subject", "")
        if detect_visit_reminder(item):
            due_dates = extract_due_dates(subject, item.get("body_preview", ""))
            remind = False
            for date_str in due_dates:
                normalized = date_str.replace("年", "-").replace("月", "-").replace("日", "")
                normalized = normalized.replace("/", "-").replace(".", "-")
                try:
                    target = datetime.strptime(normalized, "%Y-%m-%d")
                except ValueError:
                    continue
                if (target.date() - now.date()).days == 1:
                    remind = True
            if remind or not due_dates:
                visit_reminders.append(
                    {
                        "subject": subject,
                        "received_at": item.get("received_at"),
                        "sender": item.get("sender"),
                        "dates": due_dates,
                    }
                )

        due_dates = extract_due_dates(subject, item.get("body_preview", ""))
        for date_str in due_dates:
            level = calc_deadline_alert_level(date_str, now=now)
            if level:
                deadline_alerts.append(
                    {
                        "level": level,
                        "subject": subject,
                        "received_at": item.get("received_at"),
                        "due_date": date_str,
                    }
                )

    return {
        "visit_reminders": visit_reminders,
        "deadline_alerts": deadline_alerts,
    }
