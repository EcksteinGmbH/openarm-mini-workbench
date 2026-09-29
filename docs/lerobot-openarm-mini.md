# LeRobot `openarm_mini` 驱动事实记录

核对日期：2026-09-28，对照 huggingface/lerobot `main` 分支
`src/lerobot/teleoperators/openarm_mini/`。

这份文件存在的理由：**OpenArm Mini 的校准流程和 SO-101 不一样**。
把 SO-101 工作站的做法照搬过来，会在现场问出根本不存在的确认、
拦下完全正常的关节，并且漏掉真正该核对的字段。

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

本工作站在写之前多做一步解锁（`Lock`=0，地址 55），并在写完后
强制**断电 5 秒复扫**——官方程序不做这两件事，但 ID 和波特率在 EEPROM 里，
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
