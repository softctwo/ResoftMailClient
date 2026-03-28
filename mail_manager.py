#!/usr/bin/env python3
"""
EAS 邮件管理器
- 全量/增量下载邮件到本地
- 自动分类存储
- 维护邮件索引
- 生成日报/周报/月报
"""

import json
import os
import re
import sys
import time
import warnings
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

# 加载环境变量
env_file = Path(__file__).parent / ".env.eas"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

sys.path.insert(0, str(Path(__file__).parent / "src"))

from eas_client.config import ClientConfig
from eas_client.eas.commands import (
    build_sync_request,
    build_provision_request,
    build_folder_sync_request,
    build_item_operations_message_request,
)
from eas_client.eas.parsers import (
    parse_sync_response,
    parse_folder_sync_response,
    parse_item_operations_message_response,
)
from eas_client.transport import EasTransport
from bs4 import BeautifulSoup

# ========== 路径配置 ==========
ARCHIVE_DIR = Path(__file__).parent / "mail_archive"
INDEX_FILE = ARCHIVE_DIR / "index" / "mail_index.json"
STATE_FILE = ARCHIVE_DIR / "index" / "sync_state.json"

# ========== 分类规则 ==========
CATEGORY_RULES = [
    (["周报", "项目周报"], "周报", "weekly_reports"),
    (["立项", "工程立项", "研发立项", "售前及工程立项", "立项结论", "立项评审"], "立项审批", "project_approval"),
    (["制度发文", "监管", "发文通知", "新发文", "监管数据", "数据治理", "普惠金融",
      "EAST", "AML", "金数", "利率报备", "反洗钱"], "监管制度", "regulatory"),
    (["报销", "待办提醒", "打回", "借款审批"], "财务报销", "finance"),
    (["工资条", "收入", "合同负债", "收入执行", "财务机器人"], "财务统计", "finance_stats"),
    (["放假", "行政服务", "清明节", "劳动节", "国庆节", "春节", "中秋节"], "行政通知", "admin"),
    (["客户到访", "提前进场", "提前实施"], "商务审批", "business"),
    (["客户", "线索", "认领", "责任客户"], "商务线索", "leads"),
    (["版本", "升级", "制度升级"], "产品升级", "product_upgrade"),
    (["测试", "SendMail", "OpenClaw"], "系统测试", "system_test"),
]

DEFAULT_CATEGORY = "其他"
DEFAULT_FOLDER = "other"


def get_category(subject: str) -> tuple:
    """根据主题分类"""
    for keywords, cat_name, folder in CATEGORY_RULES:
        for kw in keywords:
            if kw in subject:
                return cat_name, folder
    return DEFAULT_CATEGORY, DEFAULT_FOLDER


def ensure_dirs():
    """确保所有目录存在"""
    all_folders = set(f for _, _, f in CATEGORY_RULES)
    all_folders.add(DEFAULT_FOLDER)
    for f in all_folders:
        (ARCHIVE_DIR / f).mkdir(parents=True, exist_ok=True)
    (ARCHIVE_DIR / "index").mkdir(parents=True, exist_ok=True)
    (ARCHIVE_DIR / "reports").mkdir(parents=True, exist_ok=True)


def load_index() -> dict:
    """加载邮件索引"""
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    return {"emails": {}, "stats": {"total": 0, "last_sync": None, "by_category": {}, "by_sender": {}}}


def save_index(index: dict):
    """保存邮件索引"""
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_subject(subject: str) -> str:
    """清理文件名中的非法字符"""
    return re.sub(r'[<>:"/\\|?*]', '_', subject)[:40]


def make_mail_filename(msg) -> str:
    """生成邮件文件名"""
    date_str = (msg.received_at or "unknown").replace(":", "-").replace("T", "_").replace("Z", "")[:20]
    subj = clean_subject(msg.subject or "no_subject")
    return f"{date_str}_{subj}.json"


def get_transport():
    """获取带 PolicyKey 的 transport"""
    config = ClientConfig.from_env()
    transport = EasTransport(config)
    # Provision
    resp = transport.post("Provision", build_provision_request())
    pk1 = re.findall(rb'\x03(\d{8,})\x00', resp)[0].decode()
    resp = transport.post("Provision", build_provision_request(policy_key=pk1))
    pk2 = re.findall(rb'\x03(\d{8,})\x00', resp)[-1].decode()
    return transport


def sync_all_messages(transport, inbox_id="14", max_emails=0, download_body=True) -> list:
    """全量同步邮件列表"""
    all_msgs = []
    
    # 第一次同步
    resp = transport.post("Sync", build_sync_request(
        collection_id=inbox_id, sync_key="0", window_size=100,
    ))
    sync1 = parse_sync_response(resp)
    all_msgs.extend(sync1.messages)
    sk = sync1.sync_key
    
    count = len(all_msgs)
    print(f"同步中... 已获取 {count} 封")
    
    # 持续同步
    while sk and sk != "0":
        try:
            resp = transport.post("Sync", build_sync_request(
                collection_id=inbox_id, sync_key=sk, window_size=100,
            ))
            if not resp:
                break
            sync_n = parse_sync_response(resp)
            all_msgs.extend(sync_n.messages)
            count = len(all_msgs)
            
            if max_emails > 0 and count >= max_emails:
                all_msgs = all_msgs[:max_emails]
                break
            
            if len(sync_n.messages) == 0 or sync_n.sync_key == sk:
                break
            sk = sync_n.sync_key
            
            if count % 500 == 0:
                print(f"同步中... 已获取 {count} 封")
        except Exception as e:
            print(f"同步异常: {e}")
            break
    
    print(f"同步完成: 共 {len(all_msgs)} 封")
    return all_msgs


def download_email_body(transport, server_id: str, collection_id="14") -> dict:
    """下载单封邮件的完整内容"""
    try:
        payload = build_item_operations_message_request(
            collection_id=collection_id, server_id=server_id,
        )
        resp = transport.post("ItemOperations", payload)
        result = parse_item_operations_message_response(resp)
        
        body = result.body or ""
        if "<html" in body.lower():
            soup = BeautifulSoup(body, "html.parser")
            text = soup.get_text(separator="\n", strip=True)
        else:
            text = body
        
        return {
            "body_text": text[:10000],  # 限制大小
            "body_html": body[:50000] if "<html" in body.lower() else "",
            "to": getattr(result, "to", ""),
            "cc": getattr(result, "cc", ""),
        }
    except Exception as e:
        return {"body_text": f"(读取失败: {e})", "body_html": "", "to": "", "cc": ""}


def sync_all(max_emails=0, download_body=True):
    """全量下载所有邮件"""
    ensure_dirs()
    transport = get_transport()
    
    # 获取收件箱 ID
    resp = transport.post("FolderSync", build_folder_sync_request(sync_key="0"))
    folders = parse_folder_sync_response(resp)
    inbox_id = "14"
    for f in folders.folders:
        if str(f.folder_type) == "2":
            inbox_id = f.server_id
            break
    
    # 同步所有邮件列表
    all_msgs = sync_all_messages(transport, inbox_id, max_emails)
    
    # 加载索引
    index = load_index()
    # 用 subject+sender+received_at 去重（Exchange server_id不固定）
    existing_keys = set()
    for e in index["emails"].values():
        key = f"{e.get('subject','')}|{e.get('sender','')}|{e.get('received_at','')}"
        existing_keys.add(key)
    
    new_count = 0
    updated_count = 0
    for i, msg in enumerate(all_msgs):
        mid = msg.server_id or f"unknown_{i}"
        
        subject = msg.subject or "(无主题)"
        sender = msg.sender or "(未知)"
        received_at = msg.received_at or ""
        dedup_key = f"{subject}|{sender}|{received_at}"
        
        if dedup_key in existing_keys:
            # 已存在的邮件：更新server_id（可能变了）
            old = index["emails"].get(mid)
            if not old:
                # server_id变了，找旧的记录更新
                for old_mid, old_e in index["emails"].items():
                    old_key = f"{old_e.get('subject','')}|{old_e.get('sender','')}|{old_e.get('received_at','')}"
                    if old_key == dedup_key and old_mid != mid:
                        # server_id变了，迁移记录
                        old_e["server_id"] = mid
                        index["emails"][mid] = old_e
                        del index["emails"][old_mid]
                        updated_count += 1
                        break
            continue
        
        category, folder = get_category(subject)
        filename = make_mail_filename(msg)
        filepath = ARCHIVE_DIR / folder / filename
        
        # 基本信息写入索引
        email_data = {
            "server_id": mid,
            "subject": subject,
            "sender": sender,
            "received_at": received_at,
            "category": category,
            "folder": folder,
            "filename": filename,
            "has_body": False,
        }
        
        # 下载正文
        if download_body:
            if i % 50 == 0 and i > 0:
                print(f"下载正文... {i}/{len(all_msgs)}")
            body_data = download_email_body(transport, mid, inbox_id)
            email_data["has_body"] = bool(body_data.get("body_text"))
            email_data["to"] = body_data.get("to", "")
            email_data["cc"] = body_data.get("cc", "")
            
            # 保存完整邮件到文件
            full_data = {**email_data, **body_data}
            filepath.write_text(
                json.dumps(full_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        
        # 更新索引
        index["emails"][mid] = email_data
        existing_keys.add(dedup_key)
        new_count += 1
    
    if updated_count > 0:
        print(f"server_id更新: {updated_count} 封")
    
    # 更新统计
    index["stats"]["total"] = len(index["emails"])
    index["stats"]["last_sync"] = datetime.now().isoformat()
    
    # 分类统计
    by_cat = {}
    by_sender = {}
    for mid, email in index["emails"].items():
        cat = email.get("category", "其他")
        by_cat[cat] = by_cat.get(cat, 0) + 1
        sender = email.get("sender", "未知")
        # 提取名字
        name_match = re.match(r'"?([^"<\n]+)"?', sender)
        name = name_match.group(1).strip() if name_match else sender[:20]
        by_sender[name] = by_sender.get(name, 0) + 1
    
    index["stats"]["by_category"] = dict(sorted(by_cat.items(), key=lambda x: -x[1]))
    index["stats"]["by_sender"] = dict(sorted(by_sender.items(), key=lambda x: -x[1])[:50])
    
    save_index(index)
    
    # 保存同步状态
    save_state({
        "last_full_sync": datetime.now().isoformat(),
        "total_synced": len(index["emails"]),
    })
    
    print(f"\n完成! 新增 {new_count} 封, 索引共 {len(index['emails'])} 封")
    print(f"分类: {index['stats']['by_category']}")


def sync_incremental():
    """增量同步 - 只下载新邮件
    注意: Exchange Server的server_id是动态分配的，不能用于去重。
    使用 subject+sender+received_at 三元组判断邮件是否已存在。
    """
    ensure_dirs()
    index = load_index()
    
    # 用 subject+sender+received_at 去重（server_id不固定）
    existing_keys = set()
    for e in index["emails"].values():
        key = f"{e.get('subject','')}|{e.get('sender','')}|{e.get('received_at','')}"
        existing_keys.add(key)
    
    transport = get_transport()
    
    # 同步最新邮件
    all_msgs = sync_all_messages(transport, "14", max_emails=200)
    
    new_count = 0
    for msg in all_msgs:
        mid = msg.server_id or ""
        if not mid:
            continue
        
        subject = msg.subject or "(无主题)"
        sender = msg.sender or "(未知)"
        received_at = msg.received_at or ""
        dedup_key = f"{subject}|{sender}|{received_at}"
        
        if dedup_key in existing_keys:
            continue
        
        category, folder = get_category(subject)
        filename = make_mail_filename(msg)
        
        email_data = {
            "server_id": mid,
            "subject": subject,
            "sender": msg.sender or "(未知)",
            "received_at": msg.received_at or "",
            "category": category,
            "folder": folder,
            "filename": filename,
            "has_body": False,
        }
        
        # 下载正文
        body_data = download_email_body(transport, mid)
        email_data["has_body"] = bool(body_data.get("body_text"))
        email_data["to"] = body_data.get("to", "")
        email_data["cc"] = body_data.get("cc", "")
        
        # 保存完整邮件
        filepath = ARCHIVE_DIR / folder / filename
        full_data = {**email_data, **body_data}
        filepath.write_text(
            json.dumps(full_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        
        index["emails"][mid] = email_data
        existing_keys.add(dedup_key)
        new_count += 1
        print(f"新邮件: [{category}] {subject[:50]}")
    
    if new_count > 0:
        # 更新统计
        index["stats"]["total"] = len(index["emails"])
        index["stats"]["last_sync"] = datetime.now().isoformat()
        
        by_cat = {}
        by_sender = {}
        for mid, email in index["emails"].items():
            cat = email.get("category", "其他")
            by_cat[cat] = by_cat.get(cat, 0) + 1
            sender = email.get("sender", "未知")
            name_match = re.match(r'"?([^"<\n]+)"?', sender)
            name = name_match.group(1).strip() if name_match else sender[:20]
            by_sender[name] = by_sender.get(name, 0) + 1
        
        index["stats"]["by_category"] = dict(sorted(by_cat.items(), key=lambda x: -x[1]))
        index["stats"]["by_sender"] = dict(sorted(by_sender.items(), key=lambda x: -x[1])[:50])
        
        save_index(index)
        print(f"\n增量同步完成: {new_count} 封新邮件")
    else:
        print("无新邮件")
    
    return new_count


def generate_report(index: dict, report_type: str = "daily", date_str: str = None):
    """生成汇总报告"""
    now = datetime.now()
    
    if date_str:
        base_date = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        base_date = now
    
    # 确定时间范围
    if report_type == "daily":
        start = base_date.replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=1)
    elif report_type == "weekly":
        start = base_date - timedelta(days=base_date.weekday())
        start = start.replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=7)
    elif report_type == "monthly":
        start = base_date.replace(day=1, hour=0, minute=0, second=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
    else:
        start = base_date.replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=1)
    
    # 筛选时间段内的邮件
    period_emails = []
    for mid, email in index["emails"].items():
        received = email.get("received_at", "")
        if not received:
            continue
        try:
            dt = datetime.fromisoformat(received.replace("Z", "+00:00")).replace(tzinfo=None)
            if start <= dt < end:
                period_emails.append(email)
        except (ValueError, TypeError):
            continue
    
    # 统计
    categories = {}
    senders = {}
    for email in period_emails:
        cat = email.get("category", "其他")
        categories[cat] = categories.get(cat, 0) + 1
        sender = email.get("sender", "未知")
        name_match = re.match(r'"?([^"<\n]+)"?', sender)
        name = name_match.group(1).strip() if name_match else sender
        senders[name] = senders.get(name, 0) + 1
    
    date_label = start.strftime("%Y-%m-%d")
    report = {
        "report_type": report_type,
        "period": {
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
        },
        "generated_at": datetime.now().isoformat(),
        "total_emails": len(period_emails),
        "categories": dict(sorted(categories.items(), key=lambda x: -x[1])),
        "top_senders": dict(sorted(senders.items(), key=lambda x: -x[1])[:20]),
        "emails": sorted(period_emails, key=lambda x: x.get("received_at", ""), reverse=True),
    }
    
    # 保存报告
    report_file = ARCHIVE_DIR / "reports" / f"{report_type}_{date_label}.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    
    return report


def search_emails(index: dict, query: str) -> list:
    """搜索邮件"""
    results = []
    q = query.lower()
    for mid, email in index["emails"].items():
        if (q in (email.get("subject", "")).lower() or
            q in (email.get("sender", "")).lower() or
            q in (email.get("category", "")).lower()):
            results.append(email)
    return sorted(results, key=lambda x: x.get("received_at", ""), reverse=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EAS 邮件管理器")
    parser.add_argument("action", choices=[
        "sync-all", "sync-incremental", "report", "stats", "search"
    ])
    parser.add_argument("--max", type=int, default=0, help="最大下载数量 (0=全部)")
    parser.add_argument("--no-body", action="store_true", help="不下载正文（仅索引）")
    parser.add_argument("--type", default="daily", help="报告类型: daily/weekly/monthly")
    parser.add_argument("--date", default=None, help="日期 YYYY-MM-DD")
    parser.add_argument("--query", default=None, help="搜索关键词")
    
    args = parser.parse_args()
    
    if args.action == "sync-all":
        sync_all(max_emails=args.max, download_body=not args.no_body)
    elif args.action == "sync-incremental":
        sync_incremental()
    elif args.action == "report":
        index = load_index()
        report = generate_report(index, args.type, args.date)
        print(f"报告: {report['period']['start']} ~ {report['period']['end']}")
        print(f"邮件数: {report['total_emails']}")
        print(f"分类: {report['categories']}")
    elif args.action == "stats":
        index = load_index()
        print(f"总邮件: {index['stats']['total']}")
        print(f"最后同步: {index['stats']['last_sync']}")
        print(f"分类: {json.dumps(index['stats']['by_category'], ensure_ascii=False, indent=2)}")
        print(f"Top发件人: {json.dumps(index['stats']['by_sender'], ensure_ascii=False, indent=2)}")
    elif args.action == "search":
        if not args.query:
            print("请提供 --query 参数")
            sys.exit(1)
        index = load_index()
        results = search_emails(index, args.query)
        print(f"找到 {len(results)} 封邮件:")
        for r in results[:20]:
            print(f"  [{r.get('received_at', '')[:10]}] {r.get('subject', '')[:60]}")
            print(f"    {r.get('sender', '')[:30]} | {r.get('category', '')}")
