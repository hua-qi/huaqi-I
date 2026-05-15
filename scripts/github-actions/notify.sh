#!/bin/bash
# Server酱 通知脚本
# 用法: ./notify.sh "标题" "内容"
# 需要环境变量: SERVERCHAN_KEY

set -euo pipefail

SERVERCHAN_KEY="${SERVERCHAN_KEY:-}"
if [ -z "$SERVERCHAN_KEY" ]; then
    echo "WARNING: SERVERCHAN_KEY not set, skipping notification"
    exit 0
fi

TITLE="$1"
CONTENT="$2"

curl -s -X POST "https://sctapi.ftqq.com/${SERVERCHAN_KEY}.send" \
    -d "title=${TITLE}" \
    -d "desp=${CONTENT}" \
    -o /dev/null

echo "Notification sent: ${TITLE}"
