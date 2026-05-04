#!/usr/bin/env python3
"""邮件模板库 - 支持多种办公场景的 HTML 邮件模板。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


def _looks_like_html(text: str) -> bool:
    """判断文本是否已经是 HTML"""
    if not text:
        return False
    html_tags = re.compile(r'<(html|div|p|br|table|tr|td|span|a|h[1-6]|ul|ol|li|b|i|strong|em|img|head|body|style|script)\b', re.I)
    return bool(html_tags.search(text))


@dataclass
class MailTemplate:
    name: str
    description: str
    subject_prefix: str
    html_template: str
    text_template: str


# 品牌色定义
PRIMARY_COLOR = "#1a5276"       # 深蓝
SECONDARY_COLOR = "#2874a6"     # 中蓝
ACCENT_COLOR = "#5dade2"        # 浅蓝
BG_COLOR = "#f8f9fa"            # 背景灰
TEXT_COLOR = "#2c3e50"          # 正文深灰
BORDER_COLOR = "#d5dbdb"        # 边框灰


def _common_styles() -> str:
    """返回公共 CSS 样式"""
    return """
    <style>
        body { margin: 0; padding: 0; font-family: "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif; background-color: #e8e8e8; }
        .wrapper { max-width: 680px; margin: 20px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        .header { background: linear-gradient(135deg, PRIMARY_COLOR 0%, SECONDARY_COLOR 100%); padding: 28px 32px; text-align: center; }
        .header h1 { color: #ffffff; margin: 0; font-size: 20px; font-weight: 500; letter-spacing: 1px; }
        .header .subtitle { color: rgba(255,255,255,0.85); margin: 8px 0 0; font-size: 13px; }
        .body { padding: 32px; color: TEXT_COLOR; font-size: 14px; line-height: 1.8; }
        .body p { margin: 0 0 14px; }
        .highlight-box { background: BG_COLOR; border-left: 4px solid ACCENT_COLOR; padding: 16px 20px; margin: 16px 0; border-radius: 0 6px 6px 0; }
        .highlight-box p { margin: 0; }
        .info-table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px; }
        .info-table th { background: BG_COLOR; padding: 10px 14px; text-align: left; font-weight: 600; color: PRIMARY_COLOR; border-bottom: 2px solid BORDER_COLOR; }
        .info-table td { padding: 10px 14px; border-bottom: 1px solid BORDER_COLOR; color: TEXT_COLOR; }
        .info-table tr:last-child td { border-bottom: none; }
        .footer { padding: 20px 32px; background: BG_COLOR; text-align: center; font-size: 12px; color: #7f8c8d; border-top: 1px solid BORDER_COLOR; }
        .footer .company { font-weight: 600; color: PRIMARY_COLOR; margin-bottom: 4px; }
        .btn { display: inline-block; padding: 10px 28px; background: PRIMARY_COLOR; color: #ffffff; text-decoration: none; border-radius: 4px; font-size: 13px; margin: 8px 0; }
        .divider { height: 1px; background: BORDER_COLOR; margin: 20px 0; }
        .tag { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; margin-right: 6px; }
        .tag-blue { background: #ebf5fb; color: PRIMARY_COLOR; }
        .tag-green { background: #eafaf1; color: #1e8449; }
        .tag-orange { background: #fef5e7; color: #b9770e; }
        .tag-red { background: #fdedec; color: #922b21; }
    </style>
    """.replace("PRIMARY_COLOR", PRIMARY_COLOR).replace("SECONDARY_COLOR", SECONDARY_COLOR).replace("ACCENT_COLOR", ACCENT_COLOR).replace("BG_COLOR", BG_COLOR).replace("TEXT_COLOR", TEXT_COLOR).replace("BORDER_COLOR", BORDER_COLOR)


# ========== 模板定义 ==========

TEMPLATES: dict[str, MailTemplate] = {}


def _register(template: MailTemplate) -> None:
    TEMPLATES[template.name] = template


_register(MailTemplate(
    name="formal",
    description="正式商务通知 - 适用于立项、审批、合同等正式场景",
    subject_prefix="【正式通知】",
    html_template=f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{_common_styles()}</head>
<body>
<div class="wrapper">
    <div class="header">
        <h1>{{{{title}}}}</h1>
        <div class="subtitle">{{{{subtitle}}}}</div>
    </div>
    <div class="body">
        <p>尊敬的 {{{{recipient_name}}}}：</p>
        <div class="highlight-box">
            <p>{{{{highlight}}}}</p>
        </div>
        {{{{content}}}}
        <div class="divider"></div>
        <p>如有疑问，请随时联系。</p>
    </div>
    <div class="footer">
        <div class="company">北京中软融鑫计算机系统工程有限公司</div>
        <div>{{{{sender_name}}}} | 工程交付中心</div>
        <div>{{{{send_time}}}}</div>
    </div>
</div>
</body>
</html>""",
    text_template="""
【{{title}}】
{{subtitle}}

尊敬的 {{recipient_name}}：

{{highlight}}

{{content}}

如有疑问，请随时联系。

---
北京中软融鑫计算机系统工程有限公司
{{sender_name}} | 工程交付中心
{{send_time}}
""",
))


_register(MailTemplate(
    name="weekly",
    description="周报批复 - 轻松但不失专业，适合批复周报、日报",
    subject_prefix="【周报批复】",
    html_template=f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{_common_styles()}</head>
<body>
<div class="wrapper">
    <div class="header" style="background: linear-gradient(135deg, #1e8449 0%, #28b463 100%);">
        <h1>{{{{title}}}}</h1>
        <div class="subtitle">{{{{subtitle}}}}</div>
    </div>
    <div class="body">
        <p>{{{{recipient_name}}}}，你好：</p>
        {{{{content}}}}
        <div class="highlight-box" style="border-left-color: #28b463;">
            <p><strong>批复意见：</strong>{{{{highlight}}}}</p>
        </div>
        <p>请继续按项目计划推进，如有风险及时上报。</p>
    </div>
    <div class="footer">
        <div class="company">工程交付中心</div>
        <div>{{{{sender_name}}}}</div>
        <div>{{{{send_time}}}}</div>
    </div>
</div>
</body>
</html>""",
    text_template="""
【{{title}}】
{{subtitle}}

{{recipient_name}}，你好：

{{content}}

批复意见：{{highlight}}

请继续按项目计划推进，如有风险及时上报。

---
工程交付中心
{{sender_name}}
{{send_time}}
""",
))


_register(MailTemplate(
    name="finance",
    description="财务/报销处理 - 流程清晰，信息明确",
    subject_prefix="【财务通知】",
    html_template=f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{_common_styles()}</head>
<body>
<div class="wrapper">
    <div class="header" style="background: linear-gradient(135deg, #b9770e 0%, #f39c12 100%);">
        <h1>{{{{title}}}}</h1>
        <div class="subtitle">{{{{subtitle}}}}</div>
    </div>
    <div class="body">
        <p>{{{{recipient_name}}}}：</p>
        <table class="info-table">
            <tr><th>项目</th><th>详情</th></tr>
            {{{{detail_rows}}}}
        </table>
        <div class="highlight-box" style="border-left-color: #f39c12;">
            <p><strong>处理结果：</strong>{{{{highlight}}}}</p>
        </div>
        {{{{content}}}}
    </div>
    <div class="footer">
        <div class="company">财务共享中心</div>
        <div>{{{{sender_name}}}}</div>
        <div>{{{{send_time}}}}</div>
    </div>
</div>
</body>
</html>""",
    text_template="""
【{{title}}】
{{subtitle}}

{{recipient_name}}：

处理结果：{{highlight}}

{{content}}

---
财务共享中心
{{sender_name}}
{{send_time}}
""",
))


_register(MailTemplate(
    name="project",
    description="项目通知 - 适合立项结论、进场批复、验收通知",
    subject_prefix="【项目通知】",
    html_template=f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{_common_styles()}</head>
<body>
<div class="wrapper">
    <div class="header" style="background: linear-gradient(135deg, #6c3483 0%, #8e44ad 100%);">
        <h1>{{{{title}}}}</h1>
        <div class="subtitle">{{{{subtitle}}}}</div>
    </div>
    <div class="body">
        <p>{{{{recipient_name}}}}，您好：</p>
        {{{{content}}}}
        <table class="info-table">
            <tr><th width="30%">项目信息</th><th>内容</th></tr>
            {{{{detail_rows}}}}
        </table>
        <div class="highlight-box" style="border-left-color: #8e44ad;">
            <p><strong>重要提示：</strong>{{{{highlight}}}}</p>
        </div>
    </div>
    <div class="footer">
        <div class="company">工程交付中心 · 项目管理部</div>
        <div>{{{{sender_name}}}}</div>
        <div>{{{{send_time}}}}</div>
    </div>
</div>
</body>
</html>""",
    text_template="""
【{{title}}】
{{subtitle}}

{{recipient_name}}，您好：

{{content}}

重要提示：{{highlight}}

---
工程交付中心 · 项目管理部
{{sender_name}}
{{send_time}}
""",
))


_register(MailTemplate(
    name="simple",
    description="简洁通用 - 最轻量的模板，适合日常简短通知",
    subject_prefix="",
    html_template=f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{_common_styles()}</head>
<body>
<div class="wrapper">
    <div class="header" style="background: linear-gradient(135deg, #566573 0%, #7f8c8d 100%); padding: 20px 32px;">
        <h1 style="font-size: 16px;">{{{{title}}}}</h1>
    </div>
    <div class="body" style="padding: 24px 32px;">
        {{{{content}}}}
    </div>
    <div class="footer" style="padding: 14px 32px;">
        <div>{{{{sender_name}}}} | {{{{send_time}}}}</div>
    </div>
</div>
</body>
</html>""",
    text_template="""
{{title}}

{{content}}

---
{{sender_name}}
{{send_time}}
""",
))


_register(MailTemplate(
    name="regulatory",
    description="监管制度通知 - 适合制度发文、合规通知",
    subject_prefix="【制度通知】",
    html_template=f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{_common_styles()}</head>
<body>
<div class="wrapper">
    <div class="header" style="background: linear-gradient(135deg, #922b21 0%, #c0392b 100%);">
        <h1>{{{{title}}}}</h1>
        <div class="subtitle">{{{{subtitle}}}}</div>
    </div>
    <div class="body">
        <p>各位同事：</p>
        {{{{content}}}}
        <div class="highlight-box" style="border-left-color: #c0392b;">
            <p><strong>生效日期：</strong>{{{{highlight}}}}</p>
        </div>
        <p>请相关产品组/部门评估影响并及时适配。</p>
    </div>
    <div class="footer">
        <div class="company">合规与风险管理部</div>
        <div>{{{{sender_name}}}}</div>
        <div>{{{{send_time}}}}</div>
    </div>
</div>
</body>
</html>""",
    text_template="""
【{{title}}】
{{subtitle}}

各位同事：

{{content}}

生效日期：{{highlight}}

请相关产品组/部门评估影响并及时适配。

---
合规与风险管理部
{{sender_name}}
{{send_time}}
""",
))


# ========== 张彦龙个人专属模板 ==========

ZHANGYANLONG_STYLES = """
<style>
    body { margin: 0; padding: 0; font-family: "PingFang SC", "Noto Serif SC", "Microsoft YaHei", "Songti SC", serif; background-color: #f0ece3; }
    .zy-wrapper { max-width: 720px; margin: 24px auto; background: #faf8f3; border-radius: 4px; overflow: hidden; box-shadow: 0 4px 16px rgba(26,58,92,0.10); border: 1px solid #e8e0d0; }
    .zy-header { background: #1a3a5c; padding: 32px 40px 28px; position: relative; }
    .zy-header::after { content: ""; position: absolute; bottom: 0; left: 40px; right: 40px; height: 2px; background: linear-gradient(90deg, #c9a96e 0%, transparent 100%); }
    .zy-header h1 { color: #faf8f3; margin: 0; font-size: 22px; font-weight: 500; letter-spacing: 2px; line-height: 1.4; }
    .zy-header .zy-subtitle { color: #c9a96e; margin: 10px 0 0; font-size: 13px; letter-spacing: 3px; font-weight: 300; }
    .zy-body { padding: 36px 40px; color: #2c2c2c; font-size: 15px; line-height: 2; }
    .zy-body p { margin: 0 0 16px; text-align: justify; }
    .zy-highlight { background: #f5f0e6; border-left: 3px solid #c9a96e; padding: 18px 24px; margin: 20px 0; font-size: 14px; color: #4a3f35; }
    .zy-highlight p { margin: 0; }
    .zy-divider { height: 1px; background: linear-gradient(90deg, transparent 0%, #d4c8b0 50%, transparent 100%); margin: 28px 0; }
    .zy-signature { padding: 32px 40px; background: #f5f0e6; border-top: 1px solid #e8e0d0; }
    .zy-sig-table { width: 100%; border-collapse: collapse; }
    .zy-sig-table td { vertical-align: middle; padding: 0; }
    .zy-sig-name { font-size: 20px; color: #1a3a5c; font-weight: 600; letter-spacing: 3px; margin-bottom: 4px; }
    .zy-sig-title { font-size: 13px; color: #8b7355; letter-spacing: 1px; }
    .zy-sig-sep { width: 1px; height: 56px; background: #d4c8b0; margin: 0 28px; }
    .zy-sig-contact { font-size: 12px; color: #6b5d4d; line-height: 1.9; }
    .zy-sig-motto { font-size: 14px; color: #8b3a3a; font-style: italic; margin-top: 8px; letter-spacing: 2px; }
    .zy-sig-motto::before { content: "「"; color: #c9a96e; margin-right: 4px; }
    .zy-sig-motto::after { content: "」"; color: #c9a96e; margin-left: 4px; }
    .zy-info-table { width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; }
    .zy-info-table th { background: #f5f0e6; padding: 12px 16px; text-align: left; font-weight: 500; color: #1a3a5c; border-bottom: 1px solid #d4c8b0; font-size: 13px; }
    .zy-info-table td { padding: 12px 16px; border-bottom: 1px solid #e8e0d0; color: #2c2c2c; }
    .zy-info-table tr:last-child td { border-bottom: none; }
    .zy-tag { display: inline-block; padding: 3px 12px; border-radius: 2px; font-size: 12px; margin-right: 8px; background: #e8e0d0; color: #5a4d3a; }
</style>
"""


_register(MailTemplate(
    name="zhangyanlong",
    description="张彦龙个人专属 - 藏青底色+暖金点缀，典雅商务，含个人签名",
    subject_prefix="",
    html_template=f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{ZHANGYANLONG_STYLES}</head>
<body>
<div class="zy-wrapper">
    <div class="zy-header">
        <h1>{{{{title}}}}</h1>
        <div class="zy-subtitle">{{{{subtitle}}}}</div>
    </div>
    <div class="zy-body">
        <p>{{{{recipient_name}}}}：</p>
        <div class="zy-highlight">
            <p>{{{{highlight}}}}</p>
        </div>
        {{{{content}}}}
        <div class="zy-divider"></div>
        <p style="font-size: 13px; color: #8b7355;">以上，如有任何问题请随时与我联系。</p>
    </div>
    <div class="zy-signature">
        <table class="zy-sig-table">
            <tr>
                <td style="width: 1px; white-space: nowrap;">
                    <div class="zy-sig-name">张彦龙</div>
                    <div class="zy-sig-title">副总经理 · 工程交付中心</div>
                </td>
                <td style="width: 1px;"><div class="zy-sig-sep"></div></td>
                <td>
                    <div class="zy-sig-contact">
                        北京中软融鑫计算机系统工程有限公司<br>
                        手机：18618145430
                    </div>
                    <div class="zy-sig-motto">敬天爱人</div>
                </td>
            </tr>
        </table>
    </div>
</div>
</body>
</html>""",
    text_template="""
{{title}}
{{subtitle}}

{{recipient_name}}：

{{highlight}}

{{content}}

以上，如有任何问题请随时与我联系。

---
张彦龙 | 副总经理 · 工程交付中心
北京中软融鑫计算机系统工程有限公司
手机：18618145430

「敬天爱人」
""",
))


def render_template(
    template_name: str,
    title: str,
    content: str,
    sender_name: str = "",
    recipient_name: str = "",
    subtitle: str = "",
    highlight: str = "",
    detail_rows: str = "",
) -> tuple[str, str]:
    """渲染指定模板，返回 (html_body, text_body)"""
    tmpl = TEMPLATES.get(template_name, TEMPLATES["simple"])
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 将纯文本内容转换为 HTML 段落（每行一个 <p>，空行保留间距）
    if not _looks_like_html(content):
        lines = content.split("\n")
        paras = []
        for line in lines:
            stripped = line.strip()
            if stripped:
                paras.append(f"<p>{stripped}</p>")
            else:
                paras.append("<p style='margin:4px 0;'>&nbsp;</p>")
        content_html = "\n".join(paras)
    else:
        content_html = content

    # highlight 同样处理换行
    highlight_html = highlight.replace("\n", "<br>") if highlight and not _looks_like_html(highlight) else highlight

    html_ctx = {
        "title": title,
        "content": content_html,
        "sender_name": sender_name,
        "recipient_name": recipient_name,
        "subtitle": subtitle,
        "highlight": highlight_html,
        "detail_rows": detail_rows,
        "send_time": now,
    }

    text_ctx = {
        "title": title,
        "content": content,
        "sender_name": sender_name,
        "recipient_name": recipient_name,
        "subtitle": subtitle,
        "highlight": highlight,
        "detail_rows": detail_rows,
        "send_time": now,
    }

    html = tmpl.html_template
    text = tmpl.text_template
    for key, val in html_ctx.items():
        html = html.replace(f"{{{{{key}}}}}", str(val))
    for key, val in text_ctx.items():
        text = text.replace(f"{{{{{key}}}}}", str(val))

    return html, text


def list_templates() -> list[dict]:
    return [
        {"name": t.name, "description": t.description, "subject_prefix": t.subject_prefix}
        for t in TEMPLATES.values()
    ]


def main() -> None:
    import json
    print(json.dumps(list_templates(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
