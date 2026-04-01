# OpenClaw 邮件助手操作手册

> 基于 ResoftMailClient 项目，通过 EAS 协议连接公司办公邮箱  
> 作者：青梧  
> 日期：2026-03-30

---

## 一、项目概述

本项目通过 Exchange ActiveSync (EAS) 协议连接公司办公邮箱，实现：
- 📥 读取邮件（收件箱、文件夹）
- 📤 发送邮件（含抄送）
- 🔍 监控新邮件（识别需审批邮件）

**邮箱信息：**
- 邮箱：用户名@resoftcss.com.cn
- 服务器：mail.resoftcss.com.cn
- 用户名：RESOFT\\用户名（注意单反斜杠）
- 密码：【已删除，见 .env.eas 文件】
- 协议版本：EAS 14.0（读取）/ 12.1（发送）

---

## 二、环境配置

### 2.1 配置文件

文件位置：`/root/.openclaw/workspace/ResoftMailClient/.env.eas`

内容：
```bash
# EAS 办公邮箱配置
EAS_SERVER=mail.resoftcss.com.cn
EAS_USERNAME=RESOFT\用户名
EAS_PASSWORD=【你的密码】
EAS_ACCOUNT_EMAIL=用户名@resoftcss.com.cn
EAS_DEVICE_ID=你的设备ID
EAS_VERIFY_TLS=false
EAS_DEVICE_TYPE=iPhone
EAS_USER_AGENT=Apple-iOS/17.0
EAS_PROTOCOL_VERSION=14.0
```

**注意：**
- `EAS_USERNAME` 必须是 `RESOFT\用户名`（单反斜杠）
- `EAS_VERIFY_TLS=false` 因为服务器证书有问题
- `EAS_DEVICE_ID` 如果冲突可以改成其他自定义值

### 2.2 项目结构

```text
ResoftMailClient/
├── .env.eas              # 邮箱配置
├── src/eas_client/       # EAS 客户端代码
│   ├── eas/              # EAS 协议实现
│   ├── ews/              # EWS 协议实现
│   └── wbxml/            # WBXML 编解码
├── check_mail.py         # 检查邮件脚本
├── send_mail.py          # 发送邮件脚本
├── mail_daemon.py        # 邮件监控脚本
└── SOP.md                # 工作SOP（项目自带）
```

---

## 三、常用操作

### 3.1 检查最新邮件

```bash
cd /root/.openclaw/workspace/ResoftMailClient
PYTHONPATH="src:$PYTHONPATH" python3 check_mail.py
```

### 3.2 获取邮件详情

```python
import os
os.environ['EAS_SERVER'] = 'mail.resoftcss.com.cn'
os.environ['EAS_USERNAME'] = r'RESOFT\用户名'
os.environ['EAS_PASSWORD'] = '【你的密码】'
os.environ['EAS_VERIFY_TLS'] = 'false'
```

### 3.3 发送邮件

```python
msg["From"] = "用户名@resoftcss.com.cn"
msg["To"] = "收件人@resoftcss.com.cn"
msg["Cc"] = "抄送人@resoftcss.com.cn"  # 可选
```

---

## 四、工作流（龙哥的日常）

### 4.1 邮件检查节奏

- **频率**：每30分钟或按需
- **方式**：龙哥发“检查邮件”，我立即执行
- **输出**：分类汇总（需审批 / 普通邮件 / 已处理）

### 4.2 需审批邮件识别关键词

```python
APPROVAL_KEYWORDS = [
    "立项", "审批", "待办", "待审批", "打回", "报销",
    "项目结论", "变更", "验收", "合同", "预算", "紧急", "urgent"
]
```

---

## 五、常见问题

### 5.1 401 未授权

**原因：** 用户名格式错误  
**解决：** 确保使用 `RESOFT\用户名`（单反斜杠）

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
| `send_mail.py` | 发送邮件 |
| `mail_daemon.py` | 邮件监控 |
| `SOP.md` | 龙哥工作SOP（项目自带） |

---

## 七、联系人

- **龙哥**：工程交付中心管理人员
- **青梧**：AI助手，北大中文系+哲学系双博士（人设）
