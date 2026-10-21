---
title: "OpenArm Mini 工作站的规则来源：官方两处 + SO-ARM101 移植 + 本地产线闸门"
category: reference
tags: [openarm-mini, official, lerobot, so-arm101, provenance]
sources:
  - "docs/official-comparison.md（2026-09-29 逐项核对，一致/有意差异/缺失三类）"
  - "docs/hardware-reference.md（数值照抄 pkooij/open-arms-mini README.md 与 BOM.md）"
  - "docs/lerobot-openarm-mini.md（对照 lerobot main 的 teleoperators/openarm_mini/）"
  - "git 898bf46 / 5fdf477 / e501f7d 提交说明"
confidence: high
---

# OpenArm Mini 工作站的规则来源：官方两处 + SO-ARM101 移植 + 本地产线闸门

改任何硬件规则前，先判断它属于哪一层，冲突时按下表优先级裁决。

| 层 | 来源 | 管什么 | 冲突时 |
|---|---|---|---|
| 官方硬件 | [pkooij/open-arms-mini](https://github.com/pkooij/open-arms-mini) `README.md`、`BOM.md` | 关节 ID 表、装配顺序、官方命令、BOM | 以它为准 |
| 官方驱动 | [huggingface/lerobot](https://github.com/huggingface/lerobot) `teleoperators/openarm_mini/`、`motors/feetech/`、`motors_bus.py`、`scripts/lerobot_*`、`utils/constants.py` | 写 ID 步骤与顺序、校准流程与提示串、寄存器期望值、校准文件路径 | 以它为准 |
| 移植 | `so-arm101-workbench`（同款 STS3215 与控制表） | Feetech 通信层、页面骨架、串口处理 | 只在与官方一致时保留 |
| 本地闸门 | 本仓库 | 断电复扫、只读质检、八轴扫描、预检、一致性核对、编号、会话日志、三语 | 不得改变官方流程的结果 |

## 要点

- LeRobot `docs/source/` **没有** Mini 的文档页（`openarm.mdx` 是达妙 CAN 版 OpenARM），
  所以硬件仓库 README 是 Mini **唯一的官方流程文档**。
- 页面每一步都标「官方流程」或「本地质检」，对照表在 `README.md`「流程与官方的对应」。
- 从 SO-ARM101 移植来的东西不能默认正确：逐个试 ID 找电机就是移植来的非官方行为，
  已改回广播 ping（见 [[single-motor-broadcast-ping]]）；行程试扫与停放窗口则刻意没移植
  （见 [[mini-calibration-differs-from-so101]]）。
- 官方驱动依据的是 lerobot `main`；本机实际运行的版本见 [[openarm-mini-driver-generations]]。
  上游升级后，`tests/test_workstation.py` 里引用的提示串/特征串会先失败。
