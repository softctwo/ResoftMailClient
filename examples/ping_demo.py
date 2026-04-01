#!/usr/bin/env python3
"""EAS Ping 实时推送示例 - 监听新邮件"""

import os
import sys
import time
import warnings
warnings.filterwarnings('ignore')
from pathlib import Path

# 加载环境变量
env_file = Path(__file__).parent.parent / ".env.eas"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eas_client.config import ClientConfig
from eas_client.eas.commands import (
    build_provision_request,
    build_folder_sync_request,
    build_sync_request,
    build_ping_request,
)
from eas_client.eas.parsers import (
    parse_folder_sync_response,
    parse_sync_response,
)
from eas_client.transport import EasTransport
import re


def get_policy_key(transport):
    """完成 Provision 握手，获取 PolicyKey"""
    resp = transport.post("Provision", build_provision_request())
    pk1 = re.findall(rb'\x03(\d{8,})\x00', resp)[0].decode()
    resp = transport.post("Provision", build_provision_request(policy_key=pk1))
    pks = re.findall(rb'\x03(\d{8,})\x00', resp)
    return pks[-1].decode()


def parse_wbxml_status(data):
    """从 WBXML 响应中提取状态文本"""
    body = data[4:]
    texts = []
    pos = 0
    while pos < len(body):
        b = body[pos]
        if b == 0x00:
            pos += 2
        elif b == 0x01:
            pos += 1
        elif b == 0x03:
            pos += 1
            end = body.index(0x00, pos)
            texts.append(body[pos:end].decode())
            pos = end + 1
        else:
            pos += 1
    return texts


def main():
    print("EAS Ping 实时推送示例")
    print("=" * 40)

    config = ClientConfig.from_env()
    transport = EasTransport(config)

    # 1. Provision
    print("1. 获取 PolicyKey...")
    pk = get_policy_key(transport)
    print(f"   PolicyKey: {pk}")

    # 2. 用带 PolicyKey 的 config
    config2 = ClientConfig(
        server=config.server, username=config.username,
        password=config.password, account_email=config.account_email,
        policy_key=pk, device_id=config.device_id,
        device_type=config.device_type, user_agent=config.user_agent,
        protocol_version=config.protocol_version,
        timeout=120, verify_tls=config.verify_tls,
    )
    transport = EasTransport(config2)

    # 3. FolderSync
    print("2. 同步文件夹...")
    resp = transport.post("FolderSync", build_folder_sync_request(sync_key="0"))
    folders = parse_folder_sync_response(resp)
    inbox_id = None
    for f in folders.folders:
        if str(f.folder_type) == "2":
            inbox_id = f.server_id
    print(f"   收件箱: {inbox_id}")

    # 4. Sync
    print("3. 初始同步...")
    resp = transport.post("Sync", build_sync_request(
        collection_id=inbox_id, sync_key="0", window_size=5,
    ))
    sync1 = parse_sync_response(resp)
    if sync1.sync_key and sync1.sync_key != "0":
        transport.post("Sync", build_sync_request(
            collection_id=inbox_id, sync_key=sync1.sync_key, window_size=5,
        ))
    print("   完成")

    # 5. Ping 循环
    print("4. 开始 Ping 监听...")
    heartbeat = 120
    try:
        while True:
            payload = build_ping_request([inbox_id], heartbeat_interval=heartbeat)
            start = time.time()
            resp = transport.post("Ping", payload)
            elapsed = time.time() - start
            texts = parse_wbxml_status(resp)
            status = texts[0] if texts else "?"

            if status == "1":
                print(f"   [{time.strftime('%H:%M:%S')}] 心跳超时，无变化 ({elapsed:.0f}s)")
            elif status == "2":
                print(f"   [{time.strftime('%H:%M:%S')}] ✅ 检测到新邮件！")
            elif status == "5":
                server_hb = int(texts[1]) if len(texts) > 1 and texts[1].isdigit() else 600
                print(f"   心跳调整: {heartbeat} → {server_hb}")
                heartbeat = server_hb
            else:
                print(f"   状态: {status}")
    except KeyboardInterrupt:
        print("\n停止监听")


if __name__ == "__main__":
    main()
