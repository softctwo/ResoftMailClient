#!/usr/bin/env python3
"""智能批复建议 - 基于邮件类型和关键信息生成批复草稿。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from eas_env import add_import_path, load_env
from mail_templates import render_template, TEMPLATES
from enhanced_extractor import (
    extract_income_enhanced,
    extract_project_enhanced,
    extract_reimbursement_enhanced,
    extract_regulatory_enhanced,
)

load_env()
add_import_path()


# 批复模板库（更智能的版本）
SMART_TEMPLATES = {
    "立项_同意": """
{name}，您好：

关于《{project_name}》立项申请已审批通过。

项目信息：
- 项目编号：{project_code}
- 项目类型：{project_type}
- 预估利润率：{profit_rate}

请按公司项目管理流程推进后续工作，及时提交周报。

此致
""",
    "立项_需补充": """
{name}，您好：

关于《{project_name}》立项申请，需要补充以下信息：

{missing_info}

请完善后重新提交。

此致
""",
    "周报_收到": """
{name}，您好：

本周报已收到。

{feedback}

请继续按项目计划推进。

此致
""",
    "报销_通过": """
{name}，您好：

您的报销申请已审批通过，请留意到账通知。

此致
""",
    "报销_打回": """
{name}，您好：

您的报销申请被打回，原因如下：

{reason}

请按上述要求补充材料后重新提交。

此致
""",
    "提前进场_同意": """
{name}，您好：

同意《{project_name}》提前进场申请。

请做好客户沟通、资源安排及风险预案。

此致
""",
    "监管制度_知悉": """
各位同事：

{regulation_name} 已发布，生效日期：{effective_date}。

影响产品线：{product_lines}

请相关产品组评估影响并制定适配计划。

此致
""",
}


def suggest_reply(subject: str, body: str = "", sender: str = "", template_name: str = "") -> dict:
    """分析邮件并生成批复建议"""
    result = {
        "detected_type": None,
        "suggested_templates": [],
        "extracted_info": {},
        "draft": None,
        "draft_html": None,
    }

    # 提取发件人名字
    name_match = re.match(r'"?([^"<\n]+)"?', sender)
    sender_name = name_match.group(1).strip() if name_match else "同事"

    # 判断邮件类型
    if "立项" in subject or "预立项" in subject:
        result["detected_type"] = "立项"
        proj = extract_project_enhanced(subject, body)
        result["extracted_info"] = {
            "project_name": proj.project_name,
            "project_code": proj.project_code,
            "project_type": proj.project_type,
            "profit_rate": proj.profit_rate or "未提供",
        }

        rate_val = None
        if proj.profit_rate and "%" in proj.profit_rate:
            try:
                rate_val = float(proj.profit_rate.replace("%", ""))
            except ValueError:
                pass

        if rate_val is not None and rate_val < 15:
            result["suggested_templates"].append({
                "template": "立项_需补充",
                "reason": "利润率偏低，需进一步论证",
                "draft": SMART_TEMPLATES["立项_需补充"].format(
                    name=sender_name,
                    project_name=proj.project_name or "该项目",
                    missing_info="1. 利润率低于15%，请补充成本明细和盈利分析\n2. 请提供项目风险评估",
                ).strip(),
            })
        else:
            # 默认建议通过
            result["suggested_templates"].append({
                "template": "立项_同意",
                "reason": "利润率达标或无利润率数据，建议通过",
                "draft": SMART_TEMPLATES["立项_同意"].format(
                    name=sender_name,
                    project_name=proj.project_name or "该项目",
                    project_code=proj.project_code or "待分配",
                    project_type=proj.project_type or "工程",
                    profit_rate=proj.profit_rate or "未提供",
                ).strip(),
            })

    elif "周报" in subject:
        result["detected_type"] = "周报"
        # 生成简单反馈
        feedback = "本周工作进展正常。"
        if "延期" in body or "风险" in body:
            feedback = "请注意项目风险和延期情况，及时采取措施。"
        result["suggested_templates"].append({
            "template": "周报_收到",
            "reason": "常规周报回复",
            "draft": SMART_TEMPLATES["周报_收到"].format(
                name=sender_name,
                feedback=feedback,
            ).strip(),
        })

    elif "报销" in subject or "打回" in subject:
        result["detected_type"] = "报销"
        reimb = extract_reimbursement_enhanced(subject, body)
        result["extracted_info"] = {"status": reimb.status, "amount": reimb.amount}

        if reimb.status == "打回":
            result["suggested_templates"].append({
                "template": "报销_打回",
                "reason": "报销被打回，需补充材料",
                "draft": SMART_TEMPLATES["报销_打回"].format(
                    name=sender_name,
                    reason=reimb.reason or "请检查报销单据是否齐全",
                ).strip(),
            })
        else:
            result["suggested_templates"].append({
                "template": "报销_通过",
                "reason": "报销待办提醒",
                "draft": SMART_TEMPLATES["报销_通过"].format(name=sender_name).strip(),
            })

    elif "提前进场" in subject or "进场申请" in subject:
        result["detected_type"] = "提前进场"
        proj = extract_project_enhanced(subject, body)
        result["suggested_templates"].append({
            "template": "提前进场_同意",
            "reason": "常规提前进场审批",
            "draft": SMART_TEMPLATES["提前进场_同意"].format(
                name=sender_name,
                project_name=proj.project_name or "该项目",
            ).strip(),
        })

    elif "制度" in subject or "发文" in subject:
        result["detected_type"] = "监管制度"
        reg = extract_regulatory_enhanced(subject, body)
        result["extracted_info"] = {
            "regulation_name": reg.regulation_name,
            "effective_date": reg.effective_date or "待定",
            "product_lines": ", ".join(reg.product_lines),
        }
        result["suggested_templates"].append({
            "template": "监管制度_知悉",
            "reason": "制度发文通知",
            "draft": SMART_TEMPLATES["监管制度_知悉"].format(
                regulation_name=reg.regulation_name or "该制度",
                effective_date=reg.effective_date or "待定",
                product_lines=", ".join(reg.product_lines),
            ).strip(),
        })

    # 选择最佳建议
    if result["suggested_templates"]:
        result["draft"] = result["suggested_templates"][0]["draft"]

    # 如果指定了模板，生成 HTML 版批复
    if template_name and template_name in TEMPLATES and result["draft"]:
        html, text = render_template(
            template_name=template_name,
            title=subject,
            content=result["draft"],
            sender_name="",
            recipient_name=name_match.group(1).strip() if name_match else "同事",
            highlight=result["extracted_info"].get("project_name") or result["extracted_info"].get("regulation_name") or "",
        )
        result["draft_html"] = html
        result["draft"] = text if not result["draft_html"] else result["draft"]

    return result


def suggest_from_archive(limit: int = 20, template_name: str = "") -> list[dict]:
    """从本地归档批量生成批复建议"""
    archive_dir = Path(__file__).resolve().parent / "mail_archive"
    index_file = archive_dir / "index" / "mail_index.json"
    if not index_file.exists():
        return []

    index = json.loads(index_file.read_text(encoding="utf-8"))
    results = []
    count = 0

    for mid, e in index.get("emails", {}).items():
        if count >= limit:
            break
        subject = e.get("subject", "")
        sender = e.get("sender", "")
        category = e.get("category", "")

        # 只处理需要批复的邮件
        if category not in {"立项审批", "财务报销", "商务协同", "监管制度", "周报日报"}:
            continue

        folder = e.get("folder", "")
        filename = e.get("filename", "")
        body = ""
        if filename:
            filepath = archive_dir / folder / filename
            if filepath.exists():
                try:
                    data = json.loads(filepath.read_text(encoding="utf-8"))
                    body = data.get("body_text", "") or ""
                except Exception:
                    pass

        suggestion = suggest_reply(subject, body, sender, template_name=template_name)
        if suggestion["detected_type"]:
            results.append({
                "subject": subject,
                "sender": sender,
                "detected_type": suggestion["detected_type"],
                "draft_preview": (suggestion["draft_html"] or suggestion["draft"] or "")[:100] + "...",
                "draft_full": suggestion["draft_html"] or suggestion["draft"],
                "is_html": bool(suggestion.get("draft_html")),
            })
            count += 1

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="智能批复建议")
    parser.add_argument("--subject", default="", help="邮件主题")
    parser.add_argument("--body", default="", help="邮件正文")
    parser.add_argument("--sender", default="", help="发件人")
    parser.add_argument("--batch", action="store_true", help="批量分析本地归档")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--template", choices=list(TEMPLATES.keys()), default="",
                        help="使用模板生成 HTML 格式批复建议")
    args = parser.parse_args()

    if args.batch:
        results = suggest_from_archive(limit=args.limit, template_name=args.template)
        for r in results:
            print(f"\n[{r['detected_type']}] {r['subject'][:50]}")
            print(f"发件人: {r['sender'][:30]}")
            print(f"建议批复: {r['draft_preview']}")
            if r.get("is_html"):
                print(f"格式: HTML (模板: {args.template})")
    else:
        result = suggest_reply(args.subject, args.body, args.sender, template_name=args.template)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
