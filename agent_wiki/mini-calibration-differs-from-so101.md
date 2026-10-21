---
title: "OpenArm Mini 校准与 SO-101 不同：不做行程试扫，不按停放窗口拦截"
category: decision
tags: [openarm-mini, calibration, so-arm101, lerobot]
sources:
  - "docs/lerobot-openarm-mini.md「校准流程」「与 SO-101 的三处关键差异」"
  - "lerobot main: teleoperators/openarm_mini/openarm_mini.py calibrate()"
  - "app/main.py: CalibrationSession.PHASE_PATTERNS"
  - "tests/test_workstation.py: CalibrationPhaseTest"
  - "git 898bf46 提交说明"
confidence: high
---

# OpenArm Mini 校准与 SO-101 不同：不做行程试扫，不按停放窗口拦截

Mini 的关节量程由驱动写死为整圈、校准只需零位加两次夹爪确认，所以 SO-101 的行程试扫与停放窗口不移植。

`openarm_mini.calibrate()` 给 `joint_1..joint_7` **写死整圈量程 `0..4095`**，只有夹爪按实测取量程。
所以 SO-101 那套「操作员扫行程 + 行程必须落进停放位 ±2047」的约束在 Mini 上不存在，
照搬会拦下完全正常的关节。

| | SO-101 | OpenArm Mini |
|---|---|---|
| 确认 | 2 次（置中、扫行程） | 1 次零位（整臂下垂、夹爪闭合）+ 夹爪闭合 + 夹爪张开 |
| 关节量程 | 操作员扫出 | 驱动写死 `0..4095` |
| 保存标记 | `Calibration saved` | `Calibration complete and saved to` |
| 额外写入 | — | 全部电机 `Phase = 12` |

## 由此定下的规则

- 工作站**不移植**行程试扫和停放窗口。
- 校准阶段识别按 Mini 的提示串重写，保存标记用 `Calibration complete and saved to`。
- 校准前唯一的拦截是预检里的两条（多圈累计、偏移超 ±2047），算法见 [[precheck-encoder-modulo-4096]]。
- 一致性核对期望 `Phase = 12`，核对范围见 [[calibration-consistency-check-scope]]。
