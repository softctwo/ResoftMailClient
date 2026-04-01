#!/bin/zsh
set -euo pipefail
cd /Users/zhangyanlong/.openclaw/workspace/eas-mail-reader
python3 mail_assistant.py morning-report --limit 50 --hours 24
