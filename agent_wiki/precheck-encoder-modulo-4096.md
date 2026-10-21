---
title: "校准预检的编码器折算必须对 4096 取模，否则会拦下已校准的臂"
category: debugging
tags: [openarm-mini, sts3215, encoder, homing-offset, precheck, false-fail]
sources:
  - "app/main.py: evaluate_precheck_pose()"
  - "tests/test_workstation.py: PrecheckPoseTest（含 4096 个位置的穷举）"
  - "docs/lerobot-openarm-mini.md「预检的折算必须取模」"
  - "git 1bed24f 提交说明（2026-09-29 首次真机预检的现场数据）"
confidence: high
---

# 校准预检的编码器折算必须对 4096 取模，否则会拦下已校准的臂

预检把 `Present_Position + Homing_Offset` 折算成单圈读数时必须 `mod 4096`；不取模会把停在编码器接缝附近的正常关节当成多圈累计拦下。

```
actual           = (Present_Position + Homing_Offset) mod 4096
predicted_homing = actual − 2047
```

STS3215 的 `Present_Position` 用 bit 15 符号-幅值编码，靠近编码器接缝时直接报负数；
扣掉已有的 `Homing_Offset` 后落到 `0..4095` 之外是正常姿态，不是多圈累计。

## 现场证据

2026-09-29 首次真机预检，一个摆在零位的关节被拦，报「折算读数 -1497 超出单圈」。
同一条臂 J3 实测 `present = -1478`、`homing = 0`，取模后是 2618。修复后 8/8 通过。
不取模会拦下**每一条**校准过的臂。

## 仍然成立的两条拦截

| 判据 | 官方对应 | 处置 |
|---|---|---|
| `Present_Position > 4095` | 多圈累计，偏移装不进寄存器 | 断电 5 秒重上电 |
| `\|actual − 2047\| > 2047` | `encoding_utils` 报 `Magnitude ... exceeds` | 同上 |

第二条是可达的：取模后只有 `actual == 4095`（偏移 2048）会触发，测试穷举确认它是唯一被拒的位置。

同一问题在 SO-ARM101 工作站的版本：`so-arm101-workbench/agent_wiki/sts3215-encoder-seam-and-homing-offset.md`。
