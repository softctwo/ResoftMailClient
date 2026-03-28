#!/usr/bin/env python3
"""
批量下载全部邮件正文 - v3 健壮版
修复: 文件名长度限制、Sync容错、完整重试机制
"""
import os, sys, json, time, warnings, re, traceback, hashlib
from pathlib import Path
from datetime import datetime
warnings.filterwarnings('ignore')

env_file = Path(__file__).parent / ".env.eas"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

sys.path.insert(0, str(Path(__file__).parent / "src"))
from eas_client.config import ClientConfig
from eas_client.eas.commands import (
    build_sync_request, build_provision_request,
    build_item_operations_message_request,
)
from eas_client.eas.parsers import (
    parse_sync_response, parse_item_operations_message_response,
)
from eas_client.transport import EasTransport
from eas_client.wbxml import decode_document, WbxmlElement, WbxmlText
from bs4 import BeautifulSoup

ARCHIVE_DIR = Path(__file__).parent / "mail_archive"
INDEX_FILE = ARCHIVE_DIR / "index" / "mail_index.json"
LOG_FILE = "/tmp/body_download.log"
COLLECTION_ID = "14"


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def save_index(index):
    tmp = INDEX_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(INDEX_FILE)


def make_filename(email):
    """用hash生成安全的短文件名，避免中文超长"""
    mid = email.get("server_id", "unknown").replace(":", "_")
    subj = email.get("subject", "无主题")[:30].replace("/", "_").replace("\\", "_")
    return f"{mid}_{subj}.json"


def provision(transport):
    resp = transport.post("Provision", build_provision_request())
    pk1 = re.findall(rb'\x03(\d{8,})\x00', resp)[0].decode()
    resp = transport.post("Provision", build_provision_request(policy_key=pk1))
    pk2 = re.findall(rb'\x03(\d{8,})\x00', resp)[-1].decode()
    return pk2


def full_sync(transport, max_retries=3):
    """完整同步所有邮件，增强容错"""
    all_ids = set()
    for attempt in range(max_retries):
        try:
            log(f"开始全量Sync (尝试 {attempt+1}/{max_retries})...")
            resp = transport.post("Sync", build_sync_request(
                collection_id=COLLECTION_ID, sync_key="0", window_size=256,
            ))
            sync1 = parse_sync_response(resp)
            for m in sync1.messages:
                all_ids.add(m.server_id)
            sk = sync1.sync_key

            while sk and sk != "0":
                try:
                    resp = transport.post("Sync", build_sync_request(
                        collection_id=COLLECTION_ID, sync_key=sk, window_size=256,
                    ))
                    if not resp:
                        break
                    sync_n = parse_sync_response(resp)
                    for m in sync_n.messages:
                        all_ids.add(m.server_id)
                    if len(sync_n.messages) == 0 or sync_n.sync_key == sk:
                        break
                    sk = sync_n.sync_key
                    if len(all_ids) % 500 == 0:
                        log(f"  Sync中: {len(all_ids)} 封")
                except Exception as e:
                    log(f"  Sync分页异常(继续): {e}")
                    break

            log(f"Sync完成: {len(all_ids)} 封")
            if len(all_ids) >= 2500:  # 合理数量就认为成功
                return all_ids
            log(f"Sync数量偏少({len(all_ids)}), 重试...")
        except Exception as e:
            log(f"Sync异常: {e}")
            time.sleep(3)
            # 重新认证
            try:
                provision(transport)
            except Exception:
                transport = EasTransport(ClientConfig.from_env())
                provision(transport)

    log(f"Sync最终: {len(all_ids)} 封")
    return all_ids


def download_body_raw(transport, server_id):
    """下载邮件正文，手动解析WBXML"""
    payload = build_item_operations_message_request(
        collection_id=COLLECTION_ID, server_id=server_id,
    )
    resp = transport.post("ItemOperations", payload)
    root = decode_document(resp).root

    def find_child(el, tag):
        if el is None: return None
        for c in el.children:
            if isinstance(c, WbxmlElement) and c.tag == tag: return c
        return None

    def get_text(el):
        if el is None: return None
        for c in el.children:
            if isinstance(c, WbxmlText): return c.text
        return None

    io_status = get_text(find_child(root, "Status"))
    if io_status and io_status != "1":
        raise ValueError(f"ItemOperations status {io_status}")

    response = find_child(root, "Response")
    if not response: raise ValueError("Missing Response")
    fetch = find_child(response, "Fetch")
    if not fetch: raise ValueError("Missing Fetch")

    fetch_status = get_text(find_child(fetch, "Status"))
    if fetch_status and fetch_status not in ("1", None):
        raise ValueError(f"Fetch status {fetch_status}")

    props = find_child(fetch, "Properties")
    if not props: raise ValueError("Missing Properties")

    body_el = find_child(props, "Body")
    body = get_text(find_child(body_el, "Data")) if body_el else None
    subject = get_text(find_child(props, "Subject"))
    sender = get_text(find_child(props, "From"))
    to = get_text(find_child(props, "To"))
    cc = get_text(find_child(props, "Cc"))
    date = get_text(find_child(props, "DateReceived"))

    body_text = ""
    if body:
        if "<html" in body.lower() or "<body" in body.lower():
            soup = BeautifulSoup(body, "html.parser")
            body_text = soup.get_text(separator="\n", strip=True)
        else:
            body_text = body

    return {
        "body_text": body_text[:10000],
        "body_html": body[:50000] if body and "<html" in body.lower() else "",
        "subject": subject or "",
        "sender": sender or "",
        "to": to or "",
        "cc": cc or "",
        "received_at": date or "",
    }


def main():
    log("=" * 50)
    log("邮件正文下载 v3")
    log("=" * 50)

    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    emails = index["emails"]
    log(f"索引中共 {len(emails)} 封邮件")

    # 找出需要下载的
    no_body = []
    for mid, email in emails.items():
        fp = email.get("filepath", "")
        if fp and Path(fp).exists():
            try:
                d = json.loads(Path(fp).read_text(encoding="utf-8"))
                if d.get("body_text"):
                    continue
            except Exception:
                pass
        no_body.append((mid, email))

    total = len(no_body)
    log(f"需要下载: {total} 封")
    if total == 0:
        log("全部已完成!")
        return

    config = ClientConfig.from_env()
    transport = EasTransport(config)
    provision(transport)

    # 先完整Sync
    synced_ids = full_sync(transport)

    done = 0
    failed = 0
    skipped = 0
    empty = 0
    last_save = 0
    status6_retry = []

    for i, (mid, email) in enumerate(no_body):
        subject = email.get("subject", "(无主题)")[:40]
        folder = email.get("folder", "other")
        filename = make_filename(email)
        filepath = ARCHIVE_DIR / folder / filename

        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        if mid not in synced_ids:
            skipped += 1
            continue

        try:
            body_data = download_body_raw(transport, mid)

            if not body_data.get("body_text"):
                empty += 1
                continue

            existing = {}
            if filepath.exists():
                try:
                    existing = json.loads(filepath.read_text(encoding="utf-8"))
                except Exception:
                    pass

            existing.update(body_data)
            existing["server_id"] = mid
            existing["category"] = email.get("category", "")
            existing["folder"] = folder

            filepath.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

            email["has_body"] = True
            email["filepath"] = str(filepath)
            index["emails"][mid] = email
            done += 1

            if (i + 1) % 50 == 0:
                log(f"[{i+1}/{total}] 成功={done} 空={empty} 失败={failed} 跳过={skipped} | {subject}")

            if done - last_save >= 50:
                save_index(index)
                last_save = done

            time.sleep(0.3)

        except ValueError as e:
            err = str(e)
            if "status 6" in err.lower() or "Fetch status 6" in err:
                status6_retry.append((mid, email))
            failed += 1
            if failed <= 10 or failed % 100 == 0:
                log(f"[{i+1}/{total}] 失败: {subject} - {err[:60]}")
        except Exception as e:
            failed += 1
            if failed <= 10 or failed % 100 == 0:
                log(f"[{i+1}/{total}] 异常: {subject} - {str(e)[:60]}")
            # 重连
            try:
                time.sleep(2)
                transport = EasTransport(config)
                provision(transport)
                synced_ids = full_sync(transport)
            except Exception:
                time.sleep(5)
                transport = EasTransport(config)
                provision(transport)

    # 第二轮: 重试 status 6 的邮件 (重新Sync后可能有新数据)
    if status6_retry:
        log(f"第二轮重试: {len(status6_retry)} 封 Status 6 邮件")
        synced_ids = full_sync(transport)
        retry_done = 0
        for mid, email in status6_retry:
            subject = email.get("subject", "(无主题)")[:40]
            folder = email.get("folder", "other")
            filename = make_filename(email)
            filepath = ARCHIVE_DIR / folder / filename
            try:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                body_data = download_body_raw(transport, mid)
                if body_data.get("body_text"):
                    existing = {}
                    if filepath.exists():
                        try: existing = json.loads(filepath.read_text(encoding="utf-8"))
                        except: pass
                    existing.update(body_data)
                    existing["server_id"] = mid
                    existing["category"] = email.get("category", "")
                    existing["folder"] = folder
                    filepath.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
                    email["has_body"] = True
                    email["filepath"] = str(filepath)
                    index["emails"][mid] = email
                    retry_done += 1
                    done += 1
                time.sleep(0.3)
            except Exception:
                pass
        log(f"第二轮重试成功: {retry_done}/{len(status6_retry)}")

    save_index(index)
    log("=" * 50)
    log(f"最终结果: 成功={done}, 正文为空={empty}, 失败={failed}, 跳过={skipped}, 总计={total}")
    log("=" * 50)


if __name__ == "__main__":
    main()
