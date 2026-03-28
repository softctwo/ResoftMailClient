#!/usr/bin/env python3
"""
重新下载全部无正文邮件 - 用当前有效的server_id
根因: Exchange server_id是动态的，旧ID失效后返回Status 6
修复: 先Sync获取当前server_id映射，再下载
"""
import os, sys, json, time, warnings, re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
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
from eas_client.eas.parsers import parse_sync_response
from eas_client.transport import EasTransport
from eas_client.wbxml import decode_document, WbxmlElement, WbxmlText
from bs4 import BeautifulSoup

ARCHIVE_DIR = Path(__file__).parent / "mail_archive"
INDEX_FILE = ARCHIVE_DIR / "index" / "mail_index.json"
LOG_FILE = "/tmp/body_redownload.log"
COLLECTION_ID = "14"


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def provision(transport):
    resp = transport.post("Provision", build_provision_request())
    pk1 = re.findall(rb'\x03(\d{8,})\x00', resp)[0].decode()
    resp = transport.post("Provision", build_provision_request(policy_key=pk1))
    pk2 = re.findall(rb'\x03(\d{8,})\x00', resp)[-1].decode()
    return pk2


def full_sync(transport):
    all_msgs = []
    resp = transport.post("Sync", build_sync_request(
        collection_id=COLLECTION_ID, sync_key="0", window_size=256,
    ))
    sync1 = parse_sync_response(resp)
    all_msgs.extend(sync1.messages)
    sk = sync1.sync_key
    while sk and sk != "0":
        try:
            resp = transport.post("Sync", build_sync_request(
                collection_id=COLLECTION_ID, sync_key=sk, window_size=256,
            ))
            if not resp:
                break
            sync_n = parse_sync_response(resp)
            all_msgs.extend(sync_n.messages)
            if len(sync_n.messages) == 0 or sync_n.sync_key == sk:
                break
            sk = sync_n.sync_key
            if len(all_msgs) % 500 == 0:
                log(f"  Sync中: {len(all_msgs)} 封")
        except Exception as e:
            log(f"  Sync异常: {e}")
            break
    return all_msgs


def download_body(transport, server_id):
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
    to_addr = get_text(find_child(props, "To"))
    cc_addr = get_text(find_child(props, "Cc"))

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
        "to": to_addr or "",
        "cc": cc_addr or "",
    }


def main():
    log("=" * 50)
    log("重新下载无正文邮件 (使用当前有效server_id)")
    log("=" * 50)

    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    emails = index["emails"]
    total = len(emails)
    has_body = sum(1 for e in emails.values() if e.get("has_body"))
    no_body_emails = {mid: e for mid, e in emails.items() if not e.get("has_body")}

    log(f"索引共 {total} 封, 有正文 {has_body}, 无正文 {len(no_body_emails)}")

    if not no_body_emails:
        log("全部已有正文!")
        return

    # 用subject+sender+received_at建立去重key映射
    no_body_by_key = {}
    for mid, e in no_body_emails.items():
        key = f"{e.get('subject','')}|{e.get('sender','')}|{e.get('received_at','')}"
        no_body_by_key[key] = (mid, e)

    log(f"无正文邮件去重key: {len(no_body_by_key)}")

    # 连接服务器
    config = ClientConfig.from_env()
    transport = EasTransport(config)
    provision(transport)

    # 全量Sync
    log("开始全量Sync获取当前server_id...")
    sync_msgs = full_sync(transport)
    log(f"Sync完成: {len(sync_msgs)} 封")

    # 匹配：找到无正文邮件在当前Sync中的最新server_id
    match_count = 0
    download_list = []  # (current_server_id, old_mid, email_data)

    for m in sync_msgs:
        key = f"{m.subject or ''}|{m.sender or ''}|{m.received_at or ''}"
        if key in no_body_by_key:
            old_mid, email_data = no_body_by_key[key]
            current_sid = m.server_id
            download_list.append((current_sid, old_mid, email_data, key))
            match_count += 1

    log(f"匹配到 {match_count}/{len(no_body_by_key)} 封无正文邮件")

    if not download_list:
        log("无可下载邮件")
        return

    # 统计未匹配的
    matched_keys = set(item[3] for item in download_list)
    unmatched = [k for k in no_body_by_key if k not in matched_keys]
    if unmatched:
        log(f"未匹配 {len(unmatched)} 封（Sync范围外）:")
        for k in unmatched[:5]:
            mid, e = no_body_by_key[k]
            log(f"  {e.get('subject','')[:40]} ({e.get('received_at','')[:10]})")

    # 开始下载
    done = 0
    empty = 0
    failed = 0
    last_save = 0

    for i, (current_sid, old_mid, email_data, key) in enumerate(download_list):
        subject = email_data.get("subject", "(无主题)")[:40]
        folder = email_data.get("folder", "other")

        try:
            body_data = download_body(transport, current_sid)

            if not body_data.get("body_text"):
                empty += 1
                if empty <= 5:
                    log(f"[{i+1}/{len(download_list)}] 正文为空: {subject}")
                continue

            # 更新server_id到当前值
            email_data["server_id"] = current_sid
            email_data["has_body"] = True
            email_data["to"] = body_data.get("to", "")
            email_data["cc"] = body_data.get("cc", "")

            # 删除旧ID的记录
            if old_mid in index["emails"] and old_mid != current_sid:
                del index["emails"][old_mid]

            # 写入index
            index["emails"][current_sid] = email_data

            # 保存文件
            filename = email_data.get("filename", "")
            if not filename:
                mid_str = current_sid.replace(":", "_")
                subj = subject[:30].replace("/", "_").replace("\\", "_")
                filename = f"{mid_str}_{subj}.json"
                email_data["filename"] = filename

            filepath = ARCHIVE_DIR / folder / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)

            full_data = {**email_data, **body_data}
            filepath.write_text(json.dumps(full_data, ensure_ascii=False, indent=2), encoding="utf-8")

            done += 1

            if (i + 1) % 50 == 0:
                log(f"[{i+1}/{len(download_list)}] 成功={done} 空={empty} 失败={failed}")

            if done - last_save >= 50:
                # 保存index
                tmp = INDEX_FILE.with_suffix(".tmp")
                tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
                tmp.rename(INDEX_FILE)
                last_save = done

            time.sleep(0.3)

        except Exception as e:
            failed += 1
            if failed <= 10 or failed % 100 == 0:
                log(f"[{i+1}/{len(download_list)}] 失败: {subject} - {str(e)[:60]}")
            # 重连
            try:
                time.sleep(2)
                transport = EasTransport(config)
                provision(transport)
            except Exception:
                time.sleep(5)
                transport = EasTransport(config)
                provision(transport)

    # 最终保存index
    index["stats"]["total"] = len(index["emails"])
    index["stats"]["last_sync"] = datetime.now().isoformat()
    tmp = INDEX_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(INDEX_FILE)

    log("=" * 50)
    log(f"最终结果: 成功={done}, 正文为空={empty}, 失败={failed}, 总计={len(download_list)}")

    # 更新统计
    final_has = sum(1 for e in index["emails"].values() if e.get("has_body"))
    log(f"当前有正文: {final_has}/{len(index['emails'])}")
    log("=" * 50)


if __name__ == "__main__":
    main()
