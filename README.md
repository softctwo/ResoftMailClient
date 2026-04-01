# ResoftMailClient

ResoftMailClient is a cross-system Exchange mail client built around a Python `EAS` core and supporting automation scripts for sync, digest, and send workflows.

Current desktop scope:

- account sign-in and local persistence
- folder list
- message list
- message detail reading
- attachment metadata display only
- fixed Outlook-style workspace with independent pane scrolling
- resizable folder/message panes and pane collapse/restore
- non-mail folders handled safely with a protected empty state

Not in scope for the current desktop build:

- attachment download
- message sending
- multi-account support
- full-text search

The repository also keeps the low-level CLI and `EWS` probing commands used during
protocol verification.

## Environment

Set the connection values in the shell before running live commands:

```bash
export EAS_SERVER="mail.example.com"
export EAS_USERNAME="DOMAIN\\user"
export EAS_PASSWORD="..."
export EAS_ACCOUNT_EMAIL="user@example.com"
```

Optional:

```bash
export EAS_DEVICE_ID="PYEASCLI001"
export EAS_DEVICE_TYPE="PythonEAS"
export EAS_USER_AGENT="Apple-iOS/17.0"
```

Optional EWS override:

```bash
export EWS_ENDPOINT_PATH="/EWS/Exchange.asmx"
```

## CLI Commands

List folders:

```bash
python -m eas_client.cli folders
```

List recent messages for a collection:

```bash
python -m eas_client.cli messages --collection-id COLLECTION_ID
```

Read one message detail plus attachment metadata:

```bash
python -m eas_client.cli message-detail --collection-id COLLECTION_ID --server-id SERVER_ID
```

Emit machine-readable JSON for bridge callers:

```bash
python -m eas_client.cli folders --json
python -m eas_client.cli messages --collection-id COLLECTION_ID --json
python -m eas_client.cli message-detail --collection-id COLLECTION_ID --server-id SERVER_ID --json
```

Inspect the effective EAS mobile policy:

```bash
python -m eas_client.cli provision
```

List recent inbox messages through EWS:

```bash
python -m eas_client.cli ews-find-items --max-items 10
```

Fetch one message and its attachment metadata through EWS:

```bash
python -m eas_client.cli ews-get-item --item-id ITEM_ID
```

Download one EWS attachment by attachment id:

```bash
python -m eas_client.cli ews-download-attachment --attachment-id ATTACHMENT_ID --output tmp/file.bin
```

Dump raw WBXML from a live command:

```bash
python -m eas_client.cli dump-wbxml --command folder-sync --output tmp/foldersync.wbxml
```

Decode a saved WBXML file:

```bash
python -m eas_client.cli decode-wbxml tests/samples/foldersync_response.wbxml
```

## Desktop App

The desktop shell lives in `desktop/README.md`.

Quick start:

```bash
cd desktop
npm install
npm run tauri dev
```

Desktop persistence behavior:

- account settings are stored in the Tauri app config directory
- mailbox password is stored in the system keychain, not in `account.json`
- the latest folders, message lists, and message details are cached locally for faster cold starts

## Quick Scripts

推荐直接使用仓库根目录下的脚本，它们会自行读取 `.env.eas`，避免 shell `source .env.eas` 时把 `RESOFT\zhangyanlong` 中的反斜杠吞掉：

```bash
python3 check_mail.py
python3 mail_manager.py sync-incremental
python3 send_mail.py --to zhangyanlong@resoftcss.com.cn --subject "测试" --body "正文"
python3 send_mail.py --to zhangyanlong@resoftcss.com.cn --subject "测试" --body "正文" --attach ./tmp_attachment_test.txt
python3 mail_assistant.py poll --limit 30
python3 mail_assistant.py morning-report --limit 50 --hours 24
python3 mail_daemon.py
```

如果一定要在 shell 中导入环境变量，请不要使用 `source .env.eas` 这一方式。

定时能力建议：
- 每 10 分钟轮询新邮件：`run_mail_monitor.sh`
- 每天晨报：`run_morning_report.sh`

## Verification

Core verification commands:

```bash
PYTHONPATH=src pytest -q
cd desktop && npm run build
cd desktop/src-tauri && cargo test --test storage
cd desktop/src-tauri && cargo check
```
