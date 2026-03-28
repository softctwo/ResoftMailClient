#!/usr/bin/env python3
"""EAS 邮件守护进程 - 实时监听新邮件并推送飞书通知"""

import json
import os
import sys
import time
import signal
import warnings
warnings.filterwarnings('ignore')
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
from eas_client.eas.commands import build_folder_sync_request, build_sync_request, build_ping_request
from eas_client.eas.parsers import parse_folder_sync_response, parse_sync_response, parse_ping_response
from eas_client.transport import EasTransport

# 飞书通知配置
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")

# 状态文件
STATE_FILE = Path(__file__).parent / "daemon_state.json"
SEEN_FILE = Path(__file__).parent / "last_seen_ids.txt"

# 运行标志
running = True


def signal_handler(sig, frame):
    global running
    print(f"\n[daemon] 收到信号 {sig}，正在停止...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def load_seen_ids():
    seen = set()
    if SEEN_FILE.exists():
        for line in SEEN_FILE.read_text().splitlines():
            line = line.strip()
            if line:
                seen.add(line)
    return seen


def save_seen_ids(current_ids):
    SEEN_FILE.write_text("\n".join(sorted(current_ids)))


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except:
            pass
    return {"sync_key": "0", "inbox_id": None, "last_check": 0}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_inbox_id(transport):
    """获取收件箱 ID"""
    resp = transport.post("FolderSync", build_folder_sync_request(sync_key="0"))
    folders = parse_folder_sync_response(resp)

    for f in folders.folders:
        if str(f.folder_type) == "2":
            return f.server_id
    for f in folders.folders:
        if "收件箱" in (f.display_name or ""):
            return f.server_id
    return None


def ping_loop(transport, inbox_id, heartbeat=600):
    """Ping 等待新邮件。返回 True 表示有变化，False 表示超时无变化。"""
    try:
        payload = build_ping_request(
            folder_ids=[inbox_id],
            heartbeat_interval=heartbeat,
        )
        resp = transport.post("Ping", payload)
        result = parse_ping_response(resp)
        status = result.get("status", "")

        if status == "2":
            # Changes detected
            print(f"[daemon] Ping 检测到变化！文件夹: {result.get('folders', [])}")
            return True
        elif status == "5":
            # Heartbeat interval expired, no changes
            return False
        elif status == "1":
            # Heartbeat interval too long or too short
            print(f"[daemon] Ping 状态 1，调整 heartbeat...")
            return False
        else:
            print(f"[daemon] Ping 响应: status={status}")
            return status == "2"
    except Exception as e:
        print(f"[daemon] Ping 错误: {e}")
        return False


def sync_new_messages(transport, inbox_id, state):
    """同步新邮件"""
    sync_key = state.get("sync_key", "0")

    resp = transport.post("Sync", build_sync_request(
        collection_id=inbox_id,
        sync_key=sync_key,
        window_size=10,
    ))
    sync_result = parse_sync_response(resp)
    messages = list(sync_result.messages)

    # 如果是初始同步，再做一次
    if sync_result.sync_key and sync_result.sync_key != "0" and sync_key == "0":
        resp = transport.post("Sync", build_sync_request(
            collection_id=inbox_id,
            sync_key=sync_result.sync_key,
            window_size=10,
        ))
        sync_result = parse_sync_response(resp)
        messages = list(sync_result.messages)

    # 更新 sync_key
    state["sync_key"] = sync_result.sync_key
    save_state(state)

    return messages


def notify_feishu(new_messages):
    """通过 OpenClaw 飞书通知新邮件"""
    if not new_messages:
        return

    # 构建通知内容
    lines = []
    for msg in new_messages:
        subject = msg.subject or "(无主题)"
        sender = msg.sender or "(未知)"
        ts = msg.received_at or ""
        lines.append(f"• {subject}\n  来自: {sender}\n  时间: {ts}")

    content = "\n".join(lines)
    print(f"[daemon] 通知内容:\n{content}")

    # 使用 openclaw CLI 发送飞书消息
    import subprocess
    try:
        result = subprocess.run(
            ["openclaw", "message", "send",
             "--channel", "feishu",
             "--target", "user:ou_693a42207411c4bd0c849b6b499cc46b",
             "--message", f"📧 新邮件通知 ({len(new_messages)}封)\n\n{content}"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f"[daemon] 飞书通知已发送")
        else:
            print(f"[daemon] 飞书通知失败: {result.stderr}")
    except Exception as e:
        print(f"[daemon] 飞书通知异常: {e}")


def main():
    global running

    print("=" * 50)
    print("EAS 邮件守护进程启动")
    print("=" * 50)

    config = ClientConfig.from_env()
    transport = EasTransport(config)

    # 加载状态
    state = load_state()

    # 获取收件箱 ID
    if not state.get("inbox_id"):
        print("[daemon] 获取收件箱 ID...")
        inbox_id = get_inbox_id(transport)
        if not inbox_id:
            print("[daemon] 错误: 未找到收件箱")
            sys.exit(1)
        state["inbox_id"] = inbox_id
        save_state(state)
        print(f"[daemon] 收件箱 ID: {inbox_id}")
    else:
        inbox_id = state["inbox_id"]

    seen = load_seen_ids()
    print(f"[daemon] 已知邮件数: {len(seen)}")
    print(f"[daemon] 开始 Ping 监听 (heartbeat=600秒)...")
    print()

    cycle = 0
    while running:
        cycle += 1
        try:
            # Ping 等待新邮件
            has_changes = ping_loop(transport, inbox_id, heartbeat=600)

            if not running:
                break

            if has_changes:
                print(f"[daemon] === 检测到新邮件 (周期 #{cycle}) ===")

                # 同步拉取新邮件
                messages = sync_new_messages(transport, inbox_id, state)

                # 找出新邮件
                current_ids = set()
                new_msgs = []
                for msg in messages:
                    mid = msg.server_id or ""
                    current_ids.add(mid)
                    if mid not in seen:
                        new_msgs.append(msg)

                # 更新缓存
                save_seen_ids(current_ids)
                seen = current_ids

                if new_msgs:
                    print(f"[daemon] 发现 {len(new_msgs)} 封新邮件")
                    notify_feishu(new_msgs)
                else:
                    print(f"[daemon] Ping 检测到变化但无新邮件（可能是已读/删除等操作）")

            else:
                print(f"[daemon] Ping 超时，无变化 (周期 #{cycle}) [{time.strftime('%H:%M:%S')}]")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[daemon] 错误: {e}")
            print(f"[daemon] 30秒后重试...")
            time.sleep(30)

    print("\n[daemon] 守护进程已停止")


if __name__ == "__main__":
    main()
