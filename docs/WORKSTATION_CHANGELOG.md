# OpenArm Mini 工作站变更记录

Current workstation version: **0.2.0**（与仓库根目录 `VERSION` 一致）

分级（沿用 OpenARM 工站规则）：

- **MAJOR**：不兼容的工作流、报告格式或硬件控制变更
- **MINOR**：新测试能力、报告模板、页面流程或安全行为变更
- **PATCH**：缺陷、文案或数据映射修复

每条写 Summary / Changes / Verification（具体命令与真机证据）/ Operational Notes（寄存器写入、扭矩、交付物影响）。
历史条目是证据，不是现行规则。

---

### 0.2.0 - 2026-10-21

**Summary**：按官方 7 步流程与出厂测试要求重整为 S0–S6、S9 八个阶段，判定移到服务端，新增放行门与归档报告。
方案见 `.tasks/testbench/factory-test-flow/docs/test-plan.md`。

**Changes**

- 判据表 `app/criteria.py`（版本 `2026-10-21.1`）：每条带依据类型（官方 / 规格 / 推导 / 待定标），待定标项只记录不判定。
- S0 / S2 / S9 人工检查表（S0 记录操作员），逐项入会话日志。
- S1：扫描时记录固件版本与过压 / 欠压 / 过温保护限值；反馈测试记录建议跨度与最大单步（记录项）。
- S3：八轴扫描按判据判定电压（须整臂 7.5V 档）、温度 ≤ 40 °C、状态位 = 0、扭矩关闭、8 颗固件一致；新增 60 秒通信稳定测试。
- S4（新）：关节身份与活动性——只动一个关节，跨度最大的必须是它且 ≥ 次大 × 3。
- S5：校准结局由服务端在子进程退出时记录（不依赖页面轮询）；新增「断电后再核对」；记录夹爪量程。
- S6（新）：用官方 `openarm_mini` 驱动（`scripts/openarm_mini_readout.py`，在 LeRobot 环境里以子进程运行）读零位、夹爪张开、J6/J7 扫动，验证校准文件、side 方向、J6/J7 对调与夹爪换算；生成带 `--robot.*` 与 `--teleop.side` 的交付命令。
- 放行门 `app/gate.py`：只看会话日志，每项取最近一次记录，校准后的项只采信晚于最近一次已保存校准的记录；结论 PASS / HOLD / FAIL。页面阶段条按它画，刷新页面不丢进度；`?robot_id=` 直接打开某条臂。
- 归档：`test_reports/Leader/<编号>/` 生成基础测试记录（md / html / pdf）、校准参数、会话日志、放行判定；修订号 R0n 递增；追加 `test_reports/编号与归档索引.md`。
- 双臂驱动提示更正：单臂版从 PyPI LeRobot 0.6.1 起就有。
- 审查修复：官方校准子进程整段独占串口锁（此前与其他串口操作可能交错收发——旧版本就有的隐患）；
  通信稳定计时从拿到串口后开始；编号格式不对时所有操作直接拦下（否则日志静默丢弃、整场无证据）；
  串口正忙 / 未选串口 / 校准进行中这类前置拦截标记为 precondition，不计入放行门；
  已有文件时在沿用提示处中止或沿用的校准不作废上一份校准；校准确认按提示去重；S6 扫动窗口 8 秒；
  校准子进程管道在结束时关闭。

**Verification**

- `.venv/bin/python -m unittest discover -s tests`：136 项通过（新增 `tests/test_factory_flow.py` 41 项：判据、放行门规则、检查表、归档、读数脚本入口、审查修复回归，含假 `lerobot-calibrate` 验证串口锁）。
- 对 2026-09-29 真机会话日志 `OAML2026092901` 跑放行门与归档：S1 全部 PASS，其余 MISSING，结论 HOLD，PDF 生成正常。
- 页面在 headless Chromium 中渲染，阶段条、检查表、新卡片、放行门表正常；`?robot_id=OAML2026092901` 恢复出 S1 全部通过。
- `scripts/openarm_mini_readout.py` 在 `.venv-lerobot` 里实跑到 `connect()`（无硬件，按预期报 `Could not connect on port`；无校准文件退出码 3）。
- 独立代码审查一轮，见上「审查修复」。
- **未做真机验收**：S3 通信稳定、S4、S6 官方读数、校准结局记录都还没在真机跑过。按 `CLAUDE.md` 验收门，真机通过前不用于产线。

**Operational Notes**

- 仍然全程不上扭矩。新增的写入只有 S6：官方驱动 `connect()` 时自己写的运行期配置（`Return_Delay_Time`、`Maximum_Acceleration`、`Acceleration`、`Operating_Mode`），与客户遥操作时完全相同。
- 旧格式的整臂扫描记录（无判定字段）不计入 S3，需要重扫。
- S3–S6 必须在整臂 7.5V 档下做；5V 台架档只用于 S1。

### 0.1.0 - 2026-09-29

初版：五阶段页面（准备 / 写 ID 与质检 / 八轴扫描 / 校准与核对 / 导出 JSON），全程只读，三语。见 git `898bf46`–`7494016`。
