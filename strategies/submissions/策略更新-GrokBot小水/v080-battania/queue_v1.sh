#!/bin/bash
cd "$(dirname "$0")"
while kill -0 91014 2>/dev/null; do sleep 20; done
python3 harness.py v1 101 --days 1680 --out res/v1_s101 > logs/v1_s101.log 2>&1
