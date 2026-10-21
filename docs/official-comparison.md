# 与官方的逐项核对

核对日期 **2026-09-29**。对照的官方来源只有两处：

| 来源 | 内容 | 版本 |
|---|---|---|
| [pkooij/open-arms-mini](https://github.com/pkooij/open-arms-mini) | `README.md`、`BOM.md` —— BOM、打印参数、电机 ID 表、装配顺序、官方命令 | `main` |
| [huggingface/lerobot](https://github.com/huggingface/lerobot) | `teleoperators/openarm_mini/`、`teleoperators/bi_openarm_mini/`、`teleoperators/teleoperator.py`、`motors/motors_bus.py`、`motors/feetech/`、`scripts/lerobot_{calibrate,setup_motors,find_port}.py`、`utils/constants.py` | `main` |

LeRobot 的 `docs/source/` 里**没有** openarm_mini 的文档页（`openarm.mdx` 讲的是达妙那套
CAN 版 OpenARM）。所以 Mini 唯一的官方流程文档就是硬件仓库的 README。

以下分三类：**一致**、**差异（有意）**、**缺失或待改**。

---

## 一致（已逐项核对出处）

| 项 | 本工作站 | 官方出处 |
|---|---|---|
| 关节 ID | 1–8 ↔ J1–J8 | 硬件 README「Motor IDs」 |
| 电机键名 | `joint_1`…`joint_7`, `gripper` | `openarm_mini.py` `motors` 字典 |
| 型号号 | 777 | `MODEL_NUMBER_TABLE["sts3215"]` |
| 编码器分辨率 | 4096 | `MODEL_RESOLUTION["sts3215"]` |
| 写 ID 顺序 | 夹爪 → `joint_1` | `setup_motors()` 的 `reversed(self.bus.motors)` |
| 写 ID 步骤 | 切到电机现波特率 → 关扭矩 → 写 ID → 写 1000000 | `MotorsBus.setup_motor()` |
| EEPROM 解锁 | 关扭矩时写 `Lock=0` | `feetech._disable_torque()` 同时写 `Torque_Enable=0` 和 `Lock=0` |
| 波特率搜索表 | 1M, 500k, 250k, 128k, 115200, 57600, 38400, 19200 | `STS_SMS_SERIES_BAUDRATE_TABLE` 的键序，8 档、顺序一致 |
| 中点偏移公式 | `homing = 编码器读数 − 2047` | `feetech._get_half_turn_homings()`：`pos - int((4096-1)/2)` |
| 位置折算方向 | `编码器 = Present + Homing` | `feetech` 注释：`Present_Position = Actual_Position - Homing_Offset` |
| 关节量程 | 写死 `0..4095` | `openarm_mini.calibrate()` 非夹爪分支 |
| 夹爪量程 | 实测闭合/张开 | 同上，夹爪分支 |
| `Phase` | 校准后期望 12 | `calibrate()` 给全部电机 `write("Phase", motor, 12)` |
| 运行期参数 | `Return_Delay_Time=0`、`Maximum_Acceleration=254`、`Acceleration=254`、`Operating_Mode=0` | `feetech.configure_motors()` 默认参数 |
| `Acceleration` 断电归零不判负 | 只提示 | 地址 41 在 SRAM，`configure()` 每次连接重写 |
| 校准文件路径 | `<校准根>/teleoperators/openarm_mini/<编号>.json` | `Teleoperator.__init__` + `TELEOPERATORS` 常量 |
| 一致性核对只比 3 项 | `homing_offset` / `range_min` / `range_max` | `write_calibration()` 只写这三个寄存器；官方 `is_calibrated` 也只比这三项 |
| 校准阶段提示串 | 4 条 + 保存标记 | `openarm_mini.calibrate()` 的 `input()` 文本与结尾 `print` |
| 失败特征串 | 5 条 | `encoding_utils.py:23`、`motors_bus.py:497/538`、`openarm_mini.py`、draccus/argparse |

`drive_mode` 存在校准文件里但**不写进任何寄存器**，所以无法与电机比对——官方
`read_calibration()` 甚至恒返回 `drive_mode=0`。本工作站同样不比它，这是正确的。

---

## 差异（有意为之，不打算改）

| 项 | 官方 | 本工作站 | 理由 |
|---|---|---|---|
| 找串口 | `lerobot-find-port`：让人拔掉 USB、对比前后端口列表，返回**内核名** | 按 USB 身份（vid/pid）+ `/dev/serial/by-id` 别名自动识别，返回**稳定别名** | 产线不该每次都拔线；内核名每次重新枚举都会变 |
| 写 ID 后 | 直接进入下一颗 | 强制**断电 5 秒复扫** | ID 与波特率在 EEPROM，不断电复扫分不清「写进去了」和「只在本次上电周期生效」 |
| 质检 | 无 | 只读反馈测试、八轴只读扫描 | 产线需要留痕的合格判据；全程不上扭矩 |
| 校准后核对 | 无（`is_calibrated` 是运行时判断，不产生记录） | 一致性核对，比对文件与 EEPROM | 归档需要证据 |
| 记录 | 无 | 会话日志 jsonl + 编号规则 + 导出 | 产线追溯 |
| 沿用旧校准的提示 | 裸回车 = 沿用，官方不提示后果 | 识别为独立阶段，按钮改成「重新校准（覆盖旧文件）」并回答 `c` | 裸回车会让官方程序什么都不测就返回退出码 0，随后核对拿同一份旧文件比会报 8/8 假合格 |
| 行程试扫 / 停放窗口 | 无 | 也没有 | Mini 的关节量程是驱动写死的整圈，不存在 SO-101 那条「行程必须落进停放位 ±2047」的约束；照搬会拦下正常关节 |

---

## 缺失或待改

### A1 · 单电机识别方式偏离官方（已改，2026-09-29；电机在位行为仍需真机验收）

**官方**（`feetech._find_single_motor_p0`，STS3215 走协议 0）：每档波特率发**一个广播
ping**，返回所有应答的 ID，再读它们的型号号。最坏 8 个广播包。

**本工作站**：每档波特率逐个试 ID（`[1] + range(0,254)`），最坏 8 × 254 = **2032 次单读**。
本机实测**没有电机应答时要 105 秒**，期间串口独占，其他操作报「串口正忙」。

这套逐个试的写法是从 SO-ARM101 工作站带过来的，**不是官方行为**。

改用广播 ping 还有一个额外收益：广播会返回**总线上所有**应答 ID，于是「写 ID 时只连
一颗电机」这个安全前提**第一次变得可验证**。现在无论官方还是本工作站，多接了几颗都只会
取到第一个应答，看不出来。

**已改**：`FeetechSdkClient.broadcast_ping()` 逐行移植 LeRobot 的 `_broadcast_ping()`
（已发布的 `scservo_sdk` 在协议 0 下没有广播 ping，官方自己拼包，这里照做；所需原语
`BROADCAST_ID`/`INST_PING`/`PKT_*`/`txPacket`/`setPacketTimeoutMillis`/`isPacketTimeout`/
`readPort` 在 `feetech-servo-sdk` 1.0.0 里都有）。`find_single_sts3215()` 改为按官方方式
每档波特率发一个广播包。逐个试 ID 的老路保留为 `deep_scan`，**默认关闭**。

本机实测（适配器在位、电机未上电）：

| 路径 | 耗时 |
|---|---|
| 广播 ping（默认，官方同法） | **8.0 秒** |
| 深度扫描（显式勾选，非官方） | 112.9 秒 |

比官方多的那道闸：广播返回**所有**应答，`len(answered) > 1` 时直接报错并列出 ID。
官方只取第一个应答，多接了电机发现不了——而写 ID 时多接一颗，两颗会被改成同一个 ID。
这是在**执行**官方那句「Connect the controller board to the '<motor>' motor only」，
不是偏离它。

电机在位时的行为（能否一次问到、多接时是否如期报错）仍需真机验收。

### A2 · 校准根目录被写死（已改正，2026-09-29）

原先写死 `~/.cache/huggingface/lerobot/calibration`。官方 `utils/constants.py` 的优先级是
`HF_LEROBOT_CALIBRATION` > `HF_LEROBOT_HOME/calibration` > `HF_HOME/lerobot/calibration` >
`$XDG_CACHE_HOME/huggingface/lerobot/calibration`。装机时把 `HF_HOME` 指到大盘是常见做法，
写死会让工作站在错误目录找文件：给一台**已校准**的臂报「未找到校准文件」，
或者拿一份过期旧文件核对并报出 8/8 合格。

### A3 · 启动哪个 LeRobot 曾由字母序决定（已改，2026-09-29）

本工作站与 SO-ARM101 工作站原先用同一段查找逻辑：
`sorted(glob("~/Projects/.venvs/*/bin/lerobot-calibrate"))` **取第一个**。
在那个共享目录里新建一个 venv，会按字母序悄悄改变**两个**工作站选中的 LeRobot：

| 新 venv 命名 | 两个工作站都会选中 | SO-101 |
|---|---|---|
| `openarm-mini-lerobot` | `openarm-mini-lerobot` | 被抢走 |
| `lerobot-latest` | `lerobot-latest` | 被抢走 |
| `zz-openarm-mini` | `so-arm101-lerobot-0.4.4` | 不受影响 |

靠字母顺序来保证一个安全属性是不能接受的。现在的解析优先级：

1. `--lerobot-calibrate` 参数
2. `OPENARM_MINI_LEROBOT_CALIBRATE` 环境变量
3. **项目内** `.venv-lerobot/` 或 `.venv/`
4. `PATH`
5. 共享 `~/Projects/.venvs` / `~/.venvs`（保留兼容，页面会标明「共享目录」）

显式指定的路径无效时**直接报错**，不静默回退——打错路径却回退到另一个 LeRobot，
正是这个参数要防的事。页面上会显示将要启动哪个可执行文件、来源是哪一级。

**给本工作站装 LeRobot 要放进项目目录**（`.venv-lerobot/`），不要放到
`~/Projects/.venvs/`：那个共享目录被 SO-ARM101 工作站扫描，项目内的它看不见。

只改了本仓库。SO-ARM101 工作站有同样的隐患，但那是另一个仓库、有自己的验收门，未改动。

### B1 · 双臂 `bi_openarm_mini` 未覆盖

官方有 `bi_openarm_mini`，它把两个 `OpenArmMini` 组合起来，per-arm 的 id 变成
`<id>_left` / `<id>_right`，**而且校准文件仍然落在 `teleoperators/openarm_mini/` 目录下**
（因为每个子臂的 `name` 还是 `openarm_mini`）。

本工作站只走单臂路径。如果客户按双臂校准（`--teleop.type=bi_openarm_mini`），
目录里会出现 `<id>_left.json` / `<id>_right.json`，而本工作站的编号规则不匹配这种名字，
一致性核对会报「未找到校准文件」。这是交付后的使用方式差异，**不影响台架流程**，
但得知道有这回事。

### B2 · 遥操作配对验证未覆盖

官方流程最后一步是 `lerobot-teleoperate`，需要一条 follower 臂。本工作站到第 5 步导出为止，
没有遥操作验证环节。

补充（2026-10-21 核对）：README 里的这条命令**本身就跑不起来**。`TeleoperateConfig.robot` 是必填字段，
而硬件仓库提交 8d150667（2026-03-26）把原来的 `--robot.type=so101_follower …` 删掉后没有换成 Open Arms follower。
可用写法需要补 `--robot.type=openarm_follower --robot.port=<can> --robot.side=…` 和 `--teleop.side=…`。

### B3 · `--teleop.side` 官方 README 没提，交付时会出问题

驱动的方向翻转表只在 `side` 非空时生效：

```python
SIDE_MOTORS_TO_FLIP = {
    "left":  ["joint_1", "joint_3", "joint_4", "joint_5", "joint_6", "joint_7"],
    "right": ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_7"],
}
self._motors_to_flip = SIDE_MOTORS_TO_FLIP.get(config.side, []) if config.side else []
```

而**官方硬件 README 的 `lerobot-teleoperate` 命令里没有 `--teleop.side`**。照它逐字抄，
`side=None` → 翻转表为空 → 8 个关节里有 6 个方向是反的。

本工作站记录了左右臂（编号里的 `L`/`R`），但从不把它传给 LeRobot——校准阶段传不传都
一样（`side` 不影响校准），但**交付文档必须写明遥操作时要带 `--teleop.side=left|right`**，
否则客户拿到的臂方向是反的。

### B4 · 其他已核对但不打算动的小点

- `lerobot-find-joint-limits` 官方存在，README 的流程里没用，本工作站也没有。
- `OpenArmMiniConfigBase.use_degrees` 是**死配置**：驱动里把 `norm_mode` 硬编码成
  `MotorNormMode.DEGREES`，从不读 `use_degrees`。上游的事，不影响我们。
- 官方 `_find_single_motor_p0` 取第一个应答就返回，**不校验总线上只有一颗**；
  见 A1，改用广播 ping 后我们可以比官方更严。
