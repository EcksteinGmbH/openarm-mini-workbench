---
title: "一致性核对比什么、不比什么：三个寄存器、Phase=12、Acceleration 不判负"
category: reference
tags: [openarm-mini, calibration, eeprom, lerobot, verification]
sources:
  - "app/main.py: verify_calibration_and_config() / MINI_RUNTIME_EXPECTED / MINI_RUNTIME_ONLY_FIELDS / _calibration_root()"
  - "tests/test_workstation.py: CalibrationRootTest / CalibrationPathTest / DriverConstantsTest"
  - "docs/lerobot-openarm-mini.md「校准文件位置」「Phase 寄存器」「每次连接都会重写的运行期参数」"
  - "docs/official-comparison.md A2"
confidence: high
---

# 一致性核对比什么、不比什么：三个寄存器、Phase=12、Acceleration 不判负

一致性核对按 LeRobot 规则定位校准文件，文件与电机只比 `Homing_Offset`/`Min`/`Max` 三项，配置期望 `Phase=12`，断电归零的 `Acceleration` 只提示不判负。

## 校准文件在哪

`<校准根>/teleoperators/openarm_mini/<编号>.json`。校准根**不能写死**，按 lerobot `utils/constants.py`：
`HF_LEROBOT_CALIBRATION` > `HF_LEROBOT_HOME/calibration` > `HF_HOME/lerobot/calibration` >
`$XDG_CACHE_HOME/huggingface/lerobot/calibration`。写死会在 `HF_HOME` 改过的机器上找错目录，
要么误报「未找到」，要么拿过期文件报 8/8 假合格。

## 文件 vs 电机：只比三项

`write_calibration()` 只写 `Homing_Offset`、`Min_Position_Limit`、`Max_Position_Limit`；
官方 `is_calibrated` 也只比这三项。`drive_mode` 只在文件里，不进寄存器，无法比对。

## 配置期望值

| 字段 | 期望 | 判定 |
|---|---|---|
| `Phase`（地址 18） | 12（`calibrate()` 写入；`12 & 0x10 == 0`） | 判 |
| `Return_Delay_Time`（7） | 0 | 判 |
| `Maximum_Acceleration`（85） | 254 | 判 |
| `Operating_Mode`（33） | 0 | 判 |
| `Acceleration`（41） | 254 | **只提示**：SRAM，断电归零，LeRobot 每次 `connect()` 重写 |

拿 `Acceleration` 判负会让每一条断过电的臂都不合格。

## 不覆盖

双臂 `bi_openarm_mini` 的校准文件名是 `<id>_left.json` / `<id>_right.json`，不符合本工作站编号规则，
核对会报「未找到校准文件」（`docs/official-comparison.md` B1）。
沿用旧文件导致的假合格见 [[calibration-reuse-prompt-trap]]。
