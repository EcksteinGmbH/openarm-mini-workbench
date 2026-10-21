# LeRobot `openarm_mini` 驱动事实记录

核对日期：2026-09-28，对照 huggingface/lerobot `main` 分支
`src/lerobot/teleoperators/openarm_mini/`。

这份文件存在的理由：**OpenArm Mini 的校准流程和 SO-101 不一样**。
把 SO-101 工作站的做法照搬过来，会在现场问出根本不存在的确认、
拦下完全正常的关节，并且漏掉真正该核对的字段。

## 校准文件位置

`Teleoperator.__init__`：

```python
self.calibration_dir = config.calibration_dir or (HF_LEROBOT_CALIBRATION / TELEOPERATORS / self.name)
self.calibration_fpath = self.calibration_dir / f"{self.id}.json"
```

`self.name` = `"openarm_mini"`，所以默认是
`<校准根>/teleoperators/openarm_mini/<编号>.json`。

**校准根不是写死的**（`utils/constants.py`），优先级：

1. `HF_LEROBOT_CALIBRATION`
2. `HF_LEROBOT_HOME/calibration`
3. `HF_HOME/lerobot/calibration`
4. `$XDG_CACHE_HOME`（默认 `~/.cache`）`/huggingface/lerobot/calibration`

文件内容是 `draccus.dump` 出的 `dict[电机名, MotorCalibration]`，
字段为 `id` / `drive_mode` / `homing_offset` / `range_min` / `range_max`。

其中 **`drive_mode` 不写进任何寄存器**——`write_calibration()` 只写
`Homing_Offset`、`Min_Position_Limit`、`Max_Position_Limit` 三个。
所以它无法与电机比对，只存在于文件里；官方自己的 `is_calibrated` 也只比这三项，
`read_calibration()` 甚至恒返回 `drive_mode=0`。本工作站的一致性核对同样只比这三项。

## 电机键名与 ID

```python
motors = {
    "joint_1": Motor(1, "sts3215", MotorNormMode.DEGREES),
    ...
    "joint_7": Motor(7, "sts3215", MotorNormMode.DEGREES),
    "gripper": Motor(8, "sts3215", MotorNormMode.RANGE_0_100),
}
```

校准文件用的就是这些键。工作站页面按仓库的 J1–J8 显示，代码里必须用这套键名，
否则一致性核对会全部落空。

## 校准流程（`OpenArmMini.calibrate()`）

按发生顺序：

1. 若已存在同 id 的校准文件 → 多问一句
   `Press ENTER to use existing calibration for <id>, or type 'c' and press ENTER to run new calibration:`
2. `disable_torque()`
3. **给全部 8 颗电机写 `Phase = 12`**
4. 全部电机 `Operating_Mode = POSITION(0)`
5. 一次确认：**零位姿态 —— 整臂自然下垂、夹爪闭合**，`Press ENTER when ready...`
6. `set_half_turn_homings()` → 每颗写 `homing = 当前位置 − 2047`
7. 夹爪两次确认：先**完全闭合**（`Press ENTER when gripper is closed...`），
   再**完全张开**（`Press ENTER when gripper is fully open...`）
8. 写量程：
   - `joint_1..joint_7`：`range_min = 0`，`range_max = 4095`，`drive_mode = 0` —— **驱动写死的整圈**
   - `gripper`：按实测的闭合/张开位置取小/大值；闭合值小于张开值时 `drive_mode = 0`，否则 `1`
9. 保存，打印 `Calibration complete and saved to <路径>`

### 与 SO-101 的三处关键差异

| | SO-101 | OpenArm Mini |
|---|---|---|
| 确认次数 | 2 次（置中、扫完整行程） | 1 次零位 + 2 次夹爪 |
| 关节量程 | 由操作员手动扫出来 | 驱动写死 `0..4095` |
| 保存标记 | `Calibration saved` | `Calibration complete and saved to` |

**直接后果**：SO-101 工作站那套「行程试扫 + 停放窗口」在这里没有意义。
那套逻辑是为了保证整段行程落在停放位 ±2047 内；Mini 的关节量程是整圈常量，
不存在这个约束。本工作站因此不做行程试扫，也不按停放窗口拦人。

唯一还成立的拦截是**多圈累计读数**：`homing` 存在 11 位符号-幅值寄存器里，装不下
超过 ±2047 的值，位置读数跑出单圈时官方程序会直接报
`Magnitude ... exceeds`。处置是断电 5 秒重新上电。

### 预检的折算必须取模

```
actual = (Present_Position + Homing_Offset) mod 4096
predicted_homing = actual − 2047
```

**`mod 4096` 不能省。** 编码器是模 4096 的：STS3215 的 `Present_Position` 用 bit 15
符号-幅值编码，靠近编码器接缝时会直接报出负数；再扣掉一个已有的中点偏移，
结果落到 0..4095 之外是完全正常的姿态，不是多圈累计。

这一点是现场撞出来的。2026-09-29 首次真机预检把一个**摆在零位**的关节拦停了，
报「折算编码器读数 -1497 超出单圈 0..4095，属多圈累计读数」。当时的实现算的是
`present + homing` 而没取模。同一条臂修好后 8/8 通过，J3 实测 `present = -1478`、
`homing = 0`，折算后是 2618 —— 负的 present 只是停在接缝附近，机械位置毫无问题。
漏取模会拦下每一条已经校准过的臂。

两条拦截各自对应官方真会中止的情形：

| 判据 | 官方对应 | 处置 |
|---|---|---|
| `Present_Position > 4095` | 多圈累计，`set_half_turn_homings()` 算出的偏移装不进寄存器 | 断电 5 秒重新上电 |
| `\|actual − 2047\| > 2047` | `encoding_utils` 报 `Magnitude ... exceeds` | 同上 |

第二条**是可达的**，不是纯防御性检查：取模之后只有 `actual == 4095` 这一个值会触发
（偏移 2048）。`tests/test_workstation.py` 里对整圈 4096 个位置穷举，确认被拦下的
只有 4095 这一个。

## 校准到底校准什么、往电机里写了什么

核对对象：本机 `.venv-lerobot`（lerobot 0.6.2 @ `eb7a54c`，与 PyPI 0.6.1 行为一致），2026-10-21。

### 校准的是什么

只有两件事是「测」出来的：

1. **零位**：整臂自然下垂、夹爪闭合时，读 8 颗电机的当前位置，算出各自的 `Homing_Offset`，
   让这个姿态以后读出来正好是 2047（半圈，中点）。驱动把 2047 换算成 0°，所以零位就是
   leader 与 follower 对齐的参考姿态。
2. **夹爪行程**：分别读夹爪完全闭合、完全张开时的位置，作为夹爪的量程。驱动据此把夹爪换算成
   0–100，再乘 −0.65 变成 follower 的 0° 到 −65°。

J1–J7 的量程**不测**，驱动直接写整圈 0..4095。

**不属于校准、也不写进电机的**：左右侧方向翻转（运行时由 `--teleop.side` 决定）、J6/J7 对调、
夹爪 −0.65 系数——都在驱动代码里，每次遥操作时现算。

### `lerobot-calibrate` 对每颗电机的全部写入（按执行顺序）

`scripts/lerobot_calibrate.py:104-109`：`connect(calibrate=False)` → `calibrate()` → `disconnect()`。

| 顺序 | 时机 | 写什么（地址） | 值 | 断电后 | 出处 |
|---|---|---|---|---|---|
| 1 | 连接时 `configure()` | `Torque_Enable`(40)、`Lock`(55) | 0、0（关扭矩、解锁 EEPROM） | 不保持 | `feetech.py:291-294` |
| 2 | 连接时 | `Return_Delay_Time`(7) | 0（出厂 250） | 保持 | `feetech.py:213` |
| 3 | 连接时 | `Maximum_Acceleration`(85) | 254（实测出厂 250） | 保持 | `feetech.py:216` |
| 4 | 连接时 | `Acceleration`(41) | 254 | **不保持**（断电读到 0） | `feetech.py:217` |
| 5 | 连接时 | `Phase`(18) | 若 bit4 置位则清掉（出厂实测 92 → 76） | 保持 | `feetech.py:222-225` |
| 6 | 连接时 | `Operating_Mode`(33) | 0（位置模式） | 保持 | `openarm_mini.py:200-204` |
| 7 | 校准开始 | `Torque_Enable`、`Lock` | 0、0 | 不保持 | `openarm_mini.py:130` |
| 8 | 校准开始 | `Phase`(18) | **12** | 保持 | `openarm_mini.py:132-134` |
| 9 | 校准开始 | `Operating_Mode`(33) | 0 | 保持 | `openarm_mini.py:136-137` |
| 10 | 零位确认后，先复位 | `Homing_Offset`(31) / `Min_Position_Limit`(9) / `Max_Position_Limit`(11) | 0 / 0 / 4095 | 保持 | `motors_bus.py:754-773` |
| 11 | 零位确认后 | `Homing_Offset`(31) | **零位读数 − 2047** | 保持 | `motors_bus.py:775-798` |
| 12 | 夹爪两次确认后 | 每颗 `Homing_Offset` / `Min_Position_Limit` / `Max_Position_Limit` | J1–J7：偏移 / 0 / 4095；夹爪：偏移 / 闭合与张开读数中的小值 / 大值 | 保持 | `feetech.py:268-276` |
| 13 | 结束 `disconnect()` | `Torque_Enable`、`Lock` | 0、0 | 不保持 | `motors_bus.py:547-559` `disconnect(disable_torque=True)` |

「保持」= 校准写在 EEPROM 区，断电后不丢；工作站 S5 的「断电后再核对」就是验证这一点。

**不写**：ID、波特率（那是 S2 写 ID 的事）；扭矩一直关着，不下发目标位置。

### 写到电脑上的校准文件

`<校准根>/teleoperators/openarm_mini/<编号>.json`，每颗电机一条：
`id`、`drive_mode`、`homing_offset`、`range_min`、`range_max`。

- `homing_offset` / `range_min` / `range_max` 三项与电机 EEPROM 一一对应，工作站一致性核对就比这三项。
- `drive_mode` **只在文件里**，不写进电机：J1–J7 为 0；夹爪闭合读数小于张开读数时为 0，否则为 1。
- 遥操作时驱动读这份文件做换算，并检查它和电机里的三项是否一致（`is_calibrated`）。
  所以**文件和电机必须配对交付**：换电脑要连同文件一起拷，重新校准会同时改两边。

### 已有校准文件时

开头会多问一句（沿用 / 重新校准）。沿用（裸回车）= 把文件里的三项写回电机就结束，第 7–12 步都不做，
什么也没测。工作站在这里固定回答 `c`（重新校准），见「沿用旧校准文件的陷阱」。

## `Phase` 寄存器

- 地址 18，1 字节（`motors/feetech/tables.py`）
- `configure_motors()` 只要求清掉 bit4（`0x10`，角度反馈模式），
  否则位置读数会溢出或出现负值——官方注释说这只在 STS3215 上必须做
- `openarm_mini.calibrate()` 更进一步，给全部电机写 `Phase = 12`

`12 & 0x10 == 0`，两者不冲突。**12 是校准后的期望值**，工作站的一致性核对按它判。

## 每次连接都会重写的运行期参数

`configure_motors(return_delay_time=0, maximum_acceleration=254, acceleration=254)`：

| 字段 | 地址 | 期望 | 持久性 |
|---|---|---|---|
| `Return_Delay_Time` | 7 | 0 | EEPROM |
| `Maximum_Acceleration` | 85 | 254 | EEPROM |
| `Acceleration` | 41 | 254 | **SRAM，断电归零** |
| `Operating_Mode` | 33 | 0 | EEPROM |

`Acceleration` 断电后读到 0 是正常的，LeRobot 下次 `connect()` 会重写。
拿它判不合格会让每一条断过电的臂都挂掉，所以工作站把它单列成「运行期字段待重写」，
只提示不判负。

## 左右臂差异（`side`）

```python
SIDE_MOTORS_TO_FLIP = {
    "left":  ["joint_1", "joint_3", "joint_4", "joint_5", "joint_6", "joint_7"],
    "right": ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_7"],
}
JOINT_REMAP = {"joint_6": "joint_7", "joint_7": "joint_6"}
GRIPPER_TELEOP_TO_DEGREES = -0.65
```

这三项都只作用在 `get_action()` 的读数换算上，**不写进电机、不进校准文件**。
所以台架写 ID 和校准时左右臂没有任何区别；工作站记录左右臂，是为了编号可追溯
和夹爪件号（J8 L/R）对得上，不是因为电机设置不同。

## 写 ID（`MotorsBus.setup_motor()`）

顺序：切到电机当前波特率 → 关扭矩 → 写 `ID`(地址 5) → 写 `Baud_Rate`(地址 6) = 1,000,000。
`setup_motors()` 用 `reversed(self.bus.motors)` 遍历，即 **夹爪 → joint_7 → … → joint_1**。

`setup_motor()` 里的 `_disable_torque()` **同时写 `Torque_Enable=0` 和 `Lock=0`**
（`feetech.py`），所以解锁 EEPROM 是官方行为，不是本工作站的额外动作——
本文档早先写成「官方不解锁」是错的，2026-09-29 核对上游源码时改正。

本工作站真正多做的只有一件：写完后强制**断电 5 秒复扫**。ID 和波特率在 EEPROM 里，
不断电复扫就无法区分「写进去了」和「只在本次上电周期生效」。

## 失败特征串

逐条引自上游源码；升级改了措辞时 `tests/test_workstation.py` 会先红。

| 现象 | 特征串（出处） | 处置 |
|---|---|---|
| 中点偏移超 ±2047 | `Magnitude ... exceeds`（`encoding_utils.py:23`） | 断电 5 秒重上电 |
| 串口打不开 | `Could not connect on port`（`motors_bus.py:538`） | 确认无程序占用串口 |
| 电机与预期不符 | `Full expected motor list`（`motors_bus.py:497`） | 只读扫描确认 ID 1–8 齐全 |
| 沿用了旧校准 | `Using existing calibration for`（`openarm_mini.py`） | 重来，在沿用提示处选覆盖 |
| 这套 LeRobot 没有该驱动 | `invalid choice: 'openarm_mini'` | 升级 LeRobot 或换虚拟环境 |

最后一条是实测出来的：本机 `~/Projects/.venvs/so-arm101-lerobot-0.4.4` 里的
LeRobot 0.4.4 **没有** `openarm_mini`，`--teleop.type` 的可选值里根本没有它，
启动后会被 argparse 以退出码 2 顶回来。工作站因此在启动前探测一次驱动是否存在，
不支持就直接拦下，不放注定失败的子进程出去。

## 沿用旧校准文件的陷阱

在第 1 步的提示处敲**裸回车**表示「沿用旧文件」：官方程序把上一次的参数写回电机就返回，
退出码 0，不打印保存标记，**什么都没测**。随后的一致性核对拿电机和同一个旧文件比，
会报 8/8 通过，等于给一台没校准的臂出了合格结论。

每一次复测、返修重校都会碰到这个提示。工作站因此把它识别成独立阶段，
确认按钮变成「重新校准（覆盖旧文件）」并回答字面量 `c`；
退出码 0 但没有保存标记时判为 `finished_unsaved`，**不串联一致性核对**。
