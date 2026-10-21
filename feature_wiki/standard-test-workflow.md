---
title: "testbench — OpenArm Mini 出厂测试工作流（装配后整臂，7.5V）"
category: feature
module: testbench
audience: [operator, engineer]
status: beta
since: 2026-09-29
updated: 2026-10-21
sources:
  - "app/main.py"
  - "app/criteria.py"
  - "app/gate.py"
  - "app/messages.py"
  - "scripts/openarm_mini_readout.py"
  - "tests/test_factory_flow.py"
  - "tests/test_workstation.py"
  - ".tasks/testbench/factory-test-flow/docs/test-plan.md"
related_features: []
---

# testbench — OpenArm Mini 出厂测试工作流（装配后整臂，7.5V）

## What it is

OpenArm Mini leader 臂的出厂测试页面，测的是**装配完成的整臂**，电源按官方 BOM 一律 **7.5V**。
六个阶段：S1 准备、S2 整臂电气与通信、S3 关节身份、S4 官方校准与核对、S5 官方驱动读数、S6 放行与归档。
全程不上扭矩。每一步的判定在服务端完成并写入会话日志，放行门只看日志，结论 PASS / HOLD / FAIL。
电机 ID 由装配环节在装配前写好；页面底部的「返修工具」只在需要单独重写某颗电机 ID 时用，不计入放行。

状态 beta：工作站 0.3.0 尚未在真机验收（`CLAUDE.md` 验收门）。

## Who uses it

| 角色 | 能做什么 | 权限/前提 |
|------|----------|----------|
| 测试员 | 走完 S1–S6，生成归档报告 | 用户在 `dialout` 组；台架有 7.5V 可调电源与竖直立柱 |
| 质量工程师 | 查看放行门、报告、判据表与异常记录，签核 | 能访问 `test_reports/Leader/<编号>/` |

## How to use

启动 `.venv/bin/python app/main.py --host 127.0.0.1 --port 8788`，打开 `http://127.0.0.1:8788`
（某条臂中途继续：`http://127.0.0.1:8788/?robot_id=<编号>`）。

1. **S1 准备**：电源 7.50V / ≥2A，整臂挂在立柱上自然下垂，菊花链 1→8、USB 接好。
   页面选左右臂 → 推荐编号（或填已有编号）→ 确认串口自动识别 → 填操作员 → 勾选 5 项 → 确认并记录。
2. **S2 整臂**：开始八轴扫描（先看过压限值是否 ≥ 7.5V、状态位是否为 0）→ 通信稳定（60 秒，期间不要动线）。
3. **S3 关节身份**：逐个选关节 → 开始 → 8 秒内**只动这一个关节**走完行程，其余扶住不动。
4. **S4 校准**：先做只读预检 → 开始官方校准 → 按提示：零位（整臂下垂、夹爪闭合）、夹爪闭合、夹爪张开
   （已有旧文件时按钮是「重新校准（覆盖旧文件）」）→ 保存后自动核对 → **断电 5 秒再上电** → 断电后再核对。
5. **S5 驱动读数**：零位读数（下垂、夹爪闭合、不动）→ 夹爪张开读数 →
   扫动 J6（只摆 J6，**一直摆到按钮恢复**，约 10 秒）→ 扫动 J7。页面给出交付给客户的遥操作命令。
6. **S6 放行**：刷新放行门 → 生成归档报告。

> **限制**：
> - 重新校准后，之前的核对和官方读数作废，需重做 S4 核对与 S5。
> - S7 与 follower 配对、S8 增强复测未覆盖，报告列为未验证项。
> - 待定标项（电压极差、保护限值、夹爪量程、读数方向等）只记录不判定，首批 3 台后定标。

## Screens / Routes / Endpoints

| 类型 | 位置 | 说明 |
|------|------|------|
| 页面 | `/`、`/?robot_id=<编号>` | 六阶段流程页 + 底部返修工具；阶段条按放行门画 |
| GET | `/api/config` | 关节表、档位、检查表条目、版本（工作站 / 判据 / LeRobot） |
| GET | `/api/ports`, `/api/detect-port` | 列串口 / 自动识别适配器 |
| GET | `/api/next-serial` | 推荐编号 |
| POST | `/api/checklist` | S1 准备检查表（含操作员） |
| POST | `/api/scan-all`（带 `hardware_profile`）, `/api/comm-stability` | S2 |
| POST | `/api/joint-identity` | S3 |
| POST | `/api/calibration/precheck` / `start` / `confirm` / `abort`；GET `/api/calibration/status` | S4 官方校准 |
| POST | `/api/verify-calibration`（`power_cycled`） | S4 核对 / 断电后核对 |
| POST | `/api/official-readout`（`mode` = zero / gripper_open / sweep） | S5 |
| GET | `/api/release-gate` | 放行门 |
| POST | `/api/archive` | 生成归档 |
| GET | `/api/export` | 下载会话 JSON |
| POST | `/api/scan-current`, `/api/init-id`, `/api/feedback-test` | 返修工具（不进放行门） |

## Edge cases

- 适配器 0 个提示插线；2 个以上不猜，要求手动选。无读写权限时提前给出 `usermod -aG dialout`。
- 实测电压与 7.5V 偏差 > 1.0 V 或超过 7.4 V + 1.0 V：返修写 ID 时拒绝执行；S2 判失败。
- 电机过压保护限值低于 7.5V：S2 记录项标红；若电机因此置告警位，S2 状态判失败。
- S3 跨度最大的不是被测关节：报出是哪颗在动——多半是电机装错位或线接错。
- 校准退出码 0 但无保存标记：`finished_unsaved`，S4 判失败。已有文件时在沿用提示处中止，不作废上一份校准。
- S5 选中的 LeRobot 不是单臂驱动、或校准文件不存在：直接报错，不放子进程去撞。
- 官方校准运行期间（含等确认的几分钟）其他串口操作立即被拒；串口正忙、编号格式错这类前置拦截照记日志，但不算该项的测试结果。
- 校准确认按钮每个提示只认一次，连点不会把下一个提示一起答掉。
- 归档时 Chromium 打印失败：保留 md / html，写 `_pdf_error.txt`。

## Configuration

- `--host` / `--port`（默认 `127.0.0.1:8788`）
- `--lerobot-calibrate=/path` 或 `OPENARM_MINI_LEROBOT_CALIBRATE`：指定官方校准程序；S5 用同一环境的 Python
- `HF_LEROBOT_CALIBRATION` / `HF_LEROBOT_HOME` / `HF_HOME` / `XDG_CACHE_HOME`：校准文件根目录（与 LeRobot 一致）
- 判据阈值：`app/criteria.py`（改动须升判据版本并记 `docs/WORKSTATION_CHANGELOG.md`）

## Related features

- none

## Provenance

- 任务: `.tasks/testbench/factory-test-flow/`
- 关键代码: `app/main.py`、`app/criteria.py`、`app/gate.py`、`scripts/openarm_mini_readout.py`
- 工程知识: `agent_wiki/index.md`
