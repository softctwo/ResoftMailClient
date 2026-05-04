#!/usr/bin/env python3
"""附件管理器 - 仅扫描清单（服务端限制禁止下载附件）。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from eas_env import add_import_path, load_env
from analysis_rules import extract_project_info

load_env()
add_import_path()

from eas_client.config import ClientConfig
from eas_client.eas.commands import (
    build_folder_sync_request,
    build_provision_request,
    build_sync_request,
)
from eas_client.eas.parsers import parse_folder_sync_response, parse_sync_response
from eas_client.transport import EasTransport

BASE_DIR = Path(__file__).resolve().parent
ARCHIVE_DIR = BASE_DIR / "mail_archive"
ATTACHMENTS_DIR = ARCHIVE_DIR / "attachments"
INDEX_FILE = ARCHIVE_DIR / "index" / "mail_index.json"


def get_transport() -> EasTransport:
    config = ClientConfig.from_env()
    transport = EasTransport(config)
    resp = transport.post("Provision", build_provision_request())
    pk1_list = re.findall(rb'\x03(\d{8,})\x00', resp)
    if not pk1_list:
        raise RuntimeError("Provision 第一步未返回 PolicyKey")
    resp = transport.post("Provision", build_provision_request(policy_key=pk1_list[0].decode()))
    pk2_list = re.findall(rb'\x03(\d{8,})\x00', resp)
    if not pk2_list:
        raise RuntimeError("Provision 第二步未返回 PolicyKey")
    transport.config = ClientConfig(
        **{k: getattr(config, k) for k in [
            "server", "username", "password", "account_email", "device_id",
            "device_type", "user_agent", "protocol_version", "endpoint_path",
            "ews_endpoint_path", "use_tls", "verify_tls", "timeout"
        ]},
        policy_key=pk2_list[0].decode(),
    )
    return transport


def get_inbox_id(transport: EasTransport) -> str:
    resp = transport.post("FolderSync", build_folder_sync_request(sync_key="0"))
    folders = parse_folder_sync_response(resp)
    for f in folders.folders:
        if str(f.folder_type) == "2" or "收件箱" in (f.display_name or ""):
            return f.server_id
    return "14"


def load_index() -> dict:
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    return {"emails": {}}


def resolve_project_folder(subject: str) -> str:
    info = extract_project_info(subject)
    code = info.get("project_code")
    if code:
        return code
    for pattern in [
        r"(北京银行[^-|】]+)", r"(恒生银行[^-|】]+)", r"(法兴银行[^-|】]+)",
        r"(稠州银行[^-|】]+)", r"(鞍钢[^-|】]+)", r"(中国建材[^-|】]+)",
        r"(天津农发行[^-|】]+)", r"(平安信托[^-|】]+)", r"(格力财务[^-|】]+)",
        r"(国家开发银行[^-|】]+)", r"(湖北农信[^-|】]+)", r"(徐工集团[^-|】]+)",
        r"(中建材[^-|】]+)", r"(德意志银行[^-|】]+)", r"(柳州银行[^-|】]+)",
    ]:
        match = re.search(pattern, subject)
        if match:
            return match.group(0).strip("【】 ")
    return "general"


def sanitize_folder_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name)[:60]


def list_attachments_from_server(max_emails: int = 50, category_filter: str | None = None) -> list[dict]:
    """从服务器列示附件清单（不下载）"""
    transport = get_transport()
    inbox_id = get_inbox_id(transport)

    resp = transport.post("Sync", build_sync_request(collection_id=inbox_id, sync_key="0", window_size=max_emails))
    sync1 = parse_sync_response(resp)
    messages = list(sync1.messages)
    if sync1.sync_key and sync1.sync_key != "0":
        resp = transport.post("Sync", build_sync_request(collection_id=inbox_id, sync_key=sync1.sync_key, window_size=max_emails))
        sync2 = parse_sync_response(resp)
        messages = list(sync2.messages)

    results = []
    for msg in messages[:max_emails]:
        subject = msg.subject or "(无主题)"
        sender = msg.sender or "(未知)"
        if category_filter:
            from analysis_rules import classify
            cat, _, _ = classify(subject, sender)
            if cat != category_filter:
                continue
        if msg.attachments:
            for att in msg.attachments:
                results.append({
                    "subject": subject,
                    "sender": sender,
                    "filename": att.display_name,
                    "size": att.size,
                    "file_reference": att.file_reference,
                })
    return results


def list_downloaded() -> list[dict]:
    """列示本地已归档的附件记录"""
    results = []
    if not ATTACHMENTS_DIR.exists():
        return results
    for folder in ATTACHMENTS_DIR.iterdir():
        if folder.is_dir():
            for f in folder.iterdir():
                if f.is_file():
                    results.append({
                        "project": folder.name,
                        "filename": f.name,
                        "size": f.stat().st_size,
                        "path": str(f.relative_to(BASE_DIR)),
                    })
    return sorted(results, key=lambda x: x["path"])


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="附件管理器（仅扫描清单，服务端限制禁止下载）")
    sub = parser.add_subparsers(dest="command")

    p_scan = sub.add_parser("scan", help="扫描服务器上的附件清单")
    p_scan.add_argument("--max", type=int, default=50)
    p_scan.add_argument("--category", default=None)

    p_list = sub.add_parser("list", help="列示本地已归档的附件记录")

    args = parser.parse_args()

    if args.command == "scan":
        items = list_attachments_from_server(max_emails=args.max, category_filter=args.category)
        print(f"服务器上发现 {len(items)} 个附件:\n")
        for item in items:
            size_str = f"({item['size']} bytes)" if item['size'] else ""
            print(f"- {item['filename']} {size_str}")
            print(f"  邮件: {item['subject'][:50]}")
            print(f"  来源: {item['sender'][:30]}")
    elif args.command == "list":
        items = list_downloaded()
        if not items:
            print("暂无本地附件记录")
            return
        current_project = None
        for item in items:
            if item["project"] != current_project:
                print(f"\n[{item['project']}]")
                current_project = item["project"]
            size_kb = item["size"] / 1024
            print(f"  {item['filename']} ({size_kb:.1f} KB)")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
