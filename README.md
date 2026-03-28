# eas-mail-reader

极简版 Exchange ActiveSync 邮件客户端，支持读取、Ping 实时推送和发送邮件。

## 功能

- 📬 **邮件读取** — 通过 EAS Sync 协议读取收件箱邮件
- 🔔 **Ping 实时推送** — 监听新邮件（和 iPhone 邮件客户端相同机制）
- 📨 **SendMail** — 通过 EAS 协议发送邮件
- 📁 **文件夹管理** — 列出所有邮箱文件夹

## 快速开始

### 1. 配置

创建 `.env.eas` 文件：

```bash
EAS_SERVER=mail.example.com
EAS_USERNAME=DOMAIN\\username
EAS_PASSWORD=your-password
EAS_ACCOUNT_EMAIL=username@example.com
EAS_DEVICE_ID=OPENCLAW001
EAS_DEVICE_TYPE=iPhone
EAS_USER_AGENT=Apple-iOS/17.0
EAS_VERIFY_TLS=false
```

### 2. 安装依赖

```bash
pip install requests beautifulsoup4
```

### 3. 读取邮件

```python
from eas_reader.config import ClientConfig
from eas_reader.eas.commands import build_sync_request
from eas_reader.eas.parsers import parse_sync_response
from eas_reader.transport import EasTransport

config = ClientConfig.from_env()
transport = EasTransport(config)

# 同步收件箱
resp = transport.post("Sync", build_sync_request(
    collection_id="14", sync_key="0", window_size=10,
))
result = parse_sync_response(resp)
for msg in result.messages:
    print(f"{msg.sender}: {msg.subject}")
```

### 4. Ping 实时推送

```bash
python examples/ping_demo.py
```

### 5. 发送邮件

```bash
python examples/sendmail_demo.py user@example.com "主题" "正文"
```

或在代码中：

```python
from examples.sendmail_demo import send_email

send_email(
    to="user@example.com",
    subject="测试邮件",
    body="这是通过 EAS 协议发送的邮件",
)
```

## 技术细节

### EAS Ping 实时推送

Ping 机制模拟 iPhone 邮件客户端的"推送"功能：

1. 完整握手：Provision → FolderSync → Sync
2. 发送 Ping 请求（指定心跳间隔）
3. 服务器保持连接，新邮件到达时立即响应
4. 客户端收到通知后 Sync 拉取新邮件

### EAS SendMail

通过 EAS 12.1 协议发送 MIME 格式邮件：

1. 构造标准 MIME 邮件
2. Content-Type 设为 `message/rfc822`
3. POST 到 `/Microsoft-Server-ActiveSync?Cmd=SendMail`

## EAS 协议版本

- 支持 2.5 / 12.0 / 12.1 / 14.0 / 14.1
- Ping 和 Sync 使用 14.0
- SendMail 使用 12.1（MIME 格式）

## 许可证

MIT
