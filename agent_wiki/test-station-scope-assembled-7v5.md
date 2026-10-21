---
title: "测试站测装配好的整臂：7.5V 供电，装配后逐颗写 ID"
category: decision
tags: [openarm-mini, scope, power-supply, workflow, factory-test, motor-id]
sources:
  - "owner 指示 2026-10-21：按 GitHub 信息用 7.5V 电源；测试站装配好后进行；装配完后写 ID 防止序号写错"
  - "pkooij/open-arms-mini BOM.md：7.5V DC 电源 ≥2A；README：官方建议装配前用 lerobot-setup-motors 写 ID"
  - "app/main.py: MINI_HARDWARE_PROFILES（只有 mini_field_7v5）/ CHECKLISTS（只有 S1）"
  - "app/gate.py: REQUIRED_STAGES = S1..S6；S2 只认 hardware_profile=mini_field_7v5 的 init-id"
  - "tests/test_factory_flow.py: ReleaseGateTest（S2 相关用例）"
  - "docs/WORKSTATION_CHANGELOG.md 0.3.0 / 0.4.0"
confidence: high
---

# 测试站测装配好的整臂：7.5V 供电，装配后逐颗写 ID

本工作站测**装配完成的整臂**，电源按官方 BOM 用 **7.5V、≥2A**；**电机 ID 在装配完成后由测试站逐颗写**。
这偏离了官方「装配前写 ID」的建议，理由是防止序号写错：电机已经装在关节上，写的就是这个关节的 ID。

## 由此定下的规则

- 流程：S1 准备 → S2 装配后逐颗写 ID → S3 整臂电气与通信 → S4 关节身份 → S5 官方校准与核对 →
  S6 官方驱动读数 → S7 放行与归档；S8 follower 配对、S9 增强复测可选。
- S2 每颗：驱动板线直接接这颗电机、断开相邻连线 → 广播确认只有它 → 写 ID 与 1 Mbps → 断电 ≥5 秒复扫 →
  **只动这个关节确认**读数变化。总线上只有这一颗，读数变就证明 ID 落在这个关节的电机上。
  S4 在恢复菊花链后再整体复核一遍 ID 与位置。
- 放行门只认 7.5V 档下写的 ID；重写某颗后，它之前的复扫与确认作废。
- 没有 5V 台架档。电压判据是「与 7.5V 偏差 ≤ 1.0V，且不超过额定 7.4V + 1.0V」。
- 装配检查、终检外观检查不由测试站勾选；S1 准备检查表只留测试依赖的项。

## 历史

- 0.2.0：装配前在 5V 台架写 ID + 装配检查 + 终检（`git checkout v0.2.0`）。
- 0.3.0：只测装配后整臂、只用 7.5V，写 ID 挪成不进放行门的返修工具。
- 0.4.0：owner 要求装配后写 ID，S2 回到主流程。2026-09-29 那批 5V 台架写的 ID 不计入。

## 待确认

规格书过压阈值 7.4V 与 7.5V 电源的关系：S3 记录每颗的 `Max_Voltage_Limit`。若真机限值低于 7.5V，
电机会置告警位、S3 状态判失败——届时要么调电源到限值内，要么评估改限值。
