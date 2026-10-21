---
title: "testbench — OpenArm Mini 出厂测试工作流"
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

# testbench — OpenArm Mini 出厂测试工作流

## What it is

OpenArm Mini leader 臂的出厂测试页面。按官方 7 步流程编排为 S0–S6、S9 八个阶段：
写电机 ID、装配检查、整臂电气与通信、关节身份、官方校准与核对、官方驱动读数验证、放行与归档。
全程不上扭矩。每一步的判定在服务端完成并写入会话日志，放行门只看日志，结论 PASS / HOLD / FAIL。

状态 beta：工作站 0.2.0 的 S3 通信稳定、S4、S6 与校准结局记录尚未在真机验收（`CLAUDE.md` 验收门）。

## Who uses it

| 角色 | 能做什么 | 权限/前提 |
|------|----------|----------|
| 产线操作员 | 走完 S0–S9，生成归档报告 | 用户在 `dialout` 组；台架有可调电源与竖直立柱 |
| 质量工程师 | 查看放行门、报告、判据表与异常记录，签核 | 能访问 `test_reports/Leader/<编号>/` |

## How to use

启动 `.venv/bin/python app/main.py --host 127.0.0.1 --port 8788`，打开 `http://127.0.0.1:8788`
（某条臂中途继续：`http://127.0.0.1:8788/?robot_id=<编号>`）。

1. **S0 准备**：选左右臂 → 推荐编号 → 供电档位选「台架 5V」→ 确认串口自动识别 → 填操作员 → 勾选来料与工位 → 确认并记录。
2. **S1 写 ID**（装配前，台架 5.00V / 4.00A）：按页面从 J8 夹爪到 J1，每次**只接一颗电机**：
   扫描 → 写入 → 断电 5 秒再上电 → 复扫 → 只读反馈（8 秒内用手转舵盘，尽量转大角度）。
3. **S2 装配**：按官方 10 步装配，1→8 接菊花链，逐项勾选 → 确认并记录。
4. **S3 整臂**：电源改 7.50V / 2.00A，**页面供电档位切到「整臂 7.5V」**，整臂固定在立柱上自然下垂 →
   开始八轴扫描 → 通信稳定（60 秒，期间不要动线）。
5. **S4 关节身份**：逐个选关节 → 开始 → 8 秒内**只动这一个关节**走完行程，其余扶住不动。
6. **S5 校准**：先做只读预检 → 开始官方校准 → 按提示：零位（整臂下垂、夹爪闭合）、夹爪闭合、夹爪张开
   （已有旧文件时按钮是「重新校准（覆盖旧文件）」）→ 保存后自动核对 → **断电 5 秒再上电** → 断电后再核对。
7. **S6 驱动读数**：零位读数（下垂、夹爪闭合、不动）→ 夹爪张开读数 → 扫动 J6（只摆 J6，**一直摆到按钮恢复**，约 10 秒）→ 扫动 J7。
   页面给出交付给客户的遥操作命令。
8. **S9 放行**：断电外观检查，勾选终检 → 刷新放行门 → 生成归档报告。

> **限制**：
> - S3–S6 必须在整臂 7.5V 档下做；台架档的扫描不计入放行门。
> - 重新校准后，之前的核对和官方读数作废，需重做 S5 核对与 S6。
> - S7 与 follower 配对、S8 增强复测未覆盖，报告列为未验证项。
> - 待定标项（反馈建议跨度、电压极差、夹爪量程、读数方向等）只记录不判定，首批 3 台后定标。

## Screens / Routes / Endpoints

| 类型 | 位置 | 说明 |
|------|------|------|
| 页面 | `/`、`/?robot_id=<编号>` | 八阶段流程页；阶段条按放行门画 |
| GET | `/api/config` | 关节表、档位、检查表条目、版本（工作站 / 判据 / LeRobot） |
| GET | `/api/ports`, `/api/detect-port` | 列串口 / 自动识别适配器 |
| GET | `/api/next-serial` | 推荐编号 |
| POST | `/api/checklist` | S0 / S2 / S9 检查表（S0 含操作员） |
| POST | `/api/scan-current`, `/api/init-id`, `/api/feedback-test` | S1 |
| POST | `/api/scan-all`（带 `hardware_profile`）, `/api/comm-stability` | S3 |
| POST | `/api/joint-identity` | S4 |
| POST | `/api/calibration/precheck` / `start` / `confirm` / `abort`；GET `/api/calibration/status` | S5 官方校准 |
| POST | `/api/verify-calibration`（`power_cycled`） | S5 核对 / 断电后核对 |
| POST | `/api/official-readout`（`mode` = zero / gripper_open / sweep） | S6 |
| GET | `/api/release-gate` | 放行门 |
| POST | `/api/archive` | 生成归档 |
| GET | `/api/export` | 下载会话 JSON |

## Edge cases

- 适配器 0 个提示插线；2 个以上不猜，要求手动选。无读写权限时提前给出 `usermod -aG dialout`。
- 实测电压与档位偏差 > 1.0 V 或超过 7.4 V + 1.0 V：拒绝扫描与写 ID。
- 写 ID 时广播收到多于一个应答：直接报错并列出 ID。
- S4 跨度最大的不是被测关节：报出是哪颗在动——多半是电机装错位或线接错。
- 校准退出码 0 但无保存标记：`finished_unsaved`，S5 判失败。
- S6 选中的 LeRobot 不是单臂驱动、或校准文件不存在：直接报错，不放子进程去撞。
- 归档时 Chromium 打印失败：保留 md / html，写 `_pdf_error.txt`。
- 官方校准运行期间（含等确认的几分钟）其他串口操作立即被拒；串口正忙、编号格式错这类前置拦截照记日志，但不算该项的测试结果。
- 校准确认按钮每个提示只认一次，连点不会把下一个提示一起答掉。

## Configuration

- `--host` / `--port`（默认 `127.0.0.1:8788`）
- `--lerobot-calibrate=/path` 或 `OPENARM_MINI_LEROBOT_CALIBRATE`：指定官方校准程序；S6 用同一环境的 Python
- `HF_LEROBOT_CALIBRATION` / `HF_LEROBOT_HOME` / `HF_HOME` / `XDG_CACHE_HOME`：校准文件根目录（与 LeRobot 一致）
- 判据阈值：`app/criteria.py`（改动须升判据版本并记 `docs/WORKSTATION_CHANGELOG.md`）

## Related features

- none

## Provenance

- 任务: `.tasks/testbench/factory-test-flow/`
- 关键代码: `app/main.py`、`app/criteria.py`、`app/gate.py`、`scripts/openarm_mini_readout.py`
- 工程知识: `agent_wiki/index.md`
