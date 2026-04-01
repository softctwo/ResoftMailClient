#!/usr/bin/env python3
"""龙哥邮件助手：增量拉取、分类、晨报生成、智能提醒。"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

from analysis_rules import classify
from eas_env import add_import_path, load_env
from mail_actions import build_alerts, build_intelligence, build_reminders
from time_utils import to_beijing_time

load_env()
add_import_path()

from eas_client.config import ClientConfig
from eas_client.eas.commands import (
    build_folder_sync_request,
    build_item_operations_message_request,
    build_provision_request,
    build_sync_request,
)
from eas_client.eas.parsers import (
    parse_folder_sync_response,
    parse_item_operations_message_response,
    parse_sync_response,
)
from eas_client.transport import EasTransport

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "assistant_data"
STATE_FILE = DATA_DIR / "assistant_state.json"
MAILBOX_FILE = DATA_DIR / "latest_messages.json"
REPORT_DIR = DATA_DIR / "reports"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"inbox_id": None, "last_server_ids": [], "last_sync_at": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def save_messages(messages: list[dict]) -> None:
    MAILBOX_FILE.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")


def load_messages() -> list[dict]:
    if not MAILBOX_FILE.exists():
        return []
    return json.loads(MAILBOX_FILE.read_text(encoding="utf-8"))


def get_transport() -> EasTransport:
    config = ClientConfig.from_env()
    transport = EasTransport(config)
    resp1 = transport.post("Provision", build_provision_request())
    keys1 = re.findall(rb"\x03(\d{8,})\x00", resp1)
    if not keys1:
        raise RuntimeError("Provision 第一步失败")
    resp2 = transport.post("Provision", build_provision_request(policy_key=keys1[0].decode()))
    keys2 = re.findall(rb"\x03(\d{8,})\x00", resp2)
    if not keys2:
        raise RuntimeError("Provision 第二步失败")
    return transport


def get_inbox_id(transport: EasTransport, state: dict) -> str:
    if state.get("inbox_id"):
        return state["inbox_id"]

    folders = parse_folder_sync_response(transport.post("FolderSync", build_folder_sync_request(sync_key="0")))
    for folder in folders.folders:
        if str(folder.folder_type) == "2" or "收件箱" in (folder.display_name or ""):
            state["inbox_id"] = folder.server_id
            save_state(state)
            return folder.server_id
    raise RuntimeError("未找到收件箱")


def fetch_recent_messages(limit: int = 30, include_body: bool = False) -> list[dict]:
    ensure_dirs()
    state = load_state()
    transport = get_transport()
    inbox_id = get_inbox_id(transport, state)

    sync1 = parse_sync_response(
        transport.post("Sync", build_sync_request(collection_id=inbox_id, sync_key="0", window_size=limit))
    )
    messages = list(sync1.messages)
    if sync1.sync_key and sync1.sync_key != "0":
        sync2 = parse_sync_response(
            transport.post(
                "Sync",
                build_sync_request(collection_id=inbox_id, sync_key=sync1.sync_key, window_size=limit),
            )
        )
        messages = list(sync2.messages)

    results: list[dict] = []
    for message in messages[:limit]:
        subject = message.subject or "(无主题)"
        sender = message.sender or "(未知)"
        category, priority, needs_attention = classify(subject, sender)
        item = {
            "server_id": message.server_id,
            "subject": subject,
            "sender": sender,
            "received_at": to_beijing_time(message.received_at),
            "received_at_raw": message.received_at,
            "category": category,
            "priority": priority,
            "needs_attention": needs_attention,
            "attachments": [asdict(a) for a in message.attachments],
        }
        if include_body:
            detail = parse_item_operations_message_response(
                transport.post(
                    "ItemOperations",
                    build_item_operations_message_request(collection_id=inbox_id, server_id=message.server_id),
                )
            )
            body = detail.body or ""
            item["body_preview"] = re.sub(r"\s+", " ", body)[:500]
        results.append(item)

    state["last_server_ids"] = [item["server_id"] for item in results]
    state["last_sync_at"] = datetime.now().isoformat()
    save_state(state)
    save_messages(results)
    return results


def detect_new_messages(current: list[dict], previous: list[dict]) -> list[dict]:
    previous_ids = {item.get("server_id") for item in previous}
    return [item for item in current if item.get("server_id") not in previous_ids]


def build_digest(messages: list[dict], hours: int = 12) -> dict:
    now = datetime.now()
    window_start = now - timedelta(hours=hours)
    selected = []
    for item in messages:
        raw = item.get("received_at_raw") or item.get("received_at")
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            continue
        if dt >= window_start:
            selected.append(item)

    selected.sort(key=lambda item: item.get("received_at", ""), reverse=True)
    important = [m for m in selected if m.get("priority") in {"🔴", "🟠", "🟡"}]
    approvals = [m for m in selected if m.get("needs_attention")]
    finance_pushbacks = [m for m in selected if "打回" in m.get("subject", "")]
    visits = [m for m in selected if "客户到访" in m.get("subject", "")]
    category_counter = Counter(item.get("category", "其他") for item in selected)

    return {
        "generated_at": now.isoformat(),
        "window_hours": hours,
        "total_recent": len(selected),
        "important": important[:8],
        "approvals": approvals[:8],
        "finance_pushbacks": finance_pushbacks[:8],
        "visits": visits[:8],
        "category_stats": dict(category_counter.most_common()),
    }


def format_digest_text(digest: dict) -> str:
    lines = [
        "# 邮件晨报",
        f"生成时间：{digest['generated_at'][:19].replace('T', ' ')}",
        f"统计窗口：最近 {digest['window_hours']} 小时",
        f"邮件总量：{digest['total_recent']} 封",
        "",
        "## 一、待关注事项",
    ]

    if digest["approvals"]:
        for item in digest["approvals"][:5]:
            lines.append(f"- {item['priority']} [{item['category']}] {item['subject']} | {item['sender']}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 二、报销/打回提醒"])
    if digest["finance_pushbacks"]:
        for item in digest["finance_pushbacks"][:5]:
            lines.append(f"- {item['subject']} | {item['sender']}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 三、客户到访/商务协同"])
    if digest["visits"]:
        for item in digest["visits"][:5]:
            lines.append(f"- {item['subject']} | {item['sender']}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 四、分类统计"])
    if digest["category_stats"]:
        for category, count in digest["category_stats"].items():
            lines.append(f"- {category}: {count} 封")
    else:
        lines.append("- 无")

    lines.extend(["", "## 五、重要邮件摘要"])
    if digest["important"]:
        for item in digest["important"][:5]:
            lines.append(f"- {item['priority']} {item['subject']} | {item['sender']} | {item.get('received_at', '')}（北京时间）")
    else:
        lines.append("- 无")

    return "\n".join(lines)


def write_digest_file(digest: dict) -> Path:
    ensure_dirs()
    date_key = datetime.now().strftime("%Y-%m-%d")
    output = REPORT_DIR / f"morning_digest_{date_key}.md"
    output.write_text(format_digest_text(digest), encoding="utf-8")
    return output


def run_poll(limit: int = 30) -> dict:
    previous = load_messages()
    current = fetch_recent_messages(limit=limit, include_body=False)
    new_messages = detect_new_messages(current, previous)
    return {
        "fetched": len(current),
        "new_count": len(new_messages),
        "new_messages": new_messages,
    }


def run_morning_report(limit: int = 50, hours: int = 24) -> dict:
    messages = fetch_recent_messages(limit=limit, include_body=False)
    digest = build_digest(messages, hours=hours)
    report_path = write_digest_file(digest)
    return {
        "report_path": str(report_path),
        "digest": digest,
        "text": format_digest_text(digest),
    }


def run_alerts(limit: int = 30) -> dict:
    messages = fetch_recent_messages(limit=limit, include_body=True)
    return build_alerts(messages)


def run_intelligence(limit: int = 50) -> dict:
    messages = fetch_recent_messages(limit=limit, include_body=True)
    return build_intelligence(messages)


def run_reminders(limit: int = 50) -> dict:
    messages = fetch_recent_messages(limit=limit, include_body=True)
    return build_reminders(messages)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="龙哥邮件助手")
    parser.add_argument("action", choices=["poll", "morning-report", "alerts", "intelligence", "reminders"])
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()

    if args.action == "poll":
        print(json.dumps(run_poll(limit=args.limit), ensure_ascii=False, indent=2))
    elif args.action == "morning-report":
        result = run_morning_report(limit=args.limit, hours=args.hours)
        print(result["text"])
        print(f"\n报告已写入: {result['report_path']}")
    elif args.action == "alerts":
        print(json.dumps(run_alerts(limit=args.limit), ensure_ascii=False, indent=2))
    elif args.action == "intelligence":
        print(json.dumps(run_intelligence(limit=args.limit), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(run_reminders(limit=args.limit), ensure_ascii=False, indent=2))
