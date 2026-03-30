# EAS Mail Reader 故障排查与使用指南

> 记录连接 Exchange ActiveSync 邮箱过程中的常见问题及解决方案  
> 作者：青梧 (OpenClaw AI Assistant)  
> 日期：2026-03-30  
> 适用版本：eas-mail-reader v0.1.0

---

## 一、环境配置问题

### 1.1 用户名格式错误（401 Unauthorized）

**现象：**
```
401 Client Error: Unauthorized for url: https://mail.resoftcss.com.cn/...
```

**原因：**
- 用户名格式不正确
- Exchange 服务器需要 `域名\用户名` 格式（单反斜杠）

**解决方案：**
```bash
# 正确格式
EAS_USERNAME=RESOFT\zhangyanlong

# 错误格式示例
EAS_USERNAME=zhangyanlong@resoftcss.com.cn  # ❌ 邮箱格式
EAS_USERNAME=RESOFTCSS/zhangyanlong         # ❌ 域名错误
EAS_USERNAME=RESOFT\\zhangyanlong          # ❌ 双反斜杠（转义后变成单反斜杠）
```

**注意：** 在 `.env.eas` 文件中，反斜杠不需要转义，直接写 `RESOFT\zhangyanlong` 即可。

### 1.2 SSL 证书验证失败

**现象：**
```
SSLCertVerificationError: certificate verify failed
```

**解决方案：**
在 `.env.eas` 中禁用 TLS 验证：
```bash
EAS_VERIFY_TLS=false
```

**注意：** 生产环境建议配置正确的 CA 证书，而非禁用验证。

---

## 二、模块导入问题

### 2.1 ModuleNotFoundError: No module named 'eas_client'

**现象：**
```
ModuleNotFoundError: No module named 'eas_client'
# 或
ImportError: cannot import name 'AttachmentFetchResult' from 'eas_client.eas.models'
```

**原因：**
- 项目使用 `eas_reader` 作为源码目录，但代码中导入使用 `eas_client`
- 符号链接或路径配置不正确

**解决方案：**

**方案 A：创建符号链接（推荐）**
```bash
cd src
ln -s eas_reader eas_client
```

**方案 B：统一修改为 eas_reader**
```bash
# 将所有 from eas_client. 替换为 from eas_reader.
find src -name "*.py" -exec sed -i 's/from eas_client\./from eas_reader./g' {} \;
```

**方案 C：复制目录**
```bash
cd src
cp -r eas_reader eas_client
```

### 2.2 isinstance 检查失败

**现象：**
代码逻辑正确，但 `isinstance(child, WbxmlElement)` 返回 `False`

**原因：**
- Python 将 `eas_client.wbxml.models.WbxmlElement` 和 `eas_reader.wbxml.models.WbxmlElement` 视为不同类
- 模块路径不一致导致

**解决方案：**
确保所有导入统一使用 `eas_client`（通过符号链接或复制目录）。

---

## 三、数据模型问题

### 3.1 MessageDetail 字段缺失

**现象：**
```
TypeError: MessageDetail.__init__() got an unexpected keyword argument 'collection_id'
```

**原因：**
`src/eas_client/eas/models.py` 中的 `MessageDetail` 类缺少必要字段

**解决方案：**
更新 `MessageDetail` 类定义：
```python
@dataclass(frozen=True)
class MessageDetail:
    server_id: str | None = None
    collection_id: str | None = None
    subject: str | None = None
    sender: str | None = None
    to: str | None = None
    received_at: str | None = None
    body: str | None = None
    body_type: str | None = None
    attachments: list[AttachmentSummary] | None = None
```

### 3.2 ProvisionResponse 字段缺失

**现象：**
发送邮件时解析 Provision 响应失败

**解决方案：**
更新 `ProvisionResponse` 类：
```python
@dataclass(frozen=True)
class ProvisionResponse:
    status: str | None = None
    policy_type: str | None = None
    policy_key: str | None = None
    settings: dict[str, str] | None = None
```

---

## 四、邮件发送问题

### 4.1 发送邮件返回 401

**现象：**
读取邮件正常，但发送邮件返回 401

**原因：**
- 发送邮件需要 PolicyKey
- 协议版本不正确

**解决方案：**

**步骤 1：获取 PolicyKey**
```python
from eas_client.eas.commands import build_provision_request
import re

# 第一次 Provision
resp = transport.post("Provision", build_provision_request())
pk1 = re.findall(rb'\x03(\d{8,})\x00', resp)[0].decode()

# 第二次 Provision
resp = transport.post("Provision", build_provision_request(policy_key=pk1))
pk2 = re.findall(rb'\x03(\d{8,})\x00', resp)[-1].decode()
```

**步骤 2：使用 EAS 12.1 协议发送**
```python
headers = {
    "MS-ASProtocolVersion": "12.1",  # 发送用 12.1
    "X-MS-PolicyKey": pk2,
    "Content-Type": "message/rfc822",
    # ...
}
```

**注意：** 读取邮件可用 14.0，但发送邮件建议用 12.1 兼容性更好。

### 4.2 邮件正文编码问题

**现象：**
中文邮件正文显示乱码

**解决方案：**
使用 `MIMEText` 并指定编码：
```python
from email.mime.text import MIMEText

msg = MIMEText(body, "plain", "utf-8")
msg["From"] = from_email
msg["To"] = to
msg["Subject"] = subject
```

---

## 五、邮件解析问题

### 5.1 WBXML 解析失败

**现象：**
```
ValueError: Missing text child tag 'Status' under 'FolderSync'
```

**原因：**
- 响应解析器期望的标签结构与实际响应不符
- 某些字段在特定响应中可能不存在

**解决方案：**
使用可选字段解析：
```python
# 使用 _optional_child_text 而非 _require_child_text
status = _optional_child_text(element, "Status")
if status is None:
    # 处理缺失情况
    pass
```

### 5.2 邮件列表为空

**现象：**
同步返回 0 封邮件

**原因：**
- 第一次同步只返回同步密钥，不返回邮件
- 需要使用返回的 sync_key 进行第二次同步

**解决方案：**
```python
# 第一次同步 - 获取密钥
resp = transport.post('Sync', build_sync_request(collection_id=inbox_id, sync_key='0'))
sync1 = parse_sync_response(resp)

# 第二次同步 - 获取实际邮件
if sync1.sync_key and sync1.sync_key != '0':
    resp = transport.post('Sync', build_sync_request(
        collection_id=inbox_id, 
        sync_key=sync1.sync_key,  # 使用返回的密钥
        window_size=50
    ))
    sync2 = parse_sync_response(resp)
    # sync2.messages 包含实际邮件
```

---

## 六、完整配置示例

### 6.1 .env.eas 配置文件

```bash
# EAS 办公邮箱配置
EAS_SERVER=mail.resoftcss.com.cn
EAS_USERNAME=RESOFT\zhangyanlong
EAS_PASSWORD=你的密码
EAS_ACCOUNT_EMAIL=zhangyanlong@resoftcss.com.cn
EAS_DEVICE_ID=PYEASCLI001
EAS_VERIFY_TLS=false
EAS_DEVICE_TYPE=iPhone
EAS_USER_AGENT=Apple-iOS/17.0
EAS_PROTOCOL_VERSION=14.0
```

### 6.2 快速测试脚本

```python
#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# 加载环境变量
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
from eas_client.eas.commands import build_folder_sync_request, build_sync_request
from eas_client.eas.parsers import parse_folder_sync_response, parse_sync_response
from eas_client.transport import EasTransport

config = ClientConfig.from_env()
transport = EasTransport(config)

# 获取收件箱
resp = transport.post('FolderSync', build_folder_sync_request(sync_key='0'))
folders = parse_folder_sync_response(resp)

inbox_id = None
for f in folders.folders:
    if str(f.folder_type) == '2':
        inbox_id = f.server_id
        break

# 获取邮件
resp = transport.post('Sync', build_sync_request(collection_id=inbox_id, sync_key='0'))
sync1 = parse_sync_response(resp)

if sync1.sync_key and sync1.sync_key != '0':
    resp = transport.post('Sync', build_sync_request(
        collection_id=inbox_id, sync_key=sync1.sync_key, window_size=10))
    sync2 = parse_sync_response(resp)
    
    print(f"获取到 {len(sync2.messages)} 封邮件")
    for msg in sync2.messages:
        print(f"- {msg.subject} | {msg.sender}")
```

---

## 七、调试技巧

### 7.1 查看原始 WBXML 响应

```python
resp = transport.post('FolderSync', build_folder_sync_request(sync_key='0'))
print(f"响应长度: {len(resp)}")
print(f"响应内容 (hex): {resp.hex()}")
```

### 7.2 检查环境变量加载

```python
import os
print(f"EAS_USERNAME: {os.environ.get('EAS_USERNAME')}")
print(f"EAS_SERVER: {os.environ.get('EAS_SERVER')}")
```

### 7.3 使用 curl 测试连接

```bash
# 测试 Basic Auth
curl -k -u "RESOFT/zhangyanlong:密码" \
  -H "User-Agent: Apple-iOS/17.0" \
  "https://mail.resoftcss.com.cn/Microsoft-Server-ActiveSync?Cmd=FolderSync&User=..."
```

---

## 八、相关文档

- `README.md` - 项目基本说明
- `SOP.md` - 工作SOP（项目自带）
- `OPERATION_MANUAL.md` - 操作手册（OpenClaw使用场景）
- `TROUBLESHOOTING.md` - 本文档

---

## 九、更新日志

- **2026-03-30** - 初始版本，记录连接张彦龙办公邮箱过程中的问题及解决方案

---

**如有问题，请参考本文档或联系项目维护者。**
