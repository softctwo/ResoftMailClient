#!/usr/bin/env python3
"""邮件待办追踪系统 - 标记状态、生成待办清单、超时告警。"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from analysis_rules import classify, extract_due_dates
from eas_env import add_import_path, load_env
from time_utils import SHANGHAI_TZ, parse_mail_datetime, to_beijing_time

load_env()
add_import_path()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "assistant_data"
TODO_FILE = DATA_DIR / "todo_state.json"
EMAIL_INDEX = BASE_DIR / "mail_archive" / "index" / "mail_index.json"

# 待处理超时阈值（小时）
ALERT_HOURS = {"立项审批": 24, "财务报销": 12, "商务协同": 48}
DEFAULT_ALERT_HOURS = 48


def load_todo_state() -> dict:
    if TODO_FILE.exists():
        return json.loads(TODO_FILE.read_text(encoding="utf-8"))
    return {"todos": {}, "version": 1}


def save_todo_state(state: dict) -> None:
    TODO_FILE.parent.mkdir(parents=True, exist_ok=True)
    TODO_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def make_todo_key(email: dict) -> str:
    """用去重三元组作为待办唯一键"""
    subject = email.get("subject", "")
    sender = email.get("sender", "")
    received = email.get("received_at", "")
    return f"{subject}|{sender}|{received}"


def load_emails_from_index() -> list[dict]:
    if not EMAIL_INDEX.exists():
        return []
    index = json.loads(EMAIL_INDEX.read_text(encoding="utf-8"))
    return list(index.get("emails", {}).values())


def auto_detect_todos(emails: list[dict]) -> list[dict]:
    """自动识别需要关注的邮件生成待办候选"""
    candidates = []
    for e in emails:
        subject = e.get("subject", "")
        sender = e.get("sender", "")
        category, priority, needs_attention = classify(subject, sender)
        if not needs_attention and priority not in {"🔴", "🟠"}:
            continue
        # 排除已归档/已忽略
        candidates.append({
            **e,
            "category": category,
            "priority": priority,
            "needs_attention": needs_attention,
        })
    return candidates


def sync_todos(emails: list[dict] | None = None) -> dict:
    """同步邮件索引到待办状态，保留已有状态"""
    state = load_todo_state()
    if emails is None:
        emails = load_emails_from_index()

    existing = state.get("todos", {})
    new_todos = {}

    for e in auto_detect_todos(emails):
        key = make_todo_key(e)
        old = existing.get(key)
        if old and old.get("status") in {"done", "archived", "ignored"}:
            # 保留已完成状态
            new_todos[key] = old
        else:
            new_todos[key] = {
                "key": key,
                "subject": e.get("subject"),
                "sender": e.get("sender"),
                "received_at": e.get("received_at"),
                "category": e.get("category", "其他"),
                "priority": e.get("priority", "⚪"),
                "status": old.get("status") if old else "pending",
                "created_at": old.get("created_at") if old else datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "due_dates": extract_due_dates(e.get("subject", ""), e.get("body_preview", "")),
            }

    state["todos"] = new_todos
    save_todo_state(state)
    return state


def list_todos(status: str | None = None, category: str | None = None, overdue_only: bool = False) -> list[dict]:
    state = load_todo_state()
    todos = list(state.get("todos", {}).values())
    result = []
    now = datetime.now()

    for t in todos:
        if status and t.get("status") != status:
            continue
        if category and t.get("category") != category:
            continue
        if overdue_only and t.get("status") != "pending":
            continue
        if overdue_only:
            received = t.get("received_at", "")
            hours = ALERT_HOURS.get(t.get("category"), DEFAULT_ALERT_HOURS)
            try:
                dt = datetime.fromisoformat(received.replace("Z", "+00:00")).replace(tzinfo=None)
                if (now - dt).total_seconds() < hours * 3600:
                    continue
            except (ValueError, TypeError):
                continue
        result.append(t)

    # 按优先级和时间排序
    priority_order = {"🔴": 0, "🟠": 1, "🟡": 2, "🟢": 3, "⚪": 4}
    result.sort(key=lambda x: (priority_order.get(x.get("priority"), 5), x.get("received_at", "")), reverse=False)
    return result


def update_todo_status(key: str, status: str, note: str = "") -> bool:
    state = load_todo_state()
    todos = state.get("todos", {})
    if key not in todos:
        return False
    todos[key]["status"] = status
    todos[key]["updated_at"] = datetime.now().isoformat()
    if note:
        todos[key]["note"] = note
    save_todo_state(state)
    return True


def get_todo_summary() -> dict:
    state = load_todo_state()
    todos = list(state.get("todos", {}).values())
    summary = defaultdict(int)
    overdue = 0
    now = datetime.now()
    for t in todos:
        summary[t.get("status", "unknown")] += 1
        if t.get("status") == "pending":
            cat = t.get("category", "其他")
            hours = ALERT_HOURS.get(cat, DEFAULT_ALERT_HOURS)
            try:
                dt = datetime.fromisoformat(t.get("received_at", "").replace("Z", "+00:00")).replace(tzinfo=None)
                if (now - dt).total_seconds() >= hours * 3600:
                    overdue += 1
            except (ValueError, TypeError):
                pass
    return {
        "total": len(todos),
        "by_status": dict(summary),
        "overdue": overdue,
    }


def format_todo_list(todos: list[dict]) -> str:
    if not todos:
        return "暂无待办事项。"
    lines = [f"# 待办清单（共 {len(todos)} 项）\n"]
    current_cat = None
    for t in todos:
        cat = t.get("category", "其他")
        if cat != current_cat:
            lines.append(f"\n## {cat}")
            current_cat = cat
        status_icon = {"pending": "⏳", "done": "✅", "archived": "📦", "ignored": "🚫"}.get(t.get("status"), "❓")
        due_info = ""
        if t.get("due_dates"):
            due_info = f" | 截止: {', '.join(t['due_dates'])}"
        lines.append(
            f"- {status_icon} {t.get('priority', '⚪')} {t.get('subject', '')}"
            f"\n  来自: {t.get('sender', '')} | {t.get('received_at', '')[:16]}{due_info}"
        )
    return "\n".join(lines)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="邮件待办追踪")
    sub = parser.add_subparsers(dest="command")

    p_sync = sub.add_parser("sync", help="同步邮件索引到待办库")

    p_list = sub.add_parser("list", help="列示待办")
    p_list.add_argument("--status", choices=["pending", "done", "archived", "ignored"], default=None)
    p_list.add_argument("--category", default=None)
    p_list.add_argument("--overdue", action="store_true", help="仅显示超时待办")

    p_update = sub.add_parser("update", help="更新待办状态")
    p_update.add_argument("--key", required=True, help="待办键（可用 list 查看）")
    p_update.add_argument("--status", required=True, choices=["pending", "done", "archived", "ignored"])
    p_update.add_argument("--note", default="", help="备注")

    p_summary = sub.add_parser("summary", help="待办统计")

    args = parser.parse_args()

    if args.command == "sync":
        state = sync_todos()
        print(f"同步完成，共 {len(state.get('todos', {}))} 条待办")
    elif args.command == "list":
        todos = list_todos(status=args.status, category=args.category, overdue_only=args.overdue)
        print(format_todo_list(todos))
    elif args.command == "update":
        ok = update_todo_status(args.key, args.status, args.note)
        print("更新成功" if ok else f"未找到待办: {args.key}")
    elif args.command == "summary":
        s = get_todo_summary()
        print(json.dumps(s, ensure_ascii=False, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
