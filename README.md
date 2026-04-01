# ResoftMailClient

ResoftMailClient 是面向公司 Exchange / EAS 邮箱场景的邮件助手项目，用于收信、发信、附件发送、邮件晨报、定时拉取以及规则化邮件分析。

## 一、项目定位

本项目当前重点支持以下能力：

- 公司邮箱收信与发信
- 附件发送
- 邮件时间统一按北京时间展示
- 晨报生成
- OpenClaw cron 定时拉取与提醒
- 邮件智能分析与结构化提取

## 二、环境配置

建议使用仓库根目录下的 `.env.eas` 配置邮箱连接参数，不建议直接 `source .env.eas`，避免域账号中的反斜杠被 shell 吃掉。

典型配置如下：

```bash
EAS_SERVER=mail.resoftcss.com.cn
EAS_USERNAME=RESOFT\zhangyanlong
EAS_PASSWORD=你的密码
EAS_ACCOUNT_EMAIL=zhangyanlong@resoftcss.com.cn
EAS_DEVICE_ID=PYEASCLI001
EAS_VERIFY_TLS=false
EAS_DEVICE_TYPE=PythonEAS
EAS_USER_AGENT=Apple-iOS/17.0
```

## 三、基础命令

### 1）检查邮件

```bash
python3 check_mail.py
```

### 2）发送邮件

```bash
python3 send_mail.py --to someone@example.com --subject "主题" --body "正文"
```

### 3）发送带附件邮件

```bash
python3 send_mail.py --to someone@example.com --subject "主题" --body "正文" --attach ./file1.pdf
```

多附件：

```bash
python3 send_mail.py --to someone@example.com --subject "主题" --body "正文" --attach ./file1.pdf --attach ./file2.xlsx
```

### 4）增量归档邮件

```bash
python3 mail_manager.py sync-incremental
```

## 四、邮件时间修正

Exchange 返回的原始邮件时间通常为 UTC，例如：

```text
2026-04-01T09:44:04.002Z
```

项目已统一转换为 **北京时间（Asia/Shanghai）** 展示：

- `received_at`：北京时间，用于展示
- `received_at_raw`：原始 UTC 时间，用于内部兼容和去重

## 五、晨报与定时拉取

### 1）生成晨报

```bash
python3 mail_assistant.py morning-report --limit 50 --hours 24
```

输出内容包括：

- 待关注事项
- 报销/打回提醒
- 客户到访/商务协同
- 分类统计
- 重要邮件摘要

晨报文件默认写入：

```bash
assistant_data/reports/morning_digest_YYYY-MM-DD.md
```

### 2）轮询新邮件

```bash
python3 mail_assistant.py poll --limit 30
```

### 3）轮询守护进程

```bash
python3 mail_daemon.py
```

### 4）配合 OpenClaw cron 的脚本

- 每 10 分钟轮询：`run_mail_monitor.sh`
- 每日晨报：`run_morning_report.sh`

说明：当前项目支持配合 **OpenClaw 内部 cron** 使用，不依赖 macOS 系统级调度。

## 六、智能分析能力

本项目已实现以下能力：

### 1）报销打回实时提醒（关键词触发）

命令：

```bash
python3 mail_assistant.py alerts --limit 30
```

当前会识别：
- 打回
- 报销
- 报销系统待办
- 借款审批

输出内容：
- 报销/待办提醒列表
- 重点邮件时间、发件人、主题

### 2）立项结论信息提取（结构化）

命令：

```bash
python3 mail_assistant.py alerts --limit 30
```

会对立项类邮件输出结构化字段：
- 项目名称
- 项目编号
- 范围（待结合正文/附件补充）
- 预算
- 负责人
- 风险点

### 3）收入预估数据对比（趋势分析）

命令：

```bash
python3 mail_assistant.py intelligence --limit 50
```

输出内容：
- 经营统计类邮件数量
- 按月份/周期聚合的趋势结果
- 最近样本主题

### 4）监管制度影响匹配（按产品线）

命令：

```bash
python3 mail_assistant.py intelligence --limit 50
```

会按关键词自动匹配可能影响的产品线，例如：
- 一表通
- EAST
- 反洗钱
- 利率报备
- 数据治理
- 票据

### 5）客户到访日程提醒（提前 1 天）

命令：

```bash
python3 mail_assistant.py reminders --limit 50
```

识别范围：
- 客户到访
- 提前进场
- 提前实施

若主题或正文中识别到日期，并且距离当前日期为 1 天，则进入提醒列表。

### 6）项目截止日期预警（提前 3 天黄警 / 1 天红警）

命令：

```bash
python3 mail_assistant.py reminders --limit 50
```

识别主题或正文中的日期，并输出：
- `🟡` 提前 3 天黄警
- `🔴` 提前 1 天红警

## 七、推荐工作流

建议默认按以下顺序处理邮件：

1. 财务/报销待办
2. 立项结论与审批类
3. 经营统计类
4. 系统待办通知

其中：
- 立项类邮件优先提炼：项目名称、编号、范围、预算、负责人、风险点
- 报销/待办类邮件优先判断：是否需要当天处理

## 八、验证命令

建议在变更后执行：

```bash
python3 mail_assistant.py poll --limit 20
python3 mail_assistant.py alerts --limit 30
python3 mail_assistant.py intelligence --limit 50
python3 mail_assistant.py reminders --limit 50
python3 mail_assistant.py morning-report --limit 50 --hours 24
```
