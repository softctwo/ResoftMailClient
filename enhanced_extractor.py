#!/usr/bin/env python3
"""增强型正文关键信息结构化提取 - 支持立项、收入、报销、监管制度等场景。"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from eas_env import add_import_path, load_env

load_env()
add_import_path()


@dataclass
class ProjectExtract:
    project_name: str | None
    project_code: str | None
    project_type: str | None  # 售前/工程/研发
    budget: str | None
    profit_rate: str | None
    duration_months: str | None
    customer_name: str | None
    pm_name: str | None
    status: str | None  # 立项/结论/审批中
    risk_points: list[str]


@dataclass
class IncomeExtract:
    report_period: str | None
    total_income: str | None
    contract_liability: str | None
    project_breakdown: list[dict]


@dataclass
class ReimbursementExtract:
    status: str | None  # 待办/打回/已通过
    amount: str | None
    reason: str | None
    required_action: str | None


@dataclass
class RegulatoryExtract:
    regulation_name: str | None
    effective_date: str | None
    product_lines: list[str]
    impact_level: str | None  # 高/中/低


# 更精确的正则模式
PROJECT_CODE_PATTERN = re.compile(r"(\d{10,})|(\d{6,}-\d{4,})|(\d{5}[A-Z]\d{5,})")
BUDGET_PATTERN = re.compile(r"(?:预算|金额|合同额|总价)[：:\s]*([\d.,]+\s*[万亿元]?)", re.I)
PROFIT_RATE_PATTERN = re.compile(r"(?:利润率|毛利率|净利率)[：:\s]*(\d+(?:\.\d+)?\s*%)", re.I)
DURATION_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:人月|人天|个月|月)")
CUSTOMER_PATTERN = re.compile(r"(?:客户|甲方|行方)[：:\s]*([^，。\n]{2,20})")
PM_PATTERN = re.compile(r"(?:项目经理|PM|负责人)[：:\s]*([^，。\n\s]{2,10})")
AMOUNT_PATTERN = re.compile(r"(?:金额|总价|合计)[：:\s]*([\d.,]+)")
REJECT_REASON_PATTERN = re.compile(r"(?:打回原因|驳回理由|需补充)[：:\s]*([^\n]{2,100})")
REGULATION_NAME_PATTERN = re.compile(r"(?:制度名称|发文名称|规范名称)[：:\s]*([^\n]{2,60})")
EFFECTIVE_DATE_PATTERN = re.compile(r"(?:生效日期|执行日期|自\s*)(20\d{2}[-年/]\d{1,2}[-月/]\d{1,2})")


def _clean_html(text: str) -> str:
    """去除 HTML 标签，保留纯文本"""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_project_enhanced(subject: str, body: str = "") -> ProjectExtract:
    body = _clean_html(body)
    text = f"{subject}\n{body}"
    code_match = PROJECT_CODE_PATTERN.search(subject)
    code = code_match.group(0) if code_match else None

    # 项目名称：优先从主题提取
    name = subject.strip("【】 ")
    for prefix in ["售前工程立项结论", "工程立项结论", "研发立项评审结论", "售前预立项结论", "立项结论"]:
        if prefix in subject:
            idx = subject.find(prefix)
            name = subject[idx + len(prefix):].strip("【】 -|")
            break

    # 项目类型
    ptype = None
    if "售前" in text:
        ptype = "售前"
    elif "工程" in text:
        ptype = "工程"
    elif "研发" in text:
        ptype = "研发"

    # 预算
    budget = None
    bmatch = BUDGET_PATTERN.search(text)
    if bmatch:
        budget = bmatch.group(1)

    # 利润率
    profit = None
    pmatch = PROFIT_RATE_PATTERN.search(text)
    if pmatch:
        profit = pmatch.group(1)

    # 工期
    duration = None
    dmatch = DURATION_PATTERN.search(text)
    if dmatch:
        duration = dmatch.group(1)

    # 客户
    customer = None
    cmatch = CUSTOMER_PATTERN.search(body)
    if cmatch:
        customer = cmatch.group(1).strip()

    # 项目经理
    pm = None
    pmmatch = PM_PATTERN.search(text)
    if pmmatch:
        pm = pmmatch.group(1).strip()

    # 状态
    status = "立项"
    if "结论" in subject or "评审" in subject:
        status = "已结论"
    elif "审批" in subject:
        status = "审批中"

    # 风险点
    risks = []
    for kw in ["延期", "风险", "利润率不足", "提前进场", "验收", "打回"]:
        if kw in text:
            risks.append(kw)

    return ProjectExtract(
        project_name=name or None,
        project_code=code,
        project_type=ptype,
        budget=budget,
        profit_rate=profit,
        duration_months=duration,
        customer_name=customer,
        pm_name=pm,
        status=status,
        risk_points=risks,
    )


def extract_income_enhanced(subject: str, body: str = "") -> IncomeExtract:
    text = f"{subject}\n{body}"
    period = None
    pm = re.search(r"(20\d{2}[-年/]\d{1,2})", subject)
    if pm:
        period = pm.group(1)

    total = None
    tm = re.search(r"(?:收入|共计|合计)[：:\s]*([\d.,]+)\s*万?", text)
    if tm:
        total = tm.group(1)

    liability = None
    lm = re.search(r"(?:合同负债|负债余额)[：:\s]*([\d.,]+)", text)
    if lm:
        liability = lm.group(1)

    # 项目明细（从表格或列表中提取）
    breakdown = []
    lines = body.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 简单匹配：项目名 + 金额
        m = re.search(r"([^\t]{3,30})\t+([\d.,]+)\s*万?", line)
        if m:
            breakdown.append({
                "project": m.group(1).strip(),
                "amount": m.group(2),
            })

    return IncomeExtract(
        report_period=period,
        total_income=total,
        contract_liability=liability,
        project_breakdown=breakdown,
    )


def extract_reimbursement_enhanced(subject: str, body: str = "") -> ReimbursementExtract:
    text = f"{subject}\n{body}"
    status = None
    if "打回" in text:
        status = "打回"
    elif "待办" in text:
        status = "待办"
    elif "已通过" in text or "审批通过" in text:
        status = "已通过"

    amount = None
    am = AMOUNT_PATTERN.search(text)
    if am:
        amount = am.group(1)

    reason = None
    rm = REJECT_REASON_PATTERN.search(body)
    if rm:
        reason = rm.group(1).strip()

    action = None
    if "补充" in body:
        action = "补充材料"
    elif "重新提交" in body:
        action = "重新提交"

    return ReimbursementExtract(
        status=status,
        amount=amount,
        reason=reason,
        required_action=action,
    )


def extract_regulatory_enhanced(subject: str, body: str = "") -> RegulatoryExtract:
    text = f"{subject}\n{body}"
    name = None
    nm = REGULATION_NAME_PATTERN.search(body)
    if nm:
        name = nm.group(1).strip()
    else:
        # 从主题提取
        for prefix in ["获取新发文通知：", "制度发文-", "关于"]:
            if prefix in subject:
                name = subject.split(prefix, 1)[-1].strip("【】 ")
                break

    ed = EFFECTIVE_DATE_PATTERN.search(text)
    effective = ed.group(1) if ed else None

    # 产品线影响
    products = []
    product_keywords = {
        "一表通": ["一表通", "监管报送", "金数"],
        "EAST": ["EAST", "EAST5.0"],
        "反洗钱": ["反洗钱", "AML"],
        "利率报备": ["利率报备", "IRS"],
        "数据治理": ["数据治理", "可信区"],
        "票据": ["票据"],
        "RCPMIS": ["RCPMIS"],
        "1104": ["1104"],
    }
    for pl, kws in product_keywords.items():
        if any(kw in text for kw in kws):
            products.append(pl)

    # 影响等级判断
    level = "中"
    if "紧急" in text or "立即执行" in text:
        level = "高"
    elif "征求意见" in text or "预告" in text:
        level = "低"

    return RegulatoryExtract(
        regulation_name=name,
        effective_date=effective,
        product_lines=products or ["待确认"],
        impact_level=level,
    )


def analyze_email(subject: str, body: str = "", category: str = "") -> dict:
    """根据分类选择对应的提取器"""
    result = {
        "subject": subject,
        "category": category,
        "project": None,
        "income": None,
        "reimbursement": None,
        "regulatory": None,
    }

    if category == "立项审批" or "立项" in subject:
        result["project"] = asdict(extract_project_enhanced(subject, body))

    if category == "经营统计" or "收入" in subject or "合同负债" in subject:
        result["income"] = asdict(extract_income_enhanced(subject, body))

    if category == "财务报销" or "报销" in subject:
        result["reimbursement"] = asdict(extract_reimbursement_enhanced(subject, body))

    if category == "监管制度" or "制度" in subject or "发文" in subject:
        result["regulatory"] = asdict(extract_regulatory_enhanced(subject, body))

    return result


def batch_analyze_from_archive(limit: int = 50) -> list[dict]:
    """从本地归档批量分析邮件"""
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
        category = e.get("category", "")
        subject = e.get("subject", "")
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

        analysis = analyze_email(subject, body, category)
        if any(v for k, v in analysis.items() if k not in {"subject", "category"}):
            results.append(analysis)
            count += 1

    return results


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="增强型正文结构化提取")
    parser.add_argument("--subject", default="", help="邮件主题")
    parser.add_argument("--body", default="", help="邮件正文")
    parser.add_argument("--category", default="", help="分类")
    parser.add_argument("--batch", action="store_true", help="批量分析本地归档")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    if args.batch:
        results = batch_analyze_from_archive(limit=args.limit)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        result = analyze_email(args.subject, args.body, args.category)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
