#!/usr/bin/env python3
"""通过 EAS 发送邮件。"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import urlencode

import requests

from eas_env import add_import_path, load_env

load_env()
add_import_path()

from eas_client.config import ClientConfig
from eas_client.eas.commands import build_provision_request
from eas_client.transport import EasTransport


def get_policy_key(transport: EasTransport) -> str:
    resp1 = transport.post("Provision", build_provision_request())
    keys1 = re.findall(rb"\x03(\d{8,})\x00", resp1)
    if not keys1:
        raise RuntimeError("Provision 第一步未返回 PolicyKey")

    resp2 = transport.post("Provision", build_provision_request(policy_key=keys1[0].decode()))
    keys2 = re.findall(rb"\x03(\d{8,})\x00", resp2)
    if not keys2:
        raise RuntimeError("Provision 第二步未返回 PolicyKey")

    return keys2[-1].decode()


def build_message(
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
    cc_email: str | None,
    attachment_paths: list[str] | None,
):
    attachments = attachment_paths or []
    if attachments:
        message = MIMEMultipart()
        message.attach(MIMEText(body, "plain", "utf-8"))
        for raw_path in attachments:
            file_path = Path(raw_path)
            payload = file_path.read_bytes()
            mime_type, _ = mimetypes.guess_type(str(file_path))
            subtype = (mime_type or "application/octet-stream").split("/")[-1]
            part = MIMEApplication(payload, _subtype=subtype)
            part.add_header("Content-Disposition", "attachment", filename=file_path.name)
            message.attach(part)
    else:
        message = MIMEText(body, "plain", "utf-8")

    message["From"] = from_email
    message["To"] = to_email
    if cc_email:
        message["Cc"] = cc_email
    message["Subject"] = subject
    return message


def send_mail(
    to_email: str,
    subject: str,
    body: str,
    cc_email: str | None = None,
    attachment_paths: list[str] | None = None,
) -> dict:
    config = ClientConfig.from_env()
    transport = EasTransport(config)
    policy_key = get_policy_key(transport)

    from_email = config.account_email or f"{config.username}@unknown.local"
    message = build_message(from_email, to_email, subject, body, cc_email, attachment_paths)

    params = {
        "Cmd": "SendMail",
        "User": config.account_email or config.username,
        "DeviceId": config.device_id,
        "DeviceType": config.device_type,
        "SaveInSentItems": "T",
    }
    url = f"{config.base_url}?{urlencode(params)}"
    auth = "Basic " + base64.b64encode(f"{config.username}:{config.password}".encode()).decode()
    headers = {
        "Authorization": auth,
        "MS-ASProtocolVersion": "12.1",
        "Content-Type": "message/rfc822",
        "User-Agent": config.user_agent,
        "X-MS-PolicyKey": policy_key,
    }

    response = requests.post(
        url,
        data=message.as_bytes(),
        headers=headers,
        timeout=30,
        verify=config.verify_tls,
    )
    response.raise_for_status()

    return {
        "status_code": response.status_code,
        "subject": subject,
        "to": to_email,
        "cc": cc_email,
        "attachments": attachment_paths or [],
        "sent_at": int(time.time()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="通过 EAS 发送邮件")
    parser.add_argument("--to", required=True, help="收件人邮箱")
    parser.add_argument("--subject", required=True, help="邮件主题")
    parser.add_argument("--body", required=True, help="邮件正文")
    parser.add_argument("--cc", default=None, help="抄送邮箱")
    parser.add_argument("--attach", action="append", default=[], help="附件路径，可重复传入")
    args = parser.parse_args()

    result = send_mail(args.to, args.subject, args.body, args.cc, args.attach)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
