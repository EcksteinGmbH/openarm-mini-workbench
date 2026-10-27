# 任务: factory-test-flow — 按官方流程与出厂测试重整 OpenArm Mini 测试流程

> 状态: 🟡 实现完成，待真机验收
> 模块: testbench
> 开始: 2026-10-21

## 目标

以官方 7 步流程为骨架，补齐出厂测试所需的判据、记录、报告与放行门，并据此修改工作站实现。

## 当前工作

- **阶段**: 实现完成（工作站 0.4.0，2026-10-21），待真机验收
- **下一步**: 2026-10-22 真机跑 OAML2026092901（已装配）：S1 → S2 装配后重写 ID → S3 → S4 → S5 → S6 → S7 归档；记录问题与实测值用于定标
- **阻塞**: 无
- **owner 已定（2026-10-21）**：测装配好的整臂，电源一律 7.5V；**装配完成后逐颗写 ID** 防止序号写错。阶段 S1–S7，见 test-plan.md「v0.3 修订」
- **§6 其余决策的临时默认**（可改）：S5 方向只记录；报告只做基础测试记录 + 放行门（不做受控三件套），中/英/德分成三份独立报告且工作台可直接打开，项目负责人为 `pengcheng`；交付报告只展示最终有效记录和参与放行的判据，完整过程保留在内部 JSONL/JSON；LeRobot 继续用本机 eb7a54c，新装机钉 0.6.1

## 产出

- [docs/test-plan.md](docs/test-plan.md) — 测试方案 v0.3（装配后整臂、7.5V、装配后写 ID；阶段 S1–S7；v0.2/v0.1 原文保留作依据）
- [docs/research.md](docs/research.md) — 调研证据（官方现状与变化、兄弟工站做法、真机数据、实现差距）

## 相关参考

- `agent_wiki/workstation-sources-of-truth.md` — 规则分层与冲突裁决
- `agent_wiki/mini-calibration-differs-from-so101.md` — 不移植行程试扫/停放窗口
- `agent_wiki/precheck-encoder-modulo-4096.md` — 预检折算取模
- `agent_wiki/calibration-reuse-prompt-trap.md` — 沿用旧校准的假合格
- `agent_wiki/calibration-consistency-check-scope.md` — 核对范围
- `agent_wiki/openarm-mini-driver-generations.md` — 驱动两代（已更正：PyPI 0.6.1 起单臂）
- `agent_wiki/teleop-side-required-for-delivery.md` — 交付须带 `--teleop.side`
- `feature_wiki/standard-test-workflow.md` — 出厂测试工作流（操作步骤，兼作真机测试指引）
- 兄弟工站：`so-arm101-workbench/test_reports/generate_archive.py`、`OpenARM/agent_wiki/openarm-factory-acceptance-release-gate.md`

## 里程碑

- [ ] M0: 真机基线——在 OAML2026092901 上完整跑通（2026-10-22，与新流程合并进行）
- [x] M1: 判据表 + 服务端判定 + 放行门 + LeRobot 版本记录（2026-10-21）
- [x] M2: S3 补判据、S4 关节身份与活动性、S1/S5 补项（2026-10-21，待真机验收）
- [x] M3: S6 官方驱动读数验证（2026-10-21，待真机验收）
- [x] M4: S9 归档报告 + VERSION/CHANGELOG（2026-10-21）；首批 3 台定标未做
- [ ] M5（可选）: S7 follower 配对、S8 增强复测（S0/S2/S9 检查表已随 M1 做完）

## 非协商条款

- 只测装配完成的整臂，电源一律 7.5V（官方 BOM）；电机 ID 在装配后由 S2 逐颗写，每颗动关节确认。
- 全程不上扭矩、不下发目标位置；写入只限 S2 的 ID/波特率、官方校准、官方驱动连接时的配置。
- 每项判定在服务端完成并写入会话日志；报告只从日志生成；必做项缺记录不得出 PASS。
- 每个数值判据在内部定义中标明依据类型（官方/规格/推导/待定标）；推不出的不编数字，`待定标` 项不参与 PASS/FAIL，也不作为客户交付报告的测试行。
- 官方流程步骤的结果不得被本地闸门改变；页面标明「官方流程」/「本地质检」。
- 最终有效的 FAIL / MISSING 必须在放行判定中明示，不得通过交付筛选隐藏；历史失败、失效旧校准记录和待定标项留在内部 JSONL/JSON，不进入客户 PDF。
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
| 2026-10-21 | 实现 M1–M4（工作站 0.2.0）：`app/criteria.py`、`app/gate.py`、`scripts/openarm_mini_readout.py`、页面八阶段；130 项单测通过；未做真机验收 |
| 2026-10-21 | 按代码审查修 8 处：校准子进程独占串口锁、通信计时从拿到串口起算、编号不合法即拦、前置拦截不计入放行门、沿用提示处中止不作废校准、确认按提示去重、扫动窗口 8 秒、请求字段容错；136 项单测 |
| 2026-10-21 | owner 确认只测装配后整臂、只用 7.5V：阶段改 S1–S6，写 ID 挪为返修工具，去掉装配 / 终检检查表与 5V 档（工作站 0.3.0，139 项单测） |
| 2026-10-21 | owner 要求装配后写 ID：新 S2 进入必做流程，后续阶段顺移为 S3–S7；只认 7.5V 档写的 ID；文档写明校准写入内容（工作站 0.4.0，142 项单测） |
| 2026-10-23 | owner 要求归档报告完整呈现中/英/德三语，元数据与签核栏记录项目负责人 `pengcheng`（工作站 0.5.0） |
| 2026-10-23 | owner 进一步确认三语必须分成三份独立报告，并可在工作台直接打开（工作站 0.6.0） |
| 2026-10-26 | owner 要求客户交付报告筛除历史失败、失效旧读数和待定标行；最终 FAIL/MISSING 仍如实显示，完整证据留在内部归档（工作站 0.10.0） |
