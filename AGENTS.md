# ResoftMailClient — Agent Guide

> 本文件面向 AI Coding Agent 读者。项目所有注释和文档均以中文为主。

## 项目概述

ResoftMailClient 是一个面向公司 Exchange / EAS 邮箱场景的 Python 邮件助手项目，用于：

- 通过 Exchange ActiveSync (EAS) 和 EWS 协议收发邮件
- 附件发送与下载
- 邮件时间统一按北京时间（Asia/Shanghai）展示
- 晨报生成、定时轮询与智能分析
- 本地邮件归档、分类与索引

项目当前无任何桌面端或 Rust 代码，纯 Python 实现。

## 技术栈

- **语言**: Python >= 3.11
- **构建系统**: setuptools（`pyproject.toml`）
- **核心依赖**: `requests>=2.31`, `beautifulsoup4>=4.12`
- **测试框架**: pytest
- **调度集成**: OpenClaw cron（外部，非系统级 cron）

## 项目结构

```text
ResoftMailClient/
├── src/eas_client/              # EAS/EWS 核心客户端库
│   ├── __init__.py
│   ├── config.py                # ClientConfig（环境变量配置）
│   ├── transport.py             # EasTransport（HTTP + Basic Auth）
│   ├── cli.py                   # 命令行工具 eas-cli
│   ├── eas/                     # EAS 协议实现
│   │   ├── commands.py          # WBXML 请求构建（FolderSync, Sync, ItemOperations, Provision, Ping, SendMail）
│   │   ├── parsers.py           # WBXML 响应解析
│   │   ├── models.py            # EAS 数据模型（MessageSummary, SyncResponse, ProvisionResponse 等）
│   │   └── encoder.py           # WBXML 编码器
│   ├── ews/                     # EWS 协议实现
│   │   ├── client.py            # EwsClient（SOAP 请求封装）
│   │   ├── soap.py              # SOAP Envelope 模板构建
│   │   ├── parsers.py           # EWS XML 响应解析
│   │   └── models.py            # EWS 数据模型
│   └── wbxml/                   # WBXML 编解码器
│       ├── decoder.py           # WBXML 解码器
│       ├── encoder.py           # WBXML 编码器
│       ├── codepages.py         # EAS Code Page 映射表
│       ├── models.py            # WbxmlDocument, WbxmlElement, WbxmlText, WbxmlOpaque 等
│       └── reader.py            # ByteReader
│
├── check_mail.py                # 检查新邮件并输出 JSON
├── send_mail.py                 # 发送邮件（支持附件、抄送）
├── mail_assistant.py            # 邮件助手：poll / morning-report / alerts / intelligence / reminders
├── mail_manager.py              # 邮件管理器：sync-all / sync-incremental / report / stats / search
├── mail_daemon.py               # 守护进程：每 10 分钟轮询 + 飞书通知
├── analysis_rules.py            # 邮件分类规则、立项结构化提取、日期预警、产品线匹配
├── mail_actions.py              # 构建 alerts / intelligence / reminders 输出
├── time_utils.py                # 时间解析与北京时间转换
├── eas_env.py                   # 加载 .env.eas 并自动将 src/ 加入 sys.path
├── download_all_bodies.py       # 批量下载全部邮件正文（健壮版）
├── redownload_bodies.py         # 针对无正文邮件重新下载（修复动态 server_id 问题）
│
├── examples/                    # 示例脚本
│   ├── ping_demo.py             # EAS Ping 实时推送示例
│   └── sendmail_demo.py         # EAS 发送邮件示例
│
├── tests/                       # 测试用例
│   ├── test_package_layout.py   # 包导入基础测试
│   ├── test_mail_assistant.py   # mail_assistant 单元测试
│   └── samples/                 # WBXML 样本文件
│
├── docs/superpowers/plans/      # 功能实现计划
├── pyproject.toml               # 项目配置与 pytest 配置
├── .env.eas.example             # 环境变量配置模板
├── run_mail_monitor.sh          # OpenClaw cron 轮询脚本
└── run_morning_report.sh        # OpenClaw cron 晨报脚本
```

## 环境配置

所有连接参数通过仓库根目录的 `.env.eas` 配置（已加入 `.gitignore`，禁止提交到版本库）：

```bash
EAS_SERVER=mail.resoftcss.com.cn
EAS_USERNAME=RESOFT\用户名
EAS_PASSWORD=你的密码
EAS_ACCOUNT_EMAIL=用户名@resoftcss.com.cn
EAS_DEVICE_ID=你的设备ID
EAS_VERIFY_TLS=false
EAS_DEVICE_TYPE=iPhone
EAS_USER_AGENT=Apple-iOS/17.0
EAS_PROTOCOL_VERSION=14.0
```

**注意：**
- `EAS_USERNAME` 必须使用 `RESOFT\用户名`（单反斜杠）。`.env.eas` 中不要对反斜杠做转义。
- `EAS_VERIFY_TLS=false` 是因为服务器证书存在问题；生产环境建议配置正确 CA 证书。
- 不建议直接 `source .env.eas`，避免 shell 吃掉反斜杠。

## 构建、测试与开发命令

### 运行测试

```bash
PYTHONPATH=src pytest -q
```

或（`pyproject.toml` 已配置 `pythonpath = ["src"]`）：

```bash
pytest -q
```

### 命令行工具（核心库）

```bash
PYTHONPATH=src python -m eas_client.cli folders --json
PYTHONPATH=src python -m eas_client.cli messages --collection-id <id> --json
PYTHONPATH=src python -m eas_client.cli message-detail --collection-id <id> --server-id <id> --json
PYTHONPATH=src python -m eas_client.cli provision
PYTHONPATH=src python -m eas_client.cli ews-find-items --max-items 10
PYTHONPATH=src python -m eas_client.cli decode-wbxml <path>
```

### 应用层脚本

```bash
# 检查邮件
python3 check_mail.py

# 发送邮件
python3 send_mail.py --to someone@example.com --subject "主题" --body "正文" --attach ./file.pdf

# 邮件助手
python3 mail_assistant.py poll --limit 30
python3 mail_assistant.py morning-report --limit 50 --hours 24
python3 mail_assistant.py alerts --limit 30
python3 mail_assistant.py intelligence --limit 50
python3 mail_assistant.py reminders --limit 50

# 邮件管理器
python3 mail_manager.py sync-incremental
python3 mail_manager.py sync-all --max 500
python3 mail_manager.py stats
python3 mail_manager.py report --type daily
python3 mail_manager.py search --query "关键词"
```

### 守护进程

```bash
python3 mail_daemon.py          # 前台轮询
```

### OpenClaw Cron 脚本

- 每 10 分钟轮询：`run_mail_monitor.sh`
- 每日晨报：`run_morning_report.sh`

## 代码风格与命名规范

- **缩进**: 4 空格
- **命名**: Python 使用 `snake_case`；类名使用 `PascalCase`
- **类型提示**: 核心库（`src/eas_client/`）已广泛使用类型提示，新增代码请保持
- **导入习惯**: 文件头常写 `from __future__ import annotations`
- **CLI 命令名**: 使用连字符，如 `message-detail`、`ews-find-items`
- **注释与文档**: 以中文为主

## 核心架构约定

### 1. 模块导入路径

根目录脚本（如 `mail_assistant.py`、`check_mail.py`）不依赖 `PYTHONPATH` 环境变量，而是通过 `eas_env.py` 完成两件事：

```python
from eas_env import add_import_path, load_env
load_env()          # 加载 .env.eas
add_import_path()   # 将 src/ 加入 sys.path
```

**Agent 修改根目录脚本时，必须保留这两个调用，否则会出现 `ModuleNotFoundError: No module named 'eas_client'`。**

### 2. EAS 协议版本

- **读取邮件**: `14.0`
- **发送邮件**: `12.1`（兼容性更好）

发送邮件时必须先完成两次 `Provision` 握手获取 `PolicyKey`，并在请求头中携带 `X-MS-PolicyKey`。

### 3. 时间处理

Exchange 返回的时间通常为 UTC（如 `2026-04-01T09:44:04.002Z`）。项目统一转换为 **北京时间** 展示：

- `received_at`: 北京时间字符串，用于展示
- `received_at_raw`: 原始 UTC 时间，用于内部兼容和去重

相关工具在 `time_utils.py` 中：
- `parse_mail_datetime(raw)`
- `to_beijing_time(raw)`
- `SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")`

### 4. Exchange server_id 动态性

Exchange 的 `server_id` 不是固定的，会随同步变化。因此项目中的去重逻辑不使用 `server_id`，而是使用 **`subject + sender + received_at` 三元组** 作为去重键。这一点在 `mail_manager.py`、`redownload_bodies.py` 中均有体现。

### 5. 邮件分类体系

`analysis_rules.py` 和 `mail_manager.py` 中维护了两套分类规则，核心类别包括：

| 类别 | 关键词示例 | 优先级 |
|---|---|---|
| 财务报销 | 报销、待办、打回 | 🔴 |
| 立项审批 | 立项、立项结论 | 🟠 |
| 商务协同 | 客户到访、提前进场 | 🟠 |
| 监管制度 | 制度、监管、EAST、反洗钱 | 🟡 |
| 经营统计 | 收入、合同负债 | 🟡 |
| 周报日报 | 周报、日报、月报 | 🟢 |
| 其他 | — | ⚪ |

### 6. 数据目录

运行时生成的数据默认放在以下目录，均已加入 `.gitignore`：

- `assistant_data/`: 助手状态、缓存、晨报报告
- `mail_archive/`: 邮件归档文件（按分类分子目录）
- `mail_archive/index/`: 邮件索引 `mail_index.json`、同步状态 `sync_state.json`
- `daemon_state.json`: 守护进程状态
- `last_seen_ids.txt`: `check_mail.py` 的已见邮件缓存

## 测试策略

- 使用 `pytest`。
- 运行全量测试：`PYTHONPATH=src pytest -q`
- 测试文件位于 `tests/`，样本数据位于 `tests/samples/`。
- 修改核心协议解析器（`parsers.py`、`decoder.py`）后，应同时检查 `tests/test_package_layout.py` 和对应样本解析是否通过。
- 修改 `mail_assistant.py` 后，应运行 `test_mail_assistant.py`。

## 安全注意事项

- **绝对不要将真实邮箱凭证提交到 Git**。`.env.eas` 已在 `.gitignore` 中。
- 密码明文存储在 `.env.eas` 本地文件中，不要在多用户共享环境中使用。
- `EAS_VERIFY_TLS=false` 会禁用 TLS 证书验证，仅用于当前内网邮箱服务器场景。
- `tmp/` 下的 `.wbxml` 文件和实时服务器响应属于敏感诊断数据，不要外传。

## 故障排查速查

| 现象 | 常见原因 | 解决 |
|---|---|---|
| `401 Unauthorized` | 用户名格式错误 | 确保 `EAS_USERNAME=RESOFT\用户名`（单反斜杠） |
| `SSLCertVerificationError` | 服务器证书问题 | `.env.eas` 中设置 `EAS_VERIFY_TLS=false` |
| `ModuleNotFoundError: eas_client` | `src/` 不在 `sys.path` | 使用 `PYTHONPATH=src` 或调用 `eas_env.add_import_path()` |
| 发送邮件 401 | 缺少 PolicyKey 或协议版本不对 | 完成 Provision 两步握手；发送时用 `MS-ASProtocolVersion: 12.1` |
| 同步返回 0 封邮件 | 第一次 Sync 只返回 sync_key | 用返回的 sync_key 进行第二次 Sync |
| `isinstance(WbxmlElement)` 失败 | 模型被从不同路径重复导入 | 统一使用 `eas_client` 命名空间，不要创建镜像目录 |

## 提交规范

当前仓库没有复杂的 Git 历史约定。请使用简短的中文或英文祈使句提交：

- `Fix folder selection crash`
- `Add mailbox cache recovery`
- `修复 sync_key 解析失败`

如需创建 PR，请包含：
- 行为变更的简要总结
- 验证命令及结果
- 任何协议或环境假设
