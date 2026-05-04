#!/usr/bin/env python3
"""邮件全文检索引擎 - 基于 SQLite FTS5。"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from eas_env import add_import_path, load_env

load_env()
add_import_path()

BASE_DIR = Path(__file__).resolve().parent
ARCHIVE_DIR = BASE_DIR / "mail_archive"
INDEX_FILE = ARCHIVE_DIR / "index" / "mail_index.json"
DB_PATH = ARCHIVE_DIR / "index" / "mail_search.db"


def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id TEXT PRIMARY KEY,
            subject TEXT,
            sender TEXT,
            sender_name TEXT,
            received_at TEXT,
            category TEXT,
            body_text TEXT,
            folder TEXT,
            filename TEXT,
            content_fts TEXT
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts USING fts5(
            content_fts,
            content='emails',
            content_rowid='rowid'
        )
    """)
    conn.commit()
    return conn


def _extract_name(sender: str) -> str:
    match = re.match(r'"?([^"<\n]+)"?', sender)
    return match.group(1).strip() if match else sender[:20]


def rebuild_index() -> dict:
    """从 mail_index.json 重建全文检索索引"""
    if not INDEX_FILE.exists():
        return {"error": "mail_index.json 不存在，请先运行 mail_manager.py sync-incremental"}

    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    conn = init_db()

    # 清空旧数据
    conn.execute("DELETE FROM emails")
    conn.execute("DELETE FROM emails_fts")

    emails = list(index.get("emails", {}).values())
    # 尝试导入 jieba 做中文分词
    try:
        import jieba
        JIEBA_AVAILABLE = True
    except ImportError:
        JIEBA_AVAILABLE = False

    def tokenize_for_fts(text: str) -> str:
        if not text:
            return ""
        if JIEBA_AVAILABLE:
            # 对中文部分做分词，保留英文单词
            tokens = []
            for tok in jieba.cut(text):
                t = tok.strip()
                if t:
                    tokens.append(t)
            return " ".join(tokens)
        return text

    inserted = 0

    for e in emails:
        mid = e.get("server_id", "")
        if not mid:
            continue
        subject = e.get("subject", "") or ""
        sender = e.get("sender", "") or ""
        sender_name = _extract_name(sender)
        received = e.get("received_at", "") or ""
        category = e.get("category", "") or ""
        folder = e.get("folder", "") or ""
        filename = e.get("filename", "") or ""

        # 尝试读取正文
        body_text = ""
        if filename:
            filepath = ARCHIVE_DIR / folder / filename
            if filepath.exists():
                try:
                    data = json.loads(filepath.read_text(encoding="utf-8"))
                    body_text = data.get("body_text", "") or ""
                except Exception:
                    pass

        content_fts = tokenize_for_fts(f"{subject} {sender_name} {body_text[:2000]}")

        conn.execute(
            """INSERT INTO emails (id, subject, sender, sender_name, received_at, category, body_text, folder, filename, content_fts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mid, subject, sender, sender_name, received, category, body_text, folder, filename, content_fts),
        )
        inserted += 1

    conn.execute("INSERT INTO emails_fts(rowid, content_fts) SELECT rowid, content_fts FROM emails")
    conn.commit()
    conn.close()

    return {"inserted": inserted, "db_path": str(DB_PATH)}


def _build_fts_query(query: str) -> str:
    """将查询词用 jieba 分词后构建 FTS MATCH 表达式"""
    try:
        import jieba
        tokens = [t.strip() for t in jieba.cut(query) if t.strip()]
    except ImportError:
        tokens = query.split()
    if not tokens:
        return query
    # 每个 token 用引号包裹，用 AND 连接
    return " AND ".join(f'"{t}"' for t in tokens)


def search(
    query: str,
    category: str | None = None,
    sender: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """全文检索邮件（支持中文分词）"""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    fts_query = _build_fts_query(query)

    sql = """
        SELECT e.* FROM emails e
        JOIN emails_fts fts ON e.rowid = fts.rowid
        WHERE emails_fts MATCH ?
    """
    params = [fts_query]

    if category:
        sql += " AND e.category = ?"
        params.append(category)
    if sender:
        sql += " AND (e.sender LIKE ? OR e.sender_name LIKE ?)"
        params.extend([f"%{sender}%", f"%{sender}%"])
    if date_from:
        sql += " AND e.received_at >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND e.received_at < ?"
        params.append(date_to)

    sql += " ORDER BY e.received_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "subject": row["subject"],
            "sender": row["sender"],
            "sender_name": row["sender_name"],
            "received_at": row["received_at"],
            "category": row["category"],
            "body_preview": (row["body_text"] or "")[:300],
        })
    return results


def advanced_search(
    queries: list[str],
    must_have: list[str] | None = None,
    exclude: list[str] | None = None,
    limit: int = 20,
) -> list[dict]:
    """高级搜索：支持多条件组合"""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    conditions = []
    params = []

    if queries:
        fts_parts = []
        for q in queries:
            fts_parts.append(_build_fts_query(q))
        conditions.append("(" + " OR ".join("emails_fts MATCH ?" for _ in fts_parts) + ")")
        params.extend(fts_parts)

    if must_have:
        for word in must_have:
            conditions.append("emails_fts MATCH ?")
            params.append(_build_fts_query(word))

    sql = f"""
        SELECT e.* FROM emails e
        JOIN emails_fts fts ON e.rowid = fts.rowid
        WHERE {' AND '.join(conditions)}
        ORDER BY e.received_at DESC LIMIT ?
    """
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "subject": row["subject"],
            "sender": row["sender"],
            "sender_name": row["sender_name"],
            "received_at": row["received_at"],
            "category": row["category"],
            "body_preview": (row["body_text"] or "")[:300],
        })
    conn.close()
    return results


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="邮件全文检索引擎")
    sub = parser.add_subparsers(dest="command")

    p_rebuild = sub.add_parser("rebuild", help="重建索引")

    p_search = sub.add_parser("search", help="搜索")
    p_search.add_argument("query", help="搜索关键词")
    p_search.add_argument("--category", default=None)
    p_search.add_argument("--sender", default=None)
    p_search.add_argument("--from-date", default=None, help="开始日期 YYYY-MM-DD")
    p_search.add_argument("--to-date", default=None, help="结束日期 YYYY-MM-DD")
    p_search.add_argument("--limit", type=int, default=20)

    p_advanced = sub.add_parser("advanced", help="高级搜索")
    p_advanced.add_argument("--query", action="append", default=[], help="关键词（可多次，OR关系）")
    p_advanced.add_argument("--must", action="append", default=[], help="必须包含的词")
    p_advanced.add_argument("--limit", type=int, default=20)

    args = parser.parse_args()

    if args.command == "rebuild":
        result = rebuild_index()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "search":
        date_from = None
        date_to = None
        if args.from_date:
            date_from = args.from_date + "T00:00:00"
        if args.to_date:
            date_to = args.to_date + "T23:59:59"
        results = search(
            args.query, category=args.category, sender=args.sender,
            date_from=date_from, date_to=date_to, limit=args.limit,
        )
        print(f"找到 {len(results)} 封邮件:")
        for r in results:
            print(f"\n[{r['received_at'][:10]}] {r['subject'][:60]}")
            print(f"  发件人: {r['sender_name']} | 分类: {r['category']}")
            if r["body_preview"]:
                print(f"  正文: {r['body_preview'][:100]}...")
    elif args.command == "advanced":
        results = advanced_search(args.query, must_have=args.must, limit=args.limit)
        print(f"找到 {len(results)} 封邮件:")
        for r in results:
            print(f"\n[{r['received_at'][:10]}] {r['subject'][:60]}")
            print(f"  发件人: {r['sender_name']} | 分类: {r['category']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
