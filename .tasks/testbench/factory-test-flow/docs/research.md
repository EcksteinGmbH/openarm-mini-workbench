# 前期调研：官方流程、兄弟工站做法、现有实现差距

> 调研日期：2026-10-21。官方来源为联网核对；本机事实为当日命令输出。
> 推断与事实分开标注。

## 1. 官方流程现状

来源：[pkooij/open-arms-mini README](https://github.com/pkooij/open-arms-mini/blob/main/README.md)、
[BOM.md](https://github.com/pkooij/open-arms-mini/blob/main/BOM.md)、
[lerobot `teleoperators/openarm_mini/`](https://github.com/huggingface/lerobot/tree/main/src/lerobot/teleoperators/openarm_mini)。

1. 按 BOM 采购、按 README 参数打印
2. `pip install 'lerobot[feetech]'`
3. **装配前**写 ID：`lerobot-setup-motors --teleop.type=openarm_mini --teleop.port=…`（8→1，每次一颗）
4. 10 步装配，1→8 菊花链
5. `lerobot-find-port`
6. `lerobot-calibrate …`（零位：整臂下垂、夹爪闭合；夹爪闭合；夹爪张开）
7. `lerobot-teleoperate …`

事实：
- **官方没有任何 leader 验收判据或合格阈值**。LeRobot `docs/source/` 仍无 openarm_mini 专页；Enactic 的 OpenArm 文档不涉及 Mini。
- **README 第 7 步照抄跑不起来**：`TeleoperateConfig.robot` 为必填（本机 eb7a54c `scripts/lerobot_teleoperate.py:138` 核实），
  README 命令没有 `--robot.*`，也没有 `--teleop.side`。
- `lerobot-find-joint-limits` 记录的是 follower 范围，需要 robot+teleop+URDF，不是 leader 验收工具。
- 硬件仓库自 2026-03-26（0628e081）无提交，与 `docs/hardware-reference.md` 一致。

### LeRobot 版本（本机核对 PyPI wheel）

| 版本 | `openarm_mini` 代 | 备注 |
|---|---|---|
| PyPI 0.4.4 | 双臂（`port_right/port_left`） | 本机 `.venv-lerobot.py310-pypi` |
| PyPI 0.5.0 | 双臂 | |
| **PyPI 0.6.1**（2026-08-03，最新发布） | **单臂**（`port`、`side`），含 `bi_openarm_mini` | Requires-Python ≥3.12；`feetech-servo-sdk>=1,<2` |
| git eb7a54c（报 0.6.2） | 单臂 | 本机 `.venv-lerobot`；与 0.6.1 的 `openarm_mini.py` 仅有变量改名和一个 `calibration is None` 保护的差异，`feetech/`、`motors_bus.py`、`teleoperator.py` 完全相同 |

更正：`agent_wiki/openarm-mini-driver-generations.md` 与提交 7494016 说"PyPI 没有单臂版"，对 0.6.1 不成立。

### LeRobot main 在 eb7a54c 之后的变化（尚未发布）

- #4672（146d8474，10-16）：Feetech/Dynamixel 合并为 rustypot `SerialMotorsBus`，删 `encoding_utils.py`、scservo 依赖；
  找电机波特率顺序改变；`setup_motor` 写后 ping 回读；状态告警位不再抛异常；
  **中点偏移超限不再抛 `Magnitude … exceeds`，改为静默钳到 ±2047**。
- #4867（326484d7，10-19）：沿用旧校准提示改为
  `Press ENTER to use provided calibration file associated with the id {id}, or type 'c' and press ENTER to run calibration:`，
  日志改为 `Writing calibration file associated with the id …`。
- 开放 PR #4913：双臂默认 id 改 `left`/`right`。

推断：升级到含上述提交的版本会使工作站的沿用提示识别、`offset_overflow` 诊断失效；升级前必须先改特征串与测试。

### 可用的官方/规格数值

- BOM：STS3215-C046，7.4 V，1:147；电源 7.5 V ≥2 A。
- LeRobot：1 Mbps；`Return_Delay_Time=0`、`Maximum_Acceleration=254`、`Acceleration=254`、`Operating_Mode=0`；
  `Phase` bit4 必须清零、openarm_mini 写 12；J1–J7 量程 0..4095；同型号电机固件必须一致（连接时校验）。
  寄存器：`Firmware_Major/Minor` 0/1、`Max_Temperature_Limit` 13、`Max_Voltage_Limit` 14、`Min_Voltage_Limit` 15、`Present_Load` 60、`Status` 65。
- openarm_follower 关节限位（度）：J1 ±75；J2 左 −90..9 / 右 −9..90；J3 ±85；J4 0..135；J5 ±85；J6 ±40；J7 ±80；夹爪 −65..0。
  Mini 侧 `GRIPPER_TELEOP_TO_DEGREES = −0.65`，0..100 → 0..−65°。
- Feetech 规格书（仅找到第三方托管的机翻版，型号 1:345 非 C046，**低可信**）：工作 4–7.4 V，超出进过压保护（阈值可改）；
  >70 °C 关扭矩；工作温度 −20..60 °C。C046 的实际限值须真机只读 EEPROM 确认。

## 2. 兄弟工站的出厂测试做法

### SO-ARM101（`so-arm101-workbench`）

- 五阶段：准备 → 逐颗写 ID + 质检 → 六轴只读扫描 → 官方校准（保存后核对 #1，断电 5 s 核对 #2）→ 导出 + 断电外观检查 + 归档脚本。
- Leader：只读人工位置反馈 |Δ| ≥ 5 计数；温度只记录；供电 5 V/4 A 台架档，±1.0 V 保护。
- 增强复测 R03：静态 600 s / 动态 300 s 0 失败、3 次电源循环、USB 重新枚举。
- 归档：`test_reports/{Follower|Leader}/<编号>/<编号>_SO-ARM101_基础测试记录.{md,pdf}` + 校准参数 json + 会话日志；
  文档号 `SO101-{F|L}-BENCH-RESULT-<编号>-R01`；编号索引；作废号不复用；`.sessions/` 忽略、归档提交。
- 受控三件套 DEL/QMR/AUD（`HT-QC-SOARM-*-R01`），测试员/复核/批准签署；未验证项不得解释为通过。
- **教训**：Leader 判定只在前端 JS，会话日志无判定，导致 SOL20260921101、SOL20261016101、SOL20261019101 的质检节为"本次未采集"
  而结论仍为"基础功能通过"；受控文档生成器与新记录标题不兼容，08-24 后的臂没有三件套。

### OpenARM（达妙 CAN 整臂）

- 顺序：单电机 ID → 整臂静态通信验收 → TIMEOUT 标准化 → 官方动态零位 → 复核 → 官方 Demo → 正式报告。
- 放行门：PASS / HOLD；blocking（缺必做记录、版本冲突、未硬件验证的锁定项）与 warning（缺原始证据等，需处置或重跑）。
- 证据选取：同 CN、同侧、同 profile；各阶段分开取证；测量值不得用常量填；"记录"项不参与 PASS/FAIL。
- 阈值写依据链（`docs/official/derived-thresholds.md`），推不出写 undecided；golden baseline 只用于发现变化。
- `VERSION` + `docs/WORKSTATION_CHANGELOG.md`，MAJOR/MINOR/PATCH 按对工作流/报告/硬件的影响分级，条目含 Verification 与 Operational Notes。
- 签核具名：Test Engineer、Project Lead；Quality Approval 为空时报告只作工程证据。

## 3. 现有实现与真机数据

### 真机会话 `OAML2026092901`（2026-09-29，`test_reports/.sessions/`）

- 写 ID 8/8、反馈测试 8/8（跨度 283–2327 计数，J5 仅 283）、整臂扫描 8/8（第一次 1/8 因未接菊花链）、预检 5 次（3 次 7/8 → 修复取模后 8/8）。
- 校准启动 4 次：一次代码缺函数报错、一次被双臂代拦下、最后一次 11:54 启动单臂代后**无完成记录**，
  校准目录 `~/.cache/huggingface/lerobot/calibration/teleoperators/openarm_mini/` 为空，**无一致性核对记录**。
  → S5 及之后从未在真机完整跑通。
- 5 V 台架档下实测：电压 4.9–5.0 V，温度 27–29 °C，`Status`=0，`Torque_Enable`=0。
- 出厂 EEPROM：`Phase=92`（bit4 置位）、`Max_Acceleration=250`、`Acceleration=0`、`Max_Torque_Limit=1000`、
  `Protection_Current=300`、`Overload_Torque=80`、PID 32/0/32、量程 0..4095、`Homing_Offset=0`。

### 现有实现的差距

| 现状 | 问题 |
|---|---|
| `scan_all_motors_read_only` 的 `ok` = 能读到 | 不判温度、电压、状态位、扭矩、固件 |
| `feedback_test` 只判跨度 ≥ 100 计数（≈9°） | 过低；不判连续性 |
| 无关节身份测试 | 装错位/接错线的电机发现不了 |
| 核对只在保存后做一次 | 无断电后第二次核对（SO 有） |
| 无官方驱动读数验证 | side、6/7 对调、夹爪映射、零位从未被端到端检查 |
| 无装配/外观检查记录 | 人工项不留痕 |
| 导出只有 JSON | 无报告、无放行门、无编号索引 |
| 无 VERSION/CHANGELOG | 报告无法写工作站版本 |
| 判定部分在前端 | 有 SO 同款"缺项仍通过"的风险（待 spec 阶段逐项核对） |
