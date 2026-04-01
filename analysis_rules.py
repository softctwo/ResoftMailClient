from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta

APPROVAL_KEYWORDS = [
    "立项", "审批", "待办", "待审批", "打回", "报销",
    "项目结论", "变更", "验收", "合同", "预算", "紧急", "urgent",
]

CATEGORY_RULES = [
    (["打回", "报销", "借款审批", "报销系统待办"], "财务报销", "🔴"),
    (["立项", "立项结论", "预立项", "工程立项", "售前预立项结论"], "立项审批", "🟠"),
    (["客户到访", "提前进场", "提前实施"], "商务协同", "🟠"),
    (["制度", "监管", "EAST", "反洗钱", "利率报备", "数据治理", "发文"], "监管制度", "🟡"),
    (["周报", "日报", "月报"], "周报日报", "🟢"),
    (["收入", "合同负债", "计划收入", "收入执行", "收入预估"], "经营统计", "🟡"),
]

PRODUCT_LINE_RULES = {
    "一表通": ["一表通", "监管报送", "金数"],
    "EAST": ["EAST", "EAST5.0"],
    "反洗钱": ["反洗钱", "AML"],
    "利率报备": ["利率报备"],
    "数据治理": ["数据治理"],
    "票据": ["票据"],
}

PROJECT_PATTERN = re.compile(r"(?P<name>[^-]+)-(?P<code>\d{6,})")
DATE_PATTERN = re.compile(r"(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?)")


def classify(subject: str, sender: str) -> tuple[str, str, bool]:
    text = f"{subject} {sender}".lower()
    approval = any(keyword.lower() in text for keyword in APPROVAL_KEYWORDS)
    for keywords, category, priority in CATEGORY_RULES:
        if any(keyword.lower() in text for keyword in keywords):
            return category, priority, approval
    return "其他", "⚪", approval


def extract_project_info(subject: str, body: str = "") -> dict:
    source = f"{subject} {body}".strip()
    match = PROJECT_PATTERN.search(subject)
    project_name = None
    project_code = None
    if match:
        project_name = match.group("name").strip("【】 ")
        project_code = match.group("code")

    risk_points = []
    for keyword in ["延期", "风险", "利润率不足", "提前进场", "审批", "验收"]:
        if keyword in source:
            risk_points.append(keyword)

    owner = None
    owner_match = re.search(r"项目经理[：: ]*([^，。,\s]+)", source)
    if owner_match:
        owner = owner_match.group(1)

    budget = None
    budget_match = re.search(r"(预算|金额)[：: ]*([0-9.,万亿元]+)", source)
    if budget_match:
        budget = budget_match.group(2)

    return {
        "project_name": project_name or subject,
        "project_code": project_code,
        "scope": "待结合正文/附件补充",
        "budget": budget,
        "owner": owner,
        "risk_points": risk_points,
    }


def extract_product_lines(subject: str, body: str = "") -> list[str]:
    text = f"{subject} {body}"
    matched = []
    for product_line, keywords in PRODUCT_LINE_RULES.items():
        if any(keyword in text for keyword in keywords):
            matched.append(product_line)
    return matched or ["待人工确认"]


def detect_reimbursement_alert(message: dict) -> bool:
    subject = message.get("subject", "")
    return any(keyword in subject for keyword in ["打回", "报销系统待办", "报销"])


def detect_visit_reminder(message: dict) -> bool:
    subject = message.get("subject", "")
    return any(keyword in subject for keyword in ["客户到访", "提前进场", "提前实施"])


def extract_due_dates(subject: str, body: str = "") -> list[str]:
    text = f"{subject} {body}"
    return DATE_PATTERN.findall(text)


def summarize_income_trend(messages: list[dict]) -> dict:
    income_messages = [m for m in messages if m.get("category") == "经营统计"]
    subjects = [m.get("subject", "") for m in income_messages]
    monthly = Counter()
    for subject in subjects:
        month_match = re.search(r"(20\d{2}[-年]\d{1,2})", subject)
        if month_match:
            monthly[month_match.group(1)] += 1
        else:
            monthly["未识别月份"] += 1
    return {
        "count": len(income_messages),
        "trend_by_period": dict(monthly),
        "latest_subjects": subjects[:5],
    }


def calc_deadline_alert_level(date_str: str, now: datetime | None = None) -> str | None:
    now = now or datetime.now()
    normalized = date_str.replace("年", "-").replace("月", "-").replace("日", "")
    normalized = normalized.replace("/", "-").replace(".", "-")
    try:
        target = datetime.strptime(normalized, "%Y-%m-%d")
    except ValueError:
        return None
    delta_days = (target.date() - now.date()).days
    if delta_days <= 1:
        return "🔴"
    if delta_days <= 3:
        return "🟡"
    return None


def filter_recent(messages: list[dict], hours: int = 24) -> list[dict]:
    now = datetime.now()
    start = now - timedelta(hours=hours)
    result = []
    for item in messages:
        raw = item.get("received_at_raw") or item.get("received_at")
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            continue
        if dt >= start:
            result.append(item)
    return result
