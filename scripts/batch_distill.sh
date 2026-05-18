#!/bin/bash
# 批量蒸馏所有未处理信号
# 用法: bash scripts/batch_distill.sh [每批条数] [批次间隔秒数]
# 默认: 每批 10 条，批次间隔 3 秒
# Ctrl+C 可随时中断，已处理的不丢失，下次运行继续

LIMIT="${1:-10}"
DELAY="${2:-3}"
TOTAL=0
BATCH=0

echo "批量蒸馏开始（每批 ${LIMIT} 条，间隔 ${DELAY}s）"
echo "=========================================="

while true; do
    # 检查剩余未处理信号数
    REMAINING=$(python3 -c "
import os; os.environ['HUAQI_DATA_DIR']='/Users/lianzimeng/workspace/huaqi'
from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
from huaqi_src.layers.data.raw_signal.models import RawSignalFilter
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
s = RawSignalStore(adapter=SQLiteStorageAdapter(db_path='/Users/lianzimeng/workspace/huaqi/raw_signals.db'))
print(s.count(RawSignalFilter(user_id='default', processed=0)))
" 2>/dev/null)

    if [ "$REMAINING" = "0" ] || [ -z "$REMAINING" ]; then
        echo ""
        echo "=========================================="
        echo "全部完成！共处理 ${TOTAL} 条"
        break
    fi

    BATCH=$((BATCH + 1))
    echo -n "[批次 ${BATCH}] 剩余 ${REMAINING} 条... "

    RESULT=$(huaqi telos distill --limit "$LIMIT" 2>&1)
    echo "$RESULT"

    # 提取成功数
    PROCESSED=$(echo "$RESULT" | grep -o '[0-9]* 条' | head -1 | grep -o '[0-9]*')
    PROCESSED="${PROCESSED:-0}"
    TOTAL=$((TOTAL + PROCESSED))

    if [ "$REMAINING" -gt 0 ]; then
        sleep "$DELAY"
    fi
done
