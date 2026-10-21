---
title: "测试站只测装配好的整臂，电源一律 7.5V"
category: decision
tags: [openarm-mini, scope, power-supply, workflow, factory-test]
sources:
  - "owner 指示 2026-10-21：按 GitHub 信息用 7.5V 电源；测试站只是软件测试，装配好后进行"
  - "pkooij/open-arms-mini BOM.md：7.5V DC 电源 ≥2A；README：装配前用 lerobot-setup-motors 写 ID"
  - "app/main.py: MINI_HARDWARE_PROFILES（只有 mini_field_7v5）/ CHECKLISTS（只有 S1）"
  - "app/gate.py: REQUIRED_STAGES = S1..S5"
  - "docs/WORKSTATION_CHANGELOG.md 0.3.0"
confidence: high
---

# 测试站只测装配好的整臂，电源一律 7.5V

本工作站的测试对象是**装配完成的整臂**，只做软件测试；电源按官方 BOM 用 **7.5V、≥2A**。

## 由此定下的规则

- 流程：S1 准备 → S2 整臂电气与通信 → S3 关节身份 → S4 官方校准与核对 → S5 官方驱动读数 → S6 放行与归档；
  S7 follower 配对、S8 增强复测可选。
- **装配前写 ID 属装配环节**，不在测试流程里。工作站保留单电机写 ID 作为「返修工具」
  （S2 发现 ID 不对时拆线单独重写），它的记录不进放行门，只在报告「返修记录」里列出。
- 没有 5V 台架档。电压判据是「与 7.5V 偏差 ≤ 1.0V，且不超过额定 7.4V + 1.0V」。
- 装配检查、终检外观检查不由测试站勾选；准备检查表只留测试依赖的项（电源、立柱、菊花链与 USB、
  Waveshare 跳线、夹爪件左右与编号一致）。

## 历史

工作站 0.2.0 曾按「装配前逐颗写 ID（5V 台架档）+ 装配检查 + 终检」设计，0.3.0 按本决定改掉。
旧版可用 `git checkout v0.2.0` / `v0.1.0` 对照。

## 待确认

规格书过压阈值 7.4V 与 7.5V 电源的关系：S2 记录每颗的 `Max_Voltage_Limit`。若真机限值低于 7.5V，
电机会置告警位、S2 状态判失败——届时要么调电源到限值内，要么评估改限值。
