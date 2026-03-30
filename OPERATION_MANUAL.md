# OpenClaw 邮件助手操作手册

> 基于 eas-mail-reader 项目，通过 EAS 协议连接张彦龙办公邮箱  
> 作者：青梧  
> 日期：2026-03-30

---

## 一、项目概述

本项目通过 Exchange ActiveSync (EAS) 协议连接张彦龙（龙哥）的办公邮箱，实现：
- 📥 读取邮件（收件箱、文件夹）
- 📤 发送邮件（含抄送）
- 🔍 监控新邮件（识别需审批邮件）

**邮箱信息：**
- 邮箱：zhangyanlong@resoftcss.com.cn
- 服务器：mail.resoftcss.com.cn
- 用户名：RESOFT\\zhangyanlong（注意单反斜杠）
- 密码：【已删除，见 .env.eas 文件】
- 协议版本：EAS 14.0（读取）/ 12.1（发送）

---

## 二、环境配置

### 2.1 配置文件

文件位置：`/root/.openclaw/workspace/eas-mail-reader/.env.eas`

内容：
```bash
# EAS 办公邮箱配置
EAS_SERVER=mail.resoftcss.com.cn
EAS_USERNAME=RESOFT\zhangyanlong
EAS_PASSWORD=【你的密码】
EAS_ACCOUNT_EMAIL=
EAS_DEVICE_ID=PYEASCLI002
EAS_VERIFY_TLS=false
EAS_DEVICE_TYPE=iPhone
EAS_USER_AGENT=Apple-iOS/17.0
EAS_PROTOCOL_VERSION=14.0
```

**注意：**
- `EAS_USERNAME` 必须是 `RESOFT\zhangyanlong`（单反斜杠）
- `EAS_VERIFY_TLS=false` 因为服务器证书有问题
- `EAS_DEVICE_ID` 如果冲突可以改成 PYEASCLI003 等

### 2.2 项目结构

```
eas-mail-reader/
├── .env.eas              # 邮箱配置
├── src/eas_client/       # EAS 客户端代码
│   ├── eas/              # EAS 协议实现
│   ├── ews/              # EWS 协议实现
│   └── wbxml/            # WBXML 编解码
├── check_mail.py         # 检查邮件脚本
├── send_to_lilong_v2.py  # 发送邮件示例
├── mail_monitor.py       # 邮件监控脚本
└── SOP.md                # 工作SOP（项目自带）
```

---

## 三、常用操作

### 3.1 检查最新邮件

```bash
cd /root/.openclaw/workspace/eas-mail-reader
PYTHONPATH="src:$PYTHONPATH" python3 check_mail.py
```

输出示例：
```json
{
  "timestamp": "2026-03-30 15:55:15",
  "total": 10,
  "new_count": 2,
  "new_messages": [
    {"subject": "【工程立项结论】...", "sender": "平梦琪", ...}
  ]
}
```

### 3.2 获取邮件详情

```python
# 在 Python 中执行
import os
os.environ['EAS_SERVER'] = 'mail.resoftcss.com.cn'
os.environ['EAS_USERNAME'] = r'RESOFT\zhangyanlong'
os.environ['EAS_PASSWORD'] = '【你的密码】'
os.environ['EAS_VERIFY_TLS'] = 'false'

from eas_client.config import ClientConfig
from eas_client.eas.commands import build_item_operations_message_request
from eas_client.eas.parsers import parse_item_operations_message_response
from eas_client.transport import EasTransport

config = ClientConfig.from_env()
transport = EasTransport(config)

# 获取邮件详情（collection_id:server_id）
resp = transport.post('ItemOperations', 
    build_item_operations_message_request('14', '14:10'))
result = parse_item_operations_message_response(resp)
print(result.body)  # 邮件正文
```

### 3.3 发送邮件

**方式一：使用示例脚本**

```bash
cd /root/.openclaw/workspace/eas-mail-reader
PYTHONPATH="src:$PYTHONPATH" python3 send_to_lilong_v2.py
```

**方式二：自定义发送**

```python
import os
from email.mime.text import MIMEText
import base64
import requests
from urllib.parse import urlencode

os.environ['EAS_SERVER'] = 'mail.resoftcss.com.cn'
os.environ['EAS_USERNAME'] = r'RESOFT\zhangyanlong'
os.environ['EAS_PASSWORD'] = '【你的密码】'
os.environ['EAS_VERIFY_TLS'] = 'false'

sys.path.insert(0, 'src')
from eas_client.config import ClientConfig
from eas_client.eas.commands import build_provision_request
from eas_client.transport import EasTransport
import re

config = ClientConfig.from_env()
transport = EasTransport(config)

# 获取 PolicyKey
resp = transport.post("Provision", build_provision_request())
pk1 = re.findall(rb'\x03(\d{8,})\x00', resp)[0].decode()
resp = transport.post("Provision", build_provision_request(policy_key=pk1))
pk2 = re.findall(rb'\x03(\d{8,})\x00', resp)[-1].decode()

# 构造邮件
msg = MIMEText("邮件正文", "plain", "utf-8")
msg["From"] = "zhangyanlong@resoftcss.com.cn"
msg["To"] = "收件人@resoftcss.com.cn"
msg["Cc"] = "抄送人@resoftcss.com.cn"  # 可选
msg["Subject"] = "邮件主题"

# 发送
auth = f'Basic {base64.b64encode(f"{config.username}:{config.password}".encode()).decode()}'
params = {
    "Cmd": "SendMail",
    "User": config.username,
    "DeviceId": config.device_id,
    "DeviceType": config.device_type,
    "SaveInSentItems": "T"
}
url = f'{config.base_url}?{urlencode(params)}'

headers = {
    "Authorization": auth,
    "MS-ASProtocolVersion": "12.1",
    "Content-Type": "message/rfc822",
    "User-Agent": config.user_agent,
    "X-MS-PolicyKey": pk2,
}

resp = requests.post(url, data=msg.as_bytes(), headers=headers, 
                     timeout=30, verify=config.verify_tls)
print("发送成功" if resp.status_code == 200 else f"失败: {resp.status_code}")
```

---

## 四、工作流（龙哥的日常）

### 4.1 邮件检查节奏

- **频率**：每30分钟或按需
- **方式**：龙哥发"检查邮件"，我立即执行
- **输出**：分类汇总（需审批 / 普通邮件 / 已处理）

### 4.2 需审批邮件识别关键词

```python
APPROVAL_KEYWORDS = [
    "立项", "审批", "待办", "待审批", "打回", "报销",
    "项目结论", "变更", "验收", "合同", "预算", "紧急", "urgent"
]
```

### 4.3 典型场景

**场景1：项目立项审批**
- 识别：主题含"立项结论"
- 动作：提取项目编号、金额、利润率、负责人
- 输出：结构化摘要供决策

**场景2：报销打回**
- 识别：主题含"报销"+"打回"
- 动作：立即标记高优先级
- 输出：提醒处理

**场景3：发送询问邮件**
- 模板：send_to_lilong_v2.py
- 要点：明确决策需求、分点列出、设定回复时间
- 抄送：龙哥自己

---

## 五、常见问题

### 5.1 401 未授权

**原因：** 用户名格式错误  
**解决：** 确保使用 `RESOFT\zhangyanlong`（单反斜杠）

### 5.2 SSL 证书错误

**解决：** `.env.eas` 中设置 `EAS_VERIFY_TLS=false`

### 5.3 邮件正文解析失败

**原因：** WBXML 解析器模块路径问题  
**解决：** 确保使用 `PYTHONPATH="src:$PYTHONPATH"`

### 5.4 发送邮件失败

**检查：**
1. PolicyKey 是否获取成功
2. 协议版本是否为 12.1（发送邮件用 12.1，读取用 14.0）
3. Content-Type 是否为 `message/rfc822`

---

## 六、关键文件清单

| 文件 | 用途 |
|:---|:---|
| `.env.eas` | 邮箱配置 |
| `check_mail.py` | 检查邮件 |
| `send_to_lilong_v2.py` | 发送邮件示例 |
| `mail_monitor.py` | 邮件监控（待配置 webhook） |
| `SOP.md` | 龙哥工作SOP（项目自带） |

---

## 七、联系人

- **龙哥**：张彦龙，工程交付中心管理人员
- **青梧**：AI助手，北大中文系+哲学系双博士（人设）
- **日常**：龙哥发"检查邮件"，我立即执行并汇报

---

**最后更新：2026-03-30**  
**如有问题，直接问龙哥或青梧**
