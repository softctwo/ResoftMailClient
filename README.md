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

## Mail Timezone

邮件原始时间通常来自 Exchange 的 UTC 时间（如 `2026-04-01T09:44:04.002Z`）。
当前项目已统一在展示层转换为 **北京时间（Asia/Shanghai）**：

- 用户可见字段：`received_at`（北京时间）
- 保留原始字段：`received_at_raw`（UTC 原始值）

这样既能保证展示时间正确，也不会影响内部去重和兼容逻辑。

## Attachment Sending

`send_mail.py` 已支持普通文本邮件和带附件邮件发送。

普通发信：

```bash
python3 send_mail.py --to someone@example.com --subject "主题" --body "正文"
```

带附件发信：

```bash
python3 send_mail.py --to someone@example.com --subject "主题" --body "正文" --attach ./file1.pdf
```

多附件：

```bash
python3 send_mail.py --to someone@example.com --subject "主题" --body "正文" --attach ./file1.pdf --attach ./file2.xlsx
```

## Morning Digest

`mail_assistant.py morning-report` 用于生成晨报，默认可汇总最近 24 小时的重要邮件，并输出：

- 待关注事项
- 报销/打回提醒
- 客户到访/商务协同
- 分类统计
- 重要邮件摘要

示例：

```bash
python3 mail_assistant.py morning-report --limit 50 --hours 24
```

晨报文件会写入：

```bash
assistant_data/reports/morning_digest_YYYY-MM-DD.md
```

## Scheduled Polling

项目已内置轮询与晨报脚本，适合配合 OpenClaw cron 使用，不依赖 macOS 系统级调度。

建议任务：
- 每 10 分钟轮询新邮件：`run_mail_monitor.sh`
- 每天固定时间生成晨报：`run_morning_report.sh`

手动启动轮询守护：

```bash
python3 mail_daemon.py
```

轮询脚本会：
- 拉取最新邮件
- 自动分类
- 识别新邮件
- 预留飞书通知能力

## Verification

Core verification commands:

```bash
PYTHONPATH=src pytest -q
cd desktop && npm run build
cd desktop/src-tauri && cargo test --test storage
cd desktop/src-tauri && cargo check
```
