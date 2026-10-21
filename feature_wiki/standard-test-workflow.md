---
title: "testbench — OpenArm Mini 出厂测试工作流（装配后写 ID，7.5V）"
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
  - "docs/lerobot-openarm-mini.md"
  - ".tasks/testbench/factory-test-flow/docs/test-plan.md"
related_features: []
---

# testbench — OpenArm Mini 出厂测试工作流（装配后写 ID，7.5V）

## What it is

OpenArm Mini leader 臂的出厂测试页面。测的是**装配完成的整臂**，电源按官方 BOM 一律 **7.5V**；
电机 ID 在装配后由本页逐颗写，ID 与关节位置一一对应。七个阶段：S1 准备、S2 装配后写 ID、S3 整臂电气与通信、
S4 关节身份、S5 官方校准与核对、S6 官方驱动读数、S7 放行与归档。全程不上扭矩。
每一步的判定在服务端完成并写入会话日志，放行门只看日志，结论 PASS / HOLD / FAIL。

状态 beta：工作站 0.4.0 尚未在真机验收（`CLAUDE.md` 验收门）。

## Who uses it

| 角色 | 能做什么 | 权限/前提 |
|------|----------|----------|
| 测试员 | 走完 S1–S7，生成归档报告 | 用户在 `dialout` 组；台架有 7.5V 可调电源与竖直立柱 |
| 质量工程师 | 查看放行门、报告、判据表与异常记录，签核 | 能访问 `test_reports/Leader/<编号>/` |

## How to use

启动 `.venv/bin/python app/main.py --host 127.0.0.1 --port 8788`，打开 `http://127.0.0.1:8788`
（某条臂中途继续：`http://127.0.0.1:8788/?robot_id=<编号>`）。

1. **S1 准备**：电源 7.50V / ≥2A，整臂挂在立柱上自然下垂，驱动板接电源与 USB。
   页面选左右臂 → 推荐编号（或填已有编号）→ 确认串口自动识别 → 填操作员 → 勾选 5 项 → 确认并记录。
2. **S2 写 ID**（顺序 J8 夹爪 → J1）：每颗电机——
   把驱动板的线**直接接到这颗电机、断开它与相邻电机的连线** → 扫描（广播必须只有它）→ 写入 →
   断电 5 秒再上电 → 复扫 → 开始确认，8 秒内**只来回摆这个关节**。四步全过，页面自动换下一颗。
3. **S3 整臂**：恢复 1→8 菊花链 → 开始八轴扫描（先看过压限值是否 ≥ 7.5V、状态位是否为 0）→
   通信稳定（60 秒，期间不要动线）。
4. **S4 关节身份**：逐个选关节 → 开始 → 8 秒内**只动这一个关节**走完行程，其余扶住不动。
5. **S5 校准**：先做只读预检 → 开始官方校准 → 按提示：零位（整臂下垂、夹爪闭合）、夹爪闭合、夹爪张开
   （已有旧文件时按钮是「重新校准（覆盖旧文件）」）→ 保存后自动核对 → **断电 5 秒再上电** → 断电后再核对。
   校准写入每颗电机的内容见 `docs/lerobot-openarm-mini.md`「校准到底校准什么」。
6. **S6 驱动读数**：零位读数（下垂、夹爪闭合、不动）→ 夹爪张开读数 →
   扫动 J6（只摆 J6，**一直摆到按钮恢复**，约 10 秒）→ 扫动 J7。页面给出交付给客户的遥操作命令。
7. **S7 放行**：刷新放行门 → 生成归档报告。

> **限制**：
> - 重写某颗 ID 后，它之前的复扫和动关节确认作废，需重做。
> - 重新校准后，之前的核对和官方读数作废，需重做 S5 核对与 S6。
> - S8 与 follower 配对、S9 增强复测未覆盖，报告列为未验证项。
> - 待定标项（确认摆幅建议值、电压极差、保护限值、夹爪量程、读数方向等）只记录不判定，首批 3 台后定标。

## Screens / Routes / Endpoints

| 类型 | 位置 | 说明 |
|------|------|------|
| 页面 | `/`、`/?robot_id=<编号>` | 七阶段流程页；阶段条按放行门画 |
| GET | `/api/config` | 关节表、档位、检查表条目、版本（工作站 / 判据 / LeRobot） |
| GET | `/api/ports`, `/api/detect-port` | 列串口 / 自动识别适配器 |
| GET | `/api/next-serial` | 推荐编号 |
| POST | `/api/checklist` | S1 准备检查表（含操作员） |
| POST | `/api/scan-current`, `/api/init-id`, `/api/feedback-test` | S2 扫描 / 写 ID / 动关节确认 |
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
- S2 广播收到多于一个应答：直接报错并列出 ID——说明相邻电机的线没断开。
- 实测电压与 7.5V 偏差 > 1.0 V 或超过 7.4 V + 1.0 V：S2 扫描与写 ID 拒绝执行；S3 判失败。
- S2 动关节确认读数没变：判失败——多半是动错了关节，或这颗电机不是这个关节的。
- 电机过压保护限值低于 7.5V：S3 记录项标红；若电机因此置告警位，S3 状态判失败。
- S4 跨度最大的不是被测关节：报出是哪颗在动——菊花链恢复时接错，或 ID 与位置不符。
- 校准退出码 0 但无保存标记：`finished_unsaved`，S5 判失败。已有文件时在沿用提示处中止，不作废上一份校准。
- S6 选中的 LeRobot 不是单臂驱动、或校准文件不存在：直接报错，不放子进程去撞。
- 官方校准运行期间（含等确认的几分钟）其他串口操作立即被拒；串口正忙、编号格式错这类前置拦截照记日志，但不算该项的测试结果。
- 校准确认按钮每个提示只认一次，连点不会把下一个提示一起答掉。
- 归档时 Chromium 打印失败：保留 md / html，写 `_pdf_error.txt`。

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
