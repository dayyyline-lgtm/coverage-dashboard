# -*- coding: utf-8 -*-
"""아침에 PC 를 깨워 두기만 한다 — 아마존에는 요청하지 않는다 (2026-10-18).

왜
  PC 트래커(main.py)를 끄면서 생긴 빈자리다. 그동안 05:15 트래커 작업이 PC 를 깨우고, 수집하는 40~50분 동안
  SetThreadExecutionState 로 잠들지 못하게 붙잡아 두었다. 그 덕에 05:30 아침 예약 작업(크롬 — 미국 세부 카테고리 ·
  7개국 Top100)이 크롬에 붙을 수 있었다. 트래커만 끄면 PC 가 깨어난 지 2분 만에 다시 잠들어 크롬 수집까지 끊긴다.
  그래서 작업 스케줄러 'AmazonBeautyTracker'(05:15 · 절전 해제)는 이제 run.bat 대신 awake.bat → 이 파일을 부른다.

  python awake.py [분]     기본 110분(05:15 → 07:05 — 아침 예약 작업이 크롬을 90분까지 기다린다)
"""
import ctypes
import datetime
import os
import sys
import time

ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def main():
    mins = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 110
    print(f"[깨워 두기] {datetime.datetime.now():%Y-%m-%d %H:%M:%S} · {mins}분 — 아마존 요청 없음", flush=True)
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    try:
        time.sleep(mins * 60)
    finally:
        if os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    print(f"[깨워 두기] 끝 {datetime.datetime.now():%H:%M:%S}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
