#!/bin/bash
# 顺序执行：等前一局结束再开下一局（从不并发）
cd "$(dirname "$0")"
while pgrep -f "harness.py v4 104" >/dev/null; do sleep 15; done
python3 harness.py v5 105 --days 1680 --out res/v5_s105 > logs/v5_s105.log 2>&1
