#!/usr/bin/env python3
"""EAS 邮件守护进程 - 每 10 分钟轮询新邮件并输出通知。"""

from __future__ import annotations

import json
import signal
import subprocess
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from mail_assistant import load_messages, run_poll

STATE_FILE = Path(__file__).parent / "daemon_state.json"
running = True


def signal_handler(sig, frame):
    global running
    print(f"\n[daemon] 收到信号 {sig}，正在停止...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def notify_feishu(new_messages: list[dict]) -> None:
    if not new_messages:
        return

    lines = []
    for msg in new_messages[:10]:
        lines.append(
            f"• [{msg.get('category', '其他')}] {msg.get('subject', '(无主题)')}\n"
            f"  来自: {msg.get('sender', '(未知)')}\n"
            f"  时间: {msg.get('received_at', '')}（北京时间）"
        )

    content = "\n".join(lines)
    print(f"[daemon] 通知内容:\n{content}")

    try:
        result = subprocess.run(
            [
                "openclaw",
                "message",
                "send",
                "--channel",
                "feishu",
                "--message",
                f"📧 新邮件通知 ({len(new_messages)}封)\n\n{content}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print("[daemon] 飞书通知已发送")
        else:
            print(f"[daemon] 飞书通知失败: {result.stderr}")
    except Exception as exc:
        print(f"[daemon] 飞书通知异常: {exc}")


def main() -> None:
    global running

    state = load_state()
    interval_seconds = int(state.get("interval_seconds", 600))

    print("=" * 50)
    print("EAS 邮件守护进程启动")
    print("=" * 50)
    print(f"[daemon] 已知邮件数: {len(load_messages())}")
    print(f"[daemon] 开始轮询监听 (每 {interval_seconds} 秒一次)...")
    print()

    cycle = 0
    while running:
        cycle += 1
        try:
            result = run_poll(limit=30)
            state["last_check"] = time.time()
            state["interval_seconds"] = interval_seconds
            save_state(state)

            if result["new_count"] > 0:
                print(f"[daemon] === 检测到新邮件 (周期 #{cycle}) ===")
                print(f"[daemon] 发现 {result['new_count']} 封新邮件")
                notify_feishu(result["new_messages"])
            else:
                print(f"[daemon] 无新邮件 (周期 #{cycle}) [{time.strftime('%H:%M:%S')}]")

            for _ in range(interval_seconds):
                if not running:
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"[daemon] 错误: {exc}")
            print("[daemon] 30秒后重试...")
            time.sleep(30)

    print("[daemon] 已停止")


if __name__ == "__main__":
    main()
