#!/usr/bin/env python3
"""通过 EAS 发送邮件 - 支持 HTML 模板、附件、抄送。"""

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
    html_body: str,
    text_body: str,
    cc_email: str | None,
    attachment_paths: list[str] | None,
):
    """构建 multipart/alternative + 附件的 MIME 消息"""
    attachments = attachment_paths or []

    # 创建 multipart/mixed 容器（邮件整体）
    message = MIMEMultipart("mixed")
    message["From"] = from_email
    message["To"] = to_email
    if cc_email:
        message["Cc"] = cc_email
    message["Subject"] = subject

    # 创建 multipart/alternative 容器（HTML + 纯文本）
    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(text_body, "plain", "utf-8"))
    alt_part.attach(MIMEText(html_body, "html", "utf-8"))
    message.attach(alt_part)

    # 添加附件
    for raw_path in attachments:
        file_path = Path(raw_path)
        payload = file_path.read_bytes()
        mime_type, _ = mimetypes.guess_type(str(file_path))
        subtype = (mime_type or "application/octet-stream").split("/")[-1]
        part = MIMEApplication(payload, _subtype=subtype)
        part.add_header("Content-Disposition", "attachment", filename=file_path.name)
        message.attach(part)

    return message


def send_mail(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    cc_email: str | None = None,
    attachment_paths: list[str] | None = None,
) -> dict:
    config = ClientConfig.from_env()
    transport = EasTransport(config)
    policy_key = get_policy_key(transport)

    from_email = config.account_email or f"{config.username}@unknown.local"
    message = build_message(from_email, to_email, subject, html_body, text_body, cc_email, attachment_paths)

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
    from mail_templates import list_templates, render_template, TEMPLATES

    parser = argparse.ArgumentParser(description="通过 EAS 发送邮件（支持 HTML 模板）")
    parser.add_argument("--to", default=None, help="收件人邮箱")
    parser.add_argument("--subject", default=None, help="邮件主题")
    parser.add_argument("--body", default=None, help="邮件正文（支持换行符 \\n）")
    parser.add_argument("--cc", default=None, help="抄送邮箱")
    parser.add_argument("--attach", action="append", default=[], help="附件路径，可重复传入")

    # 模板相关参数
    parser.add_argument("--template", default="simple", choices=list(TEMPLATES.keys()),
                        help="邮件模板类型")
    parser.add_argument("--title", default="", help="模板标题（默认使用 --subject）")
    parser.add_argument("--recipient-name", default="", help="收件人称呼")
    parser.add_argument("--sender-name", default="", help="发件人署名")
    parser.add_argument("--subtitle", default="", help="副标题")
    parser.add_argument("--highlight", default="", help="高亮提示内容")
    parser.add_argument("--detail-rows", default="", help="表格行 HTML（仅 project/finance 模板）")
    parser.add_argument("--list-templates", action="store_true", help="列出可用模板并退出")

    args = parser.parse_args()

    if args.list_templates:
        for t in list_templates():
            print(f"\n【{t['name']}】{t['description']}")
            print(f"  主题前缀: {t['subject_prefix'] or '(无)'}")
        return

    if not args.to or not args.subject or not args.body:
        parser.error("发送邮件时必须提供 --to、--subject、--body")

    # 将命令行中字面的 \n 转换为真正的换行符（所有文本参数统一处理）
    def _fix_nl(s: str) -> str:
        return s.replace("\\n", "\n") if s else s

    body = _fix_nl(args.body)
    highlight = _fix_nl(args.highlight)
    subtitle = _fix_nl(args.subtitle)
    title = _fix_nl(args.title)
    detail_rows = _fix_nl(args.detail_rows)
    recipient_name = _fix_nl(args.recipient_name)
    sender_name = _fix_nl(args.sender_name)

    tmpl = TEMPLATES.get(args.template, TEMPLATES["simple"])
    subject = tmpl.subject_prefix + args.subject
    title = title or args.subject

    html_body, text_body = render_template(
        template_name=args.template,
        title=title,
        content=body,
        sender_name=sender_name,
        recipient_name=recipient_name,
        subtitle=subtitle,
        highlight=highlight,
        detail_rows=detail_rows,
    )

    result = send_mail(args.to, subject, html_body, text_body, args.cc, args.attach)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
