#!/usr/bin/env python3
"""项目审批流程闭环追踪 - 以项目编号为线索串起立项目→结论→进场→周报→验收全流程。"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from eas_env import add_import_path, load_env
from analysis_rules import extract_project_info

load_env()
add_import_path()

BASE_DIR = Path(__file__).resolve().parent
ARCHIVE_DIR = BASE_DIR / "mail_archive"
INDEX_FILE = ARCHIVE_DIR / "index" / "mail_index.json"
TRACKER_FILE = BASE_DIR / "assistant_data" / "project_tracker.json"

# 流程阶段定义
STAGE_DEFINITIONS = [
    ("立项", ["立项", "预立项"], ["结论", "评审", "审批"]),
    ("进场", ["提前进场", "客户到访", "实施启动"], []),
    ("周报", ["周报", "日报", "项目周报"], []),
    ("验收", ["验收", "项目结论", "结项", "上线"], []),
    ("结算", ["结算", "回款", "收入确认"], []),
]


def load_index() -> dict:
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    return {"emails": {}}


def _extract_project_key(subject: str) -> str | None:
    """提取项目唯一标识（编号优先，名称次之）
    排除周报、日报、纯日期类主题。
    """
    # 排除周报/日报/行政通知/财务统计类
    exclude_keywords = ["周报", "日报", "月报", "放假", "通知", "工资条", "收入", "合同负债"]
    if any(kw in subject for kw in exclude_keywords):
        return None

    info = extract_project_info(subject)
    code = info.get("project_code")
    # 项目编号必须跟在非纯数字文本后（避免匹配日期）
    if code:
        # 验证：编号前必须有至少2个汉字或字母
        idx = subject.find(code)
        if idx > 0:
            prefix = subject[max(0, idx-10):idx]
            if re.search(r'[\u4e00-\u9fa5a-zA-Z]{2,}', prefix):
                return code

    # 尝试提取银行/客户名 + 系统名
    for pattern in [
        r"(北京银行[^-|】]+)", r"(恒生银行[^-|】]+)", r"(法兴银行[^-|】]+)",
        r"(稠州银行[^-|】]+)", r"(鞍钢[^-|】]+)", r"(中国建材[^-|】]+)",
        r"(天津农发行[^-|】]+)", r"(平安信托[^-|】]+)", r"(格力财务[^-|】]+)",
        r"(国家开发银行[^-|】]+)", r"(湖北农信[^-|】]+)", r"(徐工集团[^-|】]+)",
        r"(中建材[^-|】]+)", r"(德意志银行[^-|】]+)", r"(柳州银行[^-|】]+)",
    ]:
        match = re.search(pattern, subject)
        if match:
            return match.group(1).strip("【】 ")
    return None


def classify_stage(subject: str) -> str | None:
    subject_lower = subject.lower()
    for stage_name, include_keywords, exclude_keywords in STAGE_DEFINITIONS:
        if any(kw in subject_lower for kw in include_keywords):
            # 排除词仅在单独匹配时才排除，如果同时匹配包含词则优先
            if any(kw in subject_lower for kw in exclude_keywords):
                # 如果同时包含阶段词和排除词，检查优先级
                # 例如 "立项结论" 包含 "立项" 和 "结论"，仍应归类为立项
                continue
            return stage_name
    # 二次遍历：处理同时包含包含词和排除词的情况（立项优先）
    for stage_name, include_keywords, _ in STAGE_DEFINITIONS:
        if any(kw in subject_lower for kw in include_keywords):
            return stage_name
    return None


def build_project_timeline(index: dict) -> dict:
    """构建所有项目的时间线"""
    projects = defaultdict(lambda: {"stages": defaultdict(list), "first_seen": None, "last_seen": None})

    for mid, e in index.get("emails", {}).items():
        subject = e.get("subject", "")
        key = _extract_project_key(subject)
        if not key:
            continue

        received = e.get("received_at", "")
        stage = classify_stage(subject)
        if not stage:
            # 如果无法归类到具体阶段，也保留在项目下
            stage = "相关"

        try:
            dt = datetime.fromisoformat(received.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, TypeError):
            dt = None

        event = {
            "subject": subject,
            "sender": e.get("sender", ""),
            "received_at": received,
            "stage": stage,
            "category": e.get("category", "其他"),
        }
        projects[key]["stages"][stage].append(event)

        if dt:
            if projects[key]["first_seen"] is None or dt < projects[key]["first_seen"]:
                projects[key]["first_seen"] = dt
            if projects[key]["last_seen"] is None or dt > projects[key]["last_seen"]:
                projects[key]["last_seen"] = dt

    # 排序每个阶段的事件
    for proj in projects.values():
        for stage in proj["stages"]:
            proj["stages"][stage].sort(key=lambda x: x.get("received_at", ""), reverse=False)

    return dict(projects)


def detect_risks(projects: dict) -> list[dict]:
    """检测项目风险"""
    risks = []
    now = datetime.now()

    for name, proj in projects.items():
        stages = proj["stages"]

        # 风险1：立项后无进场
        if "立项" in stages and "进场" not in stages:
            lixiang_events = stages["立项"]
            if lixiang_events:
                try:
                    last_lixiang = datetime.fromisoformat(lixiang_events[-1]["received_at"].replace("Z", "+00:00")).replace(tzinfo=None)
                    days_since = (now - last_lixiang).days
                    if days_since > 30:
                        risks.append({
                            "project": name,
                            "risk_type": "立项后无进场",
                            "detail": f"立项后 {days_since} 天未收到进场邮件",
                            "severity": "高" if days_since > 60 else "中",
                        })
                except (ValueError, TypeError):
                    pass

        # 风险2：进场后无周报
        if "进场" in stages and "周报" not in stages:
            jinchang_events = stages["进场"]
            if jinchang_events:
                try:
                    last_jinchang = datetime.fromisoformat(jinchang_events[-1]["received_at"].replace("Z", "+00:00")).replace(tzinfo=None)
                    days_since = (now - last_jinchang).days
                    if days_since > 14:
                        risks.append({
                            "project": name,
                            "risk_type": "进场后无周报",
                            "detail": f"进场后 {days_since} 天未收到周报",
                            "severity": "中",
                        })
                except (ValueError, TypeError):
                    pass

        # 风险3：有周报但无验收（长期项目忽略）
        if "周报" in stages and "验收" not in stages:
            zhoubao_events = stages["周报"]
            if zhoubao_events:
                try:
                    first_zhoubao = datetime.fromisoformat(zhoubao_events[0]["received_at"].replace("Z", "+00:00")).replace(tzinfo=None)
                    weeks_since = (now - first_zhoubao).days / 7
                    if weeks_since > 26:  # 半年以上
                        risks.append({
                            "project": name,
                            "risk_type": "长期未验收",
                            "detail": f"已持续 {int(weeks_since)} 周仍未验收",
                            "severity": "低",
                        })
                except (ValueError, TypeError):
                    pass

    risks.sort(key=lambda x: {"高": 0, "中": 1, "低": 2}.get(x["severity"], 3))
    return risks


def format_project_report(name: str, proj: dict) -> str:
    lines = [f"# 项目: {name}", ""]
    stages = proj["stages"]
    first = proj["first_seen"]
    last = proj["last_seen"]

    if first and last:
        lines.append(f"跟踪周期: {first.strftime('%Y-%m-%d')} ~ {last.strftime('%Y-%m-%d')}")
        lines.append(f"持续天数: {(last - first).days} 天")
    lines.append(f"涉及邮件: {sum(len(v) for v in stages.values())} 封")
    lines.append("")

    for stage_name, _, _ in STAGE_DEFINITIONS:
        if stage_name in stages:
            events = stages[stage_name]
            lines.append(f"## {stage_name} ({len(events)} 封)")
            for e in events[-3:]:  # 最近3封
                lines.append(f"- [{e['received_at'][:10]}] {e['subject'][:50]} | {e['sender'][:20]}")
            lines.append("")

    if "相关" in stages:
        lines.append(f"## 其他相关 ({len(stages['相关'])} 封)")
        for e in stages["相关"][-3:]:
            lines.append(f"- [{e['received_at'][:10]}] {e['subject'][:50]}")

    return "\n".join(lines)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="项目审批流程闭环追踪")
    sub = parser.add_subparsers(dest="command")

    p_timeline = sub.add_parser("timeline", help="查看项目时间线")
    p_timeline.add_argument("--project", default=None, help="指定项目名/编号")
    p_timeline.add_argument("--limit", type=int, default=20)

    p_risks = sub.add_parser("risks", help="检测项目风险")

    p_list = sub.add_parser("list", help="列出所有跟踪中的项目")
    p_list.add_argument("--limit", type=int, default=30)

    args = parser.parse_args()

    index = load_index()
    projects = build_project_timeline(index)

    if args.command == "timeline":
        if args.project:
            if args.project in projects:
                print(format_project_report(args.project, projects[args.project]))
            else:
                print(f"未找到项目: {args.project}")
        else:
            for i, (name, proj) in enumerate(projects.items()):
                if i >= args.limit:
                    break
                print(format_project_report(name, proj))
                print("\n" + "=" * 60 + "\n")
    elif args.command == "risks":
        risks = detect_risks(projects)
        print(f"# 项目风险扫描 ({len(risks)} 项)\n")
        for r in risks:
            print(f"- [{r['severity']}] {r['project']}: {r['risk_type']}")
            print(f"  {r['detail']}")
    elif args.command == "list":
        print(f"# 跟踪中的项目 ({len(projects)} 个)\n")
        for name, proj in list(projects.items())[:args.limit]:
            stages = list(proj["stages"].keys())
            total = sum(len(v) for v in proj["stages"].values())
            print(f"- {name} | 阶段: {', '.join(stages)} | 共 {total} 封邮件")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
