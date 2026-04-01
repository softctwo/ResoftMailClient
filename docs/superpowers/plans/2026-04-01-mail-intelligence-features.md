# Mail Intelligence Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 ResoftMailClient 增加报销打回提醒、立项结论结构化提取、收入预估趋势分析、监管制度影响匹配、客户到访提醒、项目截止日期预警能力，并更新中文 README。

**Architecture:** 在现有 `mail_assistant.py` 的邮件拉取基础上新增规则引擎与结构化分析模块，尽量复用当前分类和时间转换逻辑。输出以 JSON/Markdown 摘要为主，并保留适配 OpenClaw cron 的命令入口。

**Tech Stack:** Python 3、现有 EAS 客户端、规则匹配、JSON/Markdown 输出

---

### Task 1: 抽离统一邮件分析模块

**Files:**
- Create: `analysis_rules.py`
- Modify: `mail_assistant.py`
- Test: 手工运行 `python3 mail_assistant.py poll --limit 20`

- [ ] 新建规则模块，集中维护关键词、产品线映射、预警等级规则。
- [ ] 在 `mail_assistant.py` 中复用规则模块，避免分类逻辑散落。
- [ ] 运行 `python3 mail_assistant.py poll --limit 20`，确认旧能力不回归。

### Task 2: 报销打回实时提醒 + 立项结构化提取

**Files:**
- Modify: `mail_assistant.py`
- Create: `mail_actions.py`
- Test: `python3 mail_assistant.py alerts --limit 30`

- [ ] 增加“报销打回/待办”专项识别逻辑。
- [ ] 增加“立项结论”结构化字段提取：项目名称、编号、范围、预算、负责人、风险点。
- [ ] 新增命令入口输出提醒与结构化结果。
- [ ] 运行验证命令并检查输出。

### Task 3: 收入预估对比 + 监管制度影响匹配

**Files:**
- Modify: `mail_assistant.py`
- Modify: `mail_manager.py`
- Test: `python3 mail_assistant.py intelligence --limit 50`

- [ ] 识别收入/计划收入类邮件并提取主题时间维度，做最近样本趋势汇总。
- [ ] 基于监管关键词与产品线映射输出影响产品线判断。
- [ ] 新增 intelligence 命令输出分析结果。
- [ ] 运行验证命令并检查输出。

### Task 4: 客户到访提醒 + 项目截止日期预警

**Files:**
- Modify: `mail_assistant.py`
- Test: `python3 mail_assistant.py reminders --limit 50`

- [ ] 识别客户到访/提前进场类邮件，判断是否提前 1 天提醒。
- [ ] 识别主题中的日期/截止信息，输出提前 3 天黄警/1 天红警。
- [ ] 新增 reminders 命令输出结果。
- [ ] 运行验证命令并检查输出。

### Task 5: README 中文化并补齐功能说明

**Files:**
- Modify: `README.md`
- Test: 手工阅读 README

- [ ] 将 README 调整为中文为主。
- [ ] 补充六项智能能力说明、命令示例、定时任务接入说明。
- [ ] 检查文档结构和示例命令是否一致。

### Task 6: 最终验证与提交

**Files:**
- Modify: 以上变更文件
- Test: 综合命令验证

- [ ] 运行 `python3 mail_assistant.py poll --limit 20`
- [ ] 运行 `python3 mail_assistant.py alerts --limit 30`
- [ ] 运行 `python3 mail_assistant.py intelligence --limit 50`
- [ ] 运行 `python3 mail_assistant.py reminders --limit 50`
- [ ] 提交 git 并 push 到 `origin/main`
