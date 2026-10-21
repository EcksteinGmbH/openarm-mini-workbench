---
title: "单电机识别用官方广播 ping，并在多于一个应答时报错"
category: decision
tags: [openarm-mini, feetech, sts3215, setup-motors, id-write, safety]
sources:
  - "app/main.py: FeetechSdkClient.broadcast_ping() / find_single_sts3215()"
  - "tests/test_workstation.py: BroadcastPingTest"
  - "lerobot main: motors/feetech/feetech.py _find_single_motor_p0() / _broadcast_ping()"
  - "docs/official-comparison.md A1"
  - "git e501f7d 提交说明（本机实测耗时）"
confidence: medium
---

# 单电机识别用官方广播 ping，并在多于一个应答时报错

第 2 步找单颗电机按官方方式每档波特率发一个广播 ping（实测 8 s，原逐个试 ID 要 105–113 s），并在收到多于一个应答时报错，防止两颗电机被写成同一 ID。

官方 `_find_single_motor_p0()` 每档波特率发**一个广播 ping**（8 档，最坏 8 包）。
已发布的 `scservo_sdk` 在协议 0 下没有广播 ping，官方自己拼包；
`broadcast_ping()` 逐行移植它，所需原语在 `feetech-servo-sdk 1.0.0` 里都有。

| 路径 | 本机实测（适配器在位、电机未上电） |
|---|---|
| 广播 ping（默认，官方同法） | 8.0 s |
| 逐个试 ID「深度扫描」（勾选才用，非官方） | 112.9 s |

逐个试 ID 是从 SO-ARM101 工作站带来的，不是官方行为，期间串口独占。

## 比官方多的一道闸

广播返回**所有**应答。`len(answered) > 1` 时直接报错并列出 ID。
官方只取第一个应答，写 ID 时多接一颗电机会把两颗改成同一个 ID 而毫无察觉。
这是在执行官方「只连接当前这颗电机」的前提，不是偏离它。

## 为什么 confidence 是 medium

无电机路径已实测；**电机在位时能否一次问到、多接时是否如期报错**仍待真机验收（验收门见 `CLAUDE.md`）。
验收通过后把本页改为 high 并补证据。
