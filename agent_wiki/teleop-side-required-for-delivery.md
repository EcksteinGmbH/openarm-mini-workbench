---
title: "交付时必须要求遥操作带 --teleop.side=left|right，官方 README 漏了它"
category: convention
tags: [openarm-mini, lerobot, teleoperate, delivery, left-right]
sources:
  - "lerobot main: teleoperators/openarm_mini/openarm_mini.py SIDE_MOTORS_TO_FLIP / JOINT_REMAP"
  - "pkooij/open-arms-mini README.md 的 lerobot-teleoperate 命令（无 --teleop.side）"
  - "docs/official-comparison.md B3"
  - "docs/lerobot-openarm-mini.md「左右臂差异（side）」"
confidence: high
---

# 交付时必须要求遥操作带 --teleop.side=left|right，官方 README 漏了它

`openarm_mini` 的方向翻转表只在 `side` 非空时生效，而官方 README 的遥操作命令没有 `--teleop.side`，照抄会让 6 个关节方向反转。

```python
SIDE_MOTORS_TO_FLIP = {
    "left":  ["joint_1", "joint_3", "joint_4", "joint_5", "joint_6", "joint_7"],
    "right": ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_7"],
}
self._motors_to_flip = SIDE_MOTORS_TO_FLIP.get(config.side, []) if config.side else []
```

`side` 为空时翻转表为空。照官方 README 的 `lerobot-teleoperate` 命令逐字抄，**8 个关节里 6 个方向反了**。

## 约定

- 交付文档、随臂说明里的遥操作命令一律写 `--teleop.side=left` 或 `--teleop.side=right`，与编号里的 `L`/`R` 一致。
- 台架流程不需要它：`side`、`JOINT_REMAP`、夹爪系数只作用于 `get_action()` 的读数换算，
  不写电机、不进校准文件，写 ID 与校准时左右臂没有区别。
- 工作站本身没有遥操作验证环节（`docs/official-comparison.md` B2），这条只能靠交付文档兜住。
