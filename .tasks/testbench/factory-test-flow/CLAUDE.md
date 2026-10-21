# 任务: factory-test-flow — 按官方流程与出厂测试重整 OpenArm Mini 测试流程

> 状态: 🔵 规划中
> 模块: testbench
> 开始: 2026-10-21

## 目标

以官方 7 步流程为骨架，补齐出厂测试所需的判据、记录、报告与放行门，并据此修改工作站实现。

## 当前工作

- **阶段**: 规划（方案提案已出，等 owner 决策）
- **下一步**: owner 确认 [docs/test-plan.md](docs/test-plan.md) §6 的 5 个决策点 → `/task-plan-spec` 写规格
- **阻塞**: §6 决策；M0 需要台架与整臂

## 产出

- [docs/test-plan.md](docs/test-plan.md) — 测试方案提案 v0.1（阶段 S0–S9、判据与依据、改动清单、里程碑、决策点）
- [docs/research.md](docs/research.md) — 调研证据（官方现状与变化、兄弟工站做法、真机数据、实现差距）

## 相关参考

- `agent_wiki/workstation-sources-of-truth.md` — 规则分层与冲突裁决
- `agent_wiki/mini-calibration-differs-from-so101.md` — 不移植行程试扫/停放窗口
- `agent_wiki/precheck-encoder-modulo-4096.md` — 预检折算取模
- `agent_wiki/calibration-reuse-prompt-trap.md` — 沿用旧校准的假合格
- `agent_wiki/calibration-consistency-check-scope.md` — 核对范围
- `agent_wiki/openarm-mini-driver-generations.md` — 驱动两代（需按 research.md 更正 0.6.1）
- `agent_wiki/teleop-side-required-for-delivery.md` — 交付须带 `--teleop.side`
- `feature_wiki/standard-test-workflow.md` — 现有五阶段流程
- 兄弟工站：`so-arm101-workbench/test_reports/generate_archive.py`、`OpenARM/agent_wiki/openarm-factory-acceptance-release-gate.md`

## 里程碑

- [ ] M0: 真机基线——现有流程在 OAML2026092901 上完整跑通 S1–S5，数据入日志
- [ ] M1: 判据表 + 服务端判定 + 放行门骨架 + LeRobot 版本钉定
- [ ] M2: S3 补判据、S4 关节身份与活动性、S1/S5 补项
- [ ] M3: S6 官方驱动读数验证
- [ ] M4: S9 归档报告 + VERSION/CHANGELOG；首批 3 台定标
- [ ] M5（可选）: S0/S2 检查表 UI、S7 follower 配对、S8 增强复测

## 非协商条款

- 全程不上扭矩、不下发目标位置；写入只限 ID/波特率、官方校准、官方驱动连接时的配置。
- 每项判定在服务端完成并写入会话日志；报告只从日志生成；必做项缺记录不得出 PASS。
- 每个数值判据标明依据类型（官方/规格/推导/待定标）；推不出的不编数字，`待定标` 项不参与 PASS/FAIL。
- 官方流程步骤的结果不得被本地闸门改变；页面标明「官方流程」/「本地质检」。
- 未验证项（如 S7）在报告中明示，不得解释为通过。
- 新增面向操作员文案同步中/英/德。
- 影响串口、寄存器写入、校准作答的改动须经 `CLAUDE.md` 验收门真机验收。

## 禁止事项

- 不移植 SO-101 的行程试扫与停放窗口。
- 不把 LeRobot 作为 `app/` 的 import 依赖；官方驱动只经子进程调用。
- 未改特征串与测试前，不升级到含 lerobot#4672/#4867 的版本。
- 不用其他臂、其他侧或常量填充报告测量值。

## 待决策（owner）

见 [docs/test-plan.md](docs/test-plan.md) §6：S1 供电档、S7 follower、S6 方向表来源、报告级别与签核人、LeRobot 改钉 PyPI 0.6.1。

## 规格文件

(待 /task-plan-spec 补充)

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-10-21 | 创建任务；完成调研与测试方案提案 v0.1 |
