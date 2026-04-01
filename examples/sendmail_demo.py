#!/usr/bin/env python3
"""EAS SendMail 示例 - 通过 EAS 协议发送邮件"""

import os
import sys
import warnings
warnings.filterwarnings('ignore')
from pathlib import Path
from email.mime.text import MIMEText
import base64
import requests
from urllib.parse import urlencode

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
from eas_client.eas.commands import build_provision_request
from eas_client.transport import EasTransport
import re


def send_email(to, subject, body, cc=None, save_in_sent=True):
    """通过 EAS 协议发送邮件

    Args:
        to: 收件人邮箱
        subject: 邮件主题
        body: 邮件正文
        cc: 抄送（可选）
        save_in_sent: 是否保存到已发送文件夹

    Returns:
        bool: 发送是否成功
    """
    config = ClientConfig.from_env()
    transport = EasTransport(config)

    # 获取 PolicyKey
    resp = transport.post("Provision", build_provision_request())
    pk1 = re.findall(rb'\x03(\d{8,})\x00', resp)[0].decode()
    resp = transport.post("Provision", build_provision_request(policy_key=pk1))
    pk2 = re.findall(rb'\x03(\d{8,})\x00', resp)[-1].decode()

    # 构造 MIME 邮件
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = config.account_email
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc

    # 发送（用 EAS 12.1 协议 + MIME 格式）
    auth = f'Basic {base64.b64encode(f"{config.username}:{config.password}".encode()).decode()}'

    params = {
        "Cmd": "SendMail",
        "User": config.account_email,
        "DeviceId": config.device_id,
        "DeviceType": config.device_type,
    }
    if save_in_sent:
        params["SaveInSentItems"] = "T"

    query = urlencode(params)
    url = f'{config.base_url}?{query}'

    headers = {
        "Authorization": auth,
        "MS-ASProtocolVersion": "12.1",
        "Content-Type": "message/rfc822",
        "User-Agent": config.user_agent,
        "X-MS-PolicyKey": pk2,
    }

    resp = requests.post(
        url, data=msg.as_bytes(), headers=headers,
        timeout=30, verify=config.verify_tls,
    )

    return resp.status_code == 200


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法: python sendmail_demo.py <收件人> <主题> <正文>")
        print("示例: python sendmail_demo.py user@example.com '测试' '你好'")
        sys.exit(1)

    to = sys.argv[1]
    subject = sys.argv[2]
    body = sys.argv[3]

    print(f"发送邮件到 {to}...")
    print(f"  主题: {subject}")

    if send_email(to, subject, body):
        print("✅ 发送成功！")
    else:
        print("❌ 发送失败")
