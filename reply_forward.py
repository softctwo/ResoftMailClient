#!/usr/bin/env python3
"""邮件回复与转发 - 支持引用原文、常用模板、HTML 美化。"""

from __future__ import annotations

import argparse
import base64
import json
import re
import time
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


def get_transport_with_policy() -> tuple[EasTransport, str]:
    config = ClientConfig.from_env()
    transport = EasTransport(config)
    policy_key = get_policy_key(transport)
    transport.config = ClientConfig(
        **{k: getattr(config, k) for k in [
            "server", "username", "password", "account_email", "device_id",
            "device_type", "user_agent", "protocol_version", "endpoint_path",
            "ews_endpoint_path", "use_tls", "verify_tls", "timeout"
        ]},
        policy_key=policy_key,
    )
    return transport, policy_key


def build_reply_message(
    from_email: str,
    to_email: str,
    original_subject: str,
    original_body: str,
    original_sender: str,
    original_date: str,
    reply_body: str,
    cc_email: str | None = None,
    use_html: bool = False,
) -> MIMEMultipart:
    """构建回复邮件 MIME"""
    message = MIMEMultipart("alternative")
    message["From"] = from_email
    message["To"] = to_email
    if cc_email:
        message["Cc"] = cc_email

    subject = original_subject
    if not subject.startswith("Re:"):
        subject = f"Re: {subject}"
    message["Subject"] = subject

    text_body = f"{reply_body}\n\n--- 原始邮件 ---\n发件人: {original_sender}\n时间: {original_date}\n主题: {original_subject}\n\n{original_body[:2000]}"
    message.attach(MIMEText(text_body, "plain", "utf-8"))

    if use_html:
        html_reply = reply_body.replace("\n", "<br>\n")
        html_body = f"""
        <div style="font-family: 'PingFang SC','Microsoft YaHei',Arial,sans-serif; color: #2c3e50; font-size: 14px; line-height: 1.8;">
            {html_reply}
            <div style="margin: 24px 0; border-top: 1px solid #d5dbdb; padding-top: 16px; color: #7f8c8d; font-size: 12px;">
                <div><strong>原始邮件</strong></div>
                <div>发件人: {original_sender}</div>
                <div>时间: {original_date}</div>
                <div>主题: {original_subject}</div>
            </div>
            <div style="color: #95a5a6; font-size: 12px; border-top: 1px solid #ecf0f1; padding-top: 12px;">
                {original_body[:1000].replace(chr(10), '<br>')}
            </div>
        </div>
        """
        message.attach(MIMEText(html_body, "html", "utf-8"))

    return message


def build_forward_message(
    from_email: str,
    to_email: str,
    original_subject: str,
    original_body: str,
    original_sender: str,
    original_date: str,
    forward_note: str = "",
    cc_email: str | None = None,
    use_html: bool = False,
) -> MIMEMultipart:
    """构建转发邮件 MIME"""
    message = MIMEMultipart("alternative")
    message["From"] = from_email
    message["To"] = to_email
    if cc_email:
        message["Cc"] = cc_email

    subject = original_subject
    if not subject.startswith("Fw:") and not subject.startswith("Fwd:"):
        subject = f"Fw: {subject}"
    message["Subject"] = subject

    note = forward_note or ""
    text_body = (
        f"{note}\n\n"
        f"--- 转发邮件 ---\n"
        f"发件人: {original_sender}\n"
        f"时间: {original_date}\n"
        f"主题: {original_subject}\n\n"
        f"{original_body[:3000]}"
    )
    message.attach(MIMEText(text_body, "plain", "utf-8"))

    if use_html:
        html_note = note.replace("\n", "<br>\n")
        html_body = f"""
        <div style="font-family: 'PingFang SC','Microsoft YaHei',Arial,sans-serif; color: #2c3e50; font-size: 14px; line-height: 1.8;">
            {html_note}
            <div style="margin: 20px 0; border: 1px solid #d5dbdb; border-radius: 6px; padding: 20px; background: #f8f9fa;">
                <div style="font-weight: 600; color: #1a5276; margin-bottom: 12px;">转发邮件</div>
                <div style="font-size: 12px; color: #7f8c8d; margin-bottom: 8px;">
                    <div>发件人: {original_sender}</div>
                    <div>时间: {original_date}</div>
                    <div>主题: {original_subject}</div>
                </div>
                <div style="border-top: 1px solid #ecf0f1; padding-top: 12px; color: #566573; font-size: 13px;">
                    {original_body[:1500].replace(chr(10), '<br>')}
                </div>
            </div>
        </div>
        """
        message.attach(MIMEText(html_body, "html", "utf-8"))

    return message


def send_raw_mail(message, policy_key: str, save_in_sent: bool = True) -> dict:
    config = ClientConfig.from_env()
    from_email = config.account_email or f"{config.username}@unknown.local"
    if not message["From"]:
        message["From"] = from_email

    params = {
        "Cmd": "SendMail",
        "User": config.account_email or config.username,
        "DeviceId": config.device_id,
        "DeviceType": config.device_type,
    }
    if save_in_sent:
        params["SaveInSentItems"] = "T"

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
        "subject": message["Subject"],
        "to": message["To"],
        "cc": message.get("Cc"),
        "sent_at": int(time.time()),
    }


def reply_to_email(
    to_email: str,
    original_subject: str,
    original_body: str,
    original_sender: str,
    original_date: str,
    reply_body: str,
    cc_email: str | None = None,
    use_html: bool = False,
) -> dict:
    transport, policy_key = get_transport_with_policy()
    config = ClientConfig.from_env()
    from_email = config.account_email or f"{config.username}@unknown.local"
    message = build_reply_message(
        from_email, to_email, original_subject, original_body,
        original_sender, original_date, reply_body, cc_email, use_html,
    )
    return send_raw_mail(message, policy_key)


def forward_email(
    to_email: str,
    original_subject: str,
    original_body: str,
    original_sender: str,
    original_date: str,
    forward_note: str = "",
    cc_email: str | None = None,
    use_html: bool = False,
) -> dict:
    transport, policy_key = get_transport_with_policy()
    config = ClientConfig.from_env()
    from_email = config.account_email or f"{config.username}@unknown.local"
    message = build_forward_message(
        from_email, to_email, original_subject, original_body,
        original_sender, original_date, forward_note, cc_email, use_html,
    )
    return send_raw_mail(message, policy_key)


def main() -> None:
    from mail_templates import list_templates, render_template, TEMPLATES

    parser = argparse.ArgumentParser(description="邮件回复与转发（支持 HTML 美化）")
    sub = parser.add_subparsers(dest="command")

    p_reply = sub.add_parser("reply", help="回复邮件")
    p_reply.add_argument("--to", required=True, help="收件人")
    p_reply.add_argument("--subject", required=True, help="原邮件主题")
    p_reply.add_argument("--original-body", default="", help="原邮件正文")
    p_reply.add_argument("--original-sender", default="", help="原邮件发件人")
    p_reply.add_argument("--original-date", default="", help="原邮件日期")
    p_reply.add_argument("--body", required=True, help="回复内容")
    p_reply.add_argument("--template", choices=list(TEMPLATES.keys()), help="使用模板美化回复")
    p_reply.add_argument("--sender-name", default="", help="发件人署名")
    p_reply.add_argument("--recipient-name", default="", help="收件人称呼")
    p_reply.add_argument("--highlight", default="", help="高亮内容")
    p_reply.add_argument("--cc", default=None)
    p_reply.add_argument("--html", action="store_true", help="启用 HTML 格式")

    p_forward = sub.add_parser("forward", help="转发邮件")
    p_forward.add_argument("--to", required=True, help="收件人")
    p_forward.add_argument("--subject", required=True, help="原邮件主题")
    p_forward.add_argument("--original-body", default="", help="原邮件正文")
    p_forward.add_argument("--original-sender", default="", help="原邮件发件人")
    p_forward.add_argument("--original-date", default="", help="原邮件日期")
    p_forward.add_argument("--note", default="", help="转发附言")
    p_forward.add_argument("--cc", default=None)
    p_forward.add_argument("--html", action="store_true", help="启用 HTML 格式")

    p_templates = sub.add_parser("templates", help="查看可用模板")

    args = parser.parse_args()

    if args.command == "reply":
        # 将命令行中字面的 \n 转换为真正的换行符
        def _fix_nl(s: str) -> str:
            return s.replace("\\n", "\n") if s else s

        body = _fix_nl(args.body)
        highlight = _fix_nl(args.highlight)
        if args.template:
            html, text = render_template(
                template_name=args.template,
                title=f"Re: {args.subject}",
                content=body,
                sender_name=_fix_nl(args.sender_name),
                recipient_name=_fix_nl(args.recipient_name),
                highlight=highlight,
            )
            body = html if args.html else text

        result = reply_to_email(
            args.to, args.subject, args.original_body,
            args.original_sender, args.original_date, body, args.cc,
            use_html=args.html or bool(args.template),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "forward":
        result = forward_email(
            args.to, args.subject, args.original_body,
            args.original_sender, args.original_date, args.note, args.cc,
            use_html=args.html,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "templates":
        print("# 可用模板")
        for t in list_templates():
            print(f"\n【{t['name']}】{t['description']}")
            print(f"  主题前缀: {t['subject_prefix'] or '(无)'}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
