#!/usr/bin/env python3
"""经营数据图表生成 - 收入趋势、分类统计、周报提交率。"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from eas_env import add_import_path, load_env

load_env()
add_import_path()

BASE_DIR = Path(__file__).resolve().parent
ARCHIVE_DIR = BASE_DIR / "mail_archive"
REPORTS_DIR = ARCHIVE_DIR / "reports"
INDEX_FILE = ARCHIVE_DIR / "index" / "mail_index.json"

# 尝试导入 matplotlib，未安装则输出文本报告
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # 设置中文字体（macOS 常见字体）
    for font_name in ["PingFang HK", "Heiti TC", "Arial Unicode MS", "SimHei"]:
        try:
            plt.rcParams["font.sans-serif"] = [font_name, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            break
        except Exception:
            continue
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


def load_index() -> dict:
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    return {"emails": {}}


def generate_income_trend(index: dict, weeks: int = 8) -> dict:
    """生成收入统计趋势数据"""
    weekly = defaultdict(list)
    now = datetime.now()

    for mid, e in index.get("emails", {}).items():
        if e.get("category") not in {"经营统计", "财务统计"}:
            continue
        received = e.get("received_at", "")
        try:
            dt = datetime.fromisoformat(received.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, TypeError):
            continue

        # 按周分组
        week_start = dt - timedelta(days=dt.weekday())
        week_key = week_start.strftime("%Y-%m-%d")
        weekly[week_key].append(e)

    # 最近 N 周
    results = []
    for i in range(weeks - 1, -1, -1):
        week_start = now - timedelta(days=now.weekday() + i * 7)
        week_key = week_start.strftime("%Y-%m-%d")
        emails = weekly.get(week_key, [])
        results.append({
            "week": week_key,
            "count": len(emails),
            "subjects": [e.get("subject", "") for e in emails[:3]],
        })

    return {"trend": results, "total_income_emails": sum(len(v) for v in weekly.values())}


def generate_category_distribution(index: dict) -> dict:
    """生成分类分布数据"""
    categories = defaultdict(int)
    for e in index.get("emails", {}).values():
        cat = e.get("category", "其他")
        categories[cat] += 1
    return dict(sorted(categories.items(), key=lambda x: -x[1]))


def generate_weekly_submission_rate(index: dict, weeks: int = 4) -> dict:
    """生成周报提交率统计"""
    now = datetime.now()
    results = []

    for i in range(weeks - 1, -1, -1):
        week_start = now - timedelta(days=now.weekday() + i * 7)
        week_end = week_start + timedelta(days=7)

        weekly_senders = set()
        for e in index.get("emails", {}).values():
            if e.get("category") not in {"周报", "周报日报"}:
                continue
            received = e.get("received_at", "")
            try:
                dt_str = received.replace("Z", "+00:00")
                dt = datetime.fromisoformat(dt_str).replace(tzinfo=None)
                ws_naive = week_start.replace(tzinfo=None) if week_start.tzinfo else week_start
                we_naive = week_end.replace(tzinfo=None) if week_end.tzinfo else week_end
                if ws_naive <= dt < we_naive:
                    sender = e.get("sender", "")
                    match = re.match(r'"?([^"<\n]+)"?', sender)
                    name = match.group(1).strip() if match else sender[:20]
                    weekly_senders.add(name)
            except (ValueError, TypeError):
                continue

        results.append({
            "week": week_start.strftime("%Y-%m-%d"),
            "submitter_count": len(weekly_senders),
            "submitters": list(weekly_senders)[:10],
        })

    return {"weekly_rates": results}


def generate_priority_distribution(index: dict) -> dict:
    """生成优先级分布"""
    from analysis_rules import classify
    priority_counts = defaultdict(int)
    for e in index.get("emails", {}).values():
        subject = e.get("subject", "")
        sender = e.get("sender", "")
        _, priority, _ = classify(subject, sender)
        priority_counts[priority] += 1
    return dict(sorted(priority_counts.items(), key=lambda x: -x[1]))


def draw_income_trend(data: dict, output_path: Path) -> Path | None:
    if not MATPLOTLIB_AVAILABLE:
        return None
    trend = data.get("trend", [])
    weeks = [t["week"][-5:] for t in trend]  # MM-DD
    counts = [t["count"] for t in trend]

    plt.figure(figsize=(10, 5))
    plt.plot(weeks, counts, marker="o", linewidth=2, markersize=8)
    plt.title("经营统计邮件趋势（最近8周）")
    plt.xlabel("周")
    plt.ylabel("邮件数量")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    return output_path


def draw_category_pie(data: dict, output_path: Path) -> Path | None:
    if not MATPLOTLIB_AVAILABLE:
        return None
    labels = list(data.keys())[:8]
    sizes = [data[k] for k in labels]
    colors = plt.cm.Set3(range(len(labels)))

    plt.figure(figsize=(8, 8))
    plt.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90, colors=colors)
    plt.title("邮件分类分布")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    return output_path


def generate_full_report() -> dict:
    index = load_index()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    income = generate_income_trend(index)
    categories = generate_category_distribution(index)
    weekly = generate_weekly_submission_rate(index)
    priorities = generate_priority_distribution(index)

    result = {
        "generated_at": datetime.now().isoformat(),
        "income_trend": income,
        "category_distribution": categories,
        "weekly_submission": weekly,
        "priority_distribution": priorities,
    }

    # 保存 JSON
    json_path = REPORTS_DIR / f"full_report_{datetime.now().strftime('%Y%m%d')}.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # 生成图表
    charts = {}
    if MATPLOTLIB_AVAILABLE:
        chart1 = draw_income_trend(income, REPORTS_DIR / f"income_trend_{datetime.now().strftime('%Y%m%d')}.png")
        if chart1:
            charts["income_trend"] = str(chart1.relative_to(BASE_DIR))
        chart2 = draw_category_pie(categories, REPORTS_DIR / f"category_pie_{datetime.now().strftime('%Y%m%d')}.png")
        if chart2:
            charts["category_pie"] = str(chart2.relative_to(BASE_DIR))

    result["charts"] = charts
    result["json_path"] = str(json_path.relative_to(BASE_DIR))
    return result


def format_text_report(result: dict) -> str:
    lines = [
        "# 经营数据报告",
        f"生成时间: {result['generated_at'][:19].replace('T', ' ')}",
        "",
        "## 邮件分类分布",
    ]
    for cat, count in result["category_distribution"].items():
        lines.append(f"- {cat}: {count} 封")

    lines.extend(["", "## 经营统计邮件趋势（最近8周）"])
    for t in result["income_trend"]["trend"]:
        lines.append(f"- 周 {t['week']}: {t['count']} 封")

    lines.extend(["", "## 周报提交情况（最近4周）"])
    for w in result["weekly_submission"]["weekly_rates"]:
        lines.append(f"- 周 {w['week']}: {w['submitter_count']} 人提交")

    lines.extend(["", "## 优先级分布"])
    for pri, count in result["priority_distribution"].items():
        lines.append(f"- {pri}: {count} 封")

    if result.get("charts"):
        lines.extend(["", "## 生成图表"])
        for name, path in result["charts"].items():
            lines.append(f"- {name}: {path}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="经营数据图表生成")
    parser.add_argument("--text", action="store_true", help="输出文本报告")
    args = parser.parse_args()

    result = generate_full_report()
    if args.text or not MATPLOTLIB_AVAILABLE:
        print(format_text_report(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
