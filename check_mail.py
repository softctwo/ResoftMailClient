#!/usr/bin/env python3
"""EAS 邮件检查脚本 - 检测新邮件并输出 JSON"""

import json
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from eas_env import add_import_path, load_env
from time_utils import to_beijing_time

load_env()
add_import_path()

from eas_client.config import ClientConfig
from eas_client.eas.commands import build_folder_sync_request, build_sync_request
from eas_client.eas.parsers import parse_folder_sync_response, parse_sync_response
from eas_client.transport import EasTransport


def main():
    config = ClientConfig.from_env()
    transport = EasTransport(config)

    # 查找收件箱
    resp = transport.post("FolderSync", build_folder_sync_request(sync_key="0"))
    folders = parse_folder_sync_response(resp)

    inbox_id = None
    for f in folders.folders:
        if str(f.folder_type) == "2":
            inbox_id = f.server_id
            break
    if not inbox_id:
        for f in folders.folders:
            if "收件箱" in (f.display_name or ""):
                inbox_id = f.server_id
                break

    if not inbox_id:
        print(json.dumps({"error": "未找到收件箱"}, ensure_ascii=False))
        return

    # 同步最新邮件
    resp = transport.post("Sync", build_sync_request(
        collection_id=inbox_id, sync_key="0", window_size=10,
    ))
    sync1 = parse_sync_response(resp)

    messages = list(sync1.messages)
    if sync1.sync_key and sync1.sync_key != "0":
        resp = transport.post("Sync", build_sync_request(
            collection_id=inbox_id, sync_key=sync1.sync_key, window_size=10,
        ))
        sync2 = parse_sync_response(resp)
        messages = list(sync2.messages)

    # 读取缓存
    cache_file = Path(__file__).parent / "last_seen_ids.txt"
    seen = set()
    if cache_file.exists():
        for line in cache_file.read_text().splitlines():
            line = line.strip()
            if line:
                seen.add(line)

    # 找出新邮件
    current_ids = set()
    new_msgs = []
    for msg in messages:
        mid = msg.server_id or ""
        current_ids.add(mid)
        if mid not in seen:
            new_msgs.append({
                "server_id": mid,
                "subject": msg.subject or "(无主题)",
                "sender": msg.sender or "(未知)",
                "received_at": to_beijing_time(msg.received_at),
                "received_at_raw": msg.received_at or "",
            })

    # 更新缓存
    cache_file.write_text("\n".join(sorted(current_ids)))

    output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(messages),
        "new_count": len(new_msgs),
        "new_messages": new_msgs,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)
