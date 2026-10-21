---
title: "已有校准文件时裸回车 = 沿用旧参数，退出码 0 但什么都没测"
category: debugging
tags: [openarm-mini, lerobot, calibration, false-pass]
sources:
  - "lerobot main: teleoperators/openarm_mini/openarm_mini.py calibrate() 的沿用提示"
  - "app/main.py: CalibrationSession（answer 'c'、finished_unsaved）/ diagnose_calibration_output()"
  - "tests/test_workstation.py: CalibrationPhaseTest.test_only_the_existing_file_prompt_answers_c / DiagnosisTest"
  - "docs/lerobot-openarm-mini.md「沿用旧校准文件的陷阱」"
confidence: high
---

# 已有校准文件时裸回车 = 沿用旧参数，退出码 0 但什么都没测

同 id 校准文件已存在时，`lerobot-calibrate` 的沿用提示处裸回车会写回旧参数并以退出码 0 返回，随后的一致性核对会给出 8/8 假合格；工作站回答 `c` 并把无保存标记判为 `finished_unsaved`。

同 id 的校准文件已存在时，`calibrate()` 先问：

```
Press ENTER to use existing calibration for <id>, or type 'c' and press ENTER to run new calibration:
```

裸回车 → 把旧参数写回电机就返回，退出码 0，**不打印保存标记**。随后的一致性核对拿电机和同一份旧文件比，
报 8/8 通过——给没校准的臂出了合格结论。每次复测、返修重校都会遇到。

## 工作站的处理

- 识别为独立阶段，确认按钮改为「重新校准（覆盖旧文件）」，回答字面量 `c`。
- 退出码 0 但没有 `Calibration complete and saved to` → 判 `finished_unsaved`，**不串联一致性核对**。
- 输出里出现 `Using existing calibration for` → 诊断为沿用旧文件，处置是重来并在提示处选覆盖。

SO-ARM101 工作站遇到的同一陷阱：`so-arm101-workbench/agent_wiki/lerobot-existing-calibration-prompt.md`（提示文字不同）。
