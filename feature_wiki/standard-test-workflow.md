---
title: "testbench — OpenArm Mini 标准测试工作流"
category: feature
module: testbench
audience: [operator, engineer]
status: beta
since: 2026-09-29
updated: 2026-10-21
sources:
  - "app/main.py"
  - "app/messages.py"
  - "tests/test_workstation.py"
  - "tests/test_serial_errors.py"
  - "tests/test_i18n.py"
  - "README.md"
related_features: []
---

# testbench — OpenArm Mini 标准测试工作流

## What it is

OpenArm Mini leader 臂的产线测试页面：逐颗写电机 ID、只读质检、八轴扫描、驱动官方 LeRobot 校准、
一致性核对和测试数据导出。全程只读、不上扭矩；官方流程与本地质检在同一页编排，每一步标明归属。

状态为 beta：广播 ping 在电机接着时的行为、校准子进程的作答尚待真机验收（`CLAUDE.md` 验收门）。

## Who uses it

| 角色 | 能做什么 | 权限/前提 |
|------|----------|----------|
| 产线操作员 | 生成编号、逐颗写 ID 与质检、八轴扫描、引导完成官方校准、导出 JSON | 能确认供电档位、写 ID 时只接一颗电机；用户在 `dialout` 组 |
| 质量工程师 | 查看位置/电压/温度/`Phase`/配置字段、校准一致性结果与会话日志 | 八轴菊花链与校准文件可用 |

## How to use

启动：`.venv/bin/python app/main.py --host 127.0.0.1 --port 8788`，浏览器打开 `http://127.0.0.1:8788`。
右上角切中文 / English / Deutsch。

1. **准备** — 选左右臂，点「推荐编号」（`OAM` + `L`/`R` + 日期 + 序号），确认供电档位；串口自动识别（恰好一个适配器时自动选中）。
2. **逐颗写 ID 与只读质检** — 按 8 → 1 的顺序，每颗走「扫描 → 写 ID → 断电 5 秒复扫 → 只读反馈测试」，四步全过才进入下一颗。
3. **八轴只读扫描** — 恢复 1→8 菊花链，读 8 颗的 ID、型号、位置、电压、温度、`Phase` 与关键配置。
4. **校准与一致性核对** — 先只读预检，再「开始官方校准」：零位（整臂下垂、夹爪闭合）→ 夹爪闭合 → 夹爪张开；保存后自动核对。
5. **导出归档** — 下载本次测试 JSON。

> **限制**：
> - 写 ID 时总线上只能接当前这颗电机；广播收到多于一个应答会直接报错。
> - 已有校准文件时，确认按钮是「重新校准（覆盖旧文件）」。不要在终端里直接回车沿用旧文件。
> - 没有遥操作配对验证；交付时必须告诉客户遥操作要带 `--teleop.side=left|right`。
> - 只覆盖单臂；`bi_openarm_mini` 双臂校准的文件核对会报「未找到」。
> - 第 5 步只导出 JSON，Markdown/PDF 归档脚本尚未实现。

## Screens / Routes / Endpoints

| 类型 | 位置 | 说明 |
|------|------|------|
| 页面 | `/` | 五阶段流程页 |
| 接口 GET | `/api/config` | 关节表、供电档位、编号规则、选中的 LeRobot 与驱动代 |
| 接口 GET | `/api/ports`, `/api/detect-port` | 列串口 / 按 USB 身份自动识别适配器 |
| 接口 GET | `/api/next-serial` | 推荐当日下一个未用编号 |
| 接口 POST | `/api/scan-current` | 广播 ping 找当前单颗电机（可选深度扫描） |
| 接口 POST | `/api/init-id` | 写 ID 与波特率（EEPROM） |
| 接口 POST | `/api/feedback-test` | 只读反馈测试：读起点 → 手动摆动 → 再读 |
| 接口 POST | `/api/scan-all` | 八轴只读扫描 |
| 接口 POST | `/api/motor-params` | 单颗电机参数读取 |
| 接口 POST | `/api/reconnect-port` | 重连串口 |
| 接口 POST | `/api/calibration/precheck` | 校准前编码器预检，只读 |
| 接口 POST | `/api/calibration/start` / `confirm` / `abort` | 启动、确认、中止官方 `lerobot-calibrate` 子进程 |
| 接口 GET | `/api/calibration/status` | 轮询校准阶段与输出 |
| 接口 POST | `/api/verify-calibration` | 校准文件与 EEPROM 一致性核对 |
| 接口 GET | `/api/export` | 导出本次测试 JSON |

## Edge cases

- 适配器 0 个：提示插线并说明 `/dev/ttyS*` 不是适配器；2 个以上：不猜，要求手动选。
- 有适配器但无读写权限：提前警告并给出 `usermod -aG dialout` 命令。
- 实测电压与所选档位偏差 > 1.0 V 或超过 7.4 V：拒绝扫描与写 ID。
- 串口打不开：三语 `ConnectionError` 并释放串口锁，不会卡在「串口正忙」。
- 选中的 LeRobot 是双臂代或没有 `openarm_mini`：第 4 步启动前拦下并说明原因。
- 校准退出码 0 但无保存标记：判 `finished_unsaved`，不串联一致性核对。
- 断电后 `Acceleration` 读到 0：只提示「运行期字段待重写」，不判不合格。

## Configuration

- `--host` / `--port`（默认 `127.0.0.1:8788`）
- `--lerobot-calibrate=/path` 或环境变量 `OPENARM_MINI_LEROBOT_CALIBRATE`：指定官方校准程序；不指定时项目内 `.venv-lerobot/` 优先
- `HF_LEROBOT_CALIBRATION` / `HF_LEROBOT_HOME` / `HF_HOME` / `XDG_CACHE_HOME`：决定校准文件根目录（与 LeRobot 一致）

## Related features

- none

## Provenance

- 任务: 无任务目录；见 git 898bf46 – 7494016（2026-09-29）
- 关键代码: `app/main.py`（`CalibrationSession`、`FeetechSdkClient`、`AppHandler`）、`app/messages.py`
- 工程知识: `agent_wiki/index.md`
