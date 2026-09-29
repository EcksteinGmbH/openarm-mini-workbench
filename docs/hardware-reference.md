# OpenArm Mini 硬件资料

来源：[pkooij/open-arms-mini](https://github.com/pkooij/open-arms-mini)（硬件设计 Apache 2.0，
基于 SO-ARM100）。本文是台架要用的部分，数值全部照抄官方 `README.md` 与 `BOM.md`，
凡是本仓库自己加的判断都标了「本工作站」。

## 是什么

7 DOF + 夹爪的 3D 打印遥操作 **leader 臂**：3 个肩关节、1 个肘、1 个前臂旋转、2 个腕关节，
再加一个扳机式夹爪。设计目标是低惯量、与操作者身高无关（腕部握持）、便宜。
配对的 follower 是 Open Arms 系列；软件侧作为 LeRobot 的 `openarm_mini` 遥操作器接入。

腕带（约 25 mm 弹性魔术贴）不是可选装饰：官方明确说没有它手会打滑，腕部旋转精度明显变差。

## BOM（单臂 / 一对）

| 项 | 单臂 | 一对 | 单价 | 备注 |
|---|---|---|---|---|
| Feetech STS3215-C046 舵机（7.4V，1:147） | 8 | 16 | ~15 EUR | 与 SO-ARM101 同款电机 |
| Waveshare 串行总线舵机驱动板 | 1 | 2 | ~10 EUR | Bus Servo Adapter (A) |
| 7.5V 直流电源（≥2A） | 1 | 2 | ~12 EUR | |
| USB-A 转 USB-C 线 | 1 | 2 | ~3 EUR | |
| 弹性魔术贴腕带（~25 mm） | 1 | 2 | ~5 EUR | |
| M2×6 螺丝 | ~35 | ~70 | | 电机固定 |
| M3×6 螺丝 | ~35 | ~70 | | 结构连接 |
| M3×6 舵盘螺丝 | 8 | 16 | | 每颗电机一个，通常随电机附带 |
| 三芯舵机线（150–200 mm） | 8 | 16 | | 菊花链 |
| PLA / PETG 耗材 | ~150–200 g | ~300–400 g | ~5 EUR | |

合计约 **157 EUR / 单臂**，**314 EUR / 一对**。

## 3D 打印

| 参数 | 推荐值 |
|---|---|
| 材料 | PLA 或 PETG |
| 层高 | 0.2 mm |
| 填充 | 20–40% |
| 支撑 | 需要处加 |
| 喷嘴 | 0.4 mm |

一对共 **32 件**（单臂 16 件）。通用件各 2，夹爪 L/R 各 1，Waveshare 底板整对共用 1。
`arducam_holder` 是可选相机支架，不计入。

## 关节 / 电机 ID 表

官方 README「Motor IDs」一节，ID 与 J 编号一一对应：

| ID | 关节 | 件号 | 本工作站显示 | LeRobot 电机键名 |
|---|---|---|---|---|
| 1 | Shoulder Pan | J1 | 肩部旋转 | `joint_1` |
| 2 | Shoulder Lift | J2 | 肩部抬升 | `joint_2` |
| 3 | Shoulder Roll | J3 | 肩部翻滚 | `joint_3` |
| 4 | Elbow Flex | J4 | 肘部弯曲 | `joint_4` |
| 5 | Forearm Rotation | J5 | 前臂旋转 | `joint_5` |
| 6 | Wrist Flex | J6 | 腕部俯仰 | `joint_6` |
| 7 | Wrist Roll | J7 | 腕部旋转 | `joint_7` |
| 8 | Gripper | J8 L/R | 夹爪 | `gripper` |

> **关节交换**：leader 的 wrist flex(6) 与 wrist roll(7) 在软件里相对 follower 是故意对调的，
> 因为这样更贴合人手腕的动作方式。对调由 `openarm_mini` 驱动自动处理，
> **不是接线或写 ID 时要做的事**——台架仍然严格按上表把 ID 6 写给 J6、ID 7 写给 J7。

写 ID 的顺序按官方 `setup_motors()`：从夹爪倒着走到肩部，即 **8 → 7 → … → 1**。
装配前先配好 ID 比装好再配容易得多。

## 装配顺序（官方 10 步）

1. **肩部旋转 J1** —— 装入电机 1，4× M2×6 固定；J1_holder 用 2× M2×6；装舵盘，顶部舵盘用 M3×6 锁紧。
2. **肩部抬升 J2** —— 滑入电机 2，4× M2×6；装舵盘；J2 与 J1 两侧各 4× M3×6 连接。
3. **肩部翻滚 J3** —— 装入电机 3，4× M2×6；装舵盘；J3 与 J2 两侧各 4× M3×6。
4. **肘 J4** —— J4_holder 套到 J3 上；装入电机 4，4× M2×6；装舵盘。
5. **前臂旋转 J5** —— 装入电机 5，2× M2×6；装一个舵盘；J5 与电机 4 两侧各 4× M3×6。
6. **腕部俯仰 J6** —— J6 用 4× M3×6 接到电机 5 舵盘；装入电机 6，2× M2×6；装舵盘。
7. **腕部旋转 J7** —— J7 经 J7_holder 接到电机 6；装入电机 7，4× M2×6。
8. **夹爪** —— 电机 8 装进 J8 holder；J8 L/R 爪片两侧各 4× M3×6；装扳机。
9. **手柄与腕带** —— 装 J Handle；腕部装「J6 holder with strap」；穿好魔术贴并调到贴合。
10. **驱动板** —— Waveshare 板装到底板上；按 1→8 接成菊花链。

## LeRobot 官方命令

```bash
pip install 'lerobot[feetech]'

lerobot-find-port

lerobot-setup-motors \
    --teleop.type=openarm_mini \
    --teleop.port=/dev/ttyACM0

lerobot-calibrate \
    --teleop.type=openarm_mini \
    --teleop.port=/dev/ttyACM0 \
    --teleop.id=my_mini_leader_arm

lerobot-teleoperate \
    --teleop.type=openarm_mini \
    --teleop.port=/dev/ttyACM0 \
    --teleop.id=my_mini_leader_arm
```

本工作站替代 `lerobot-setup-motors` 做写 ID（多了断电复扫和只读质检这两道门），
校准则是直接驱动 `lerobot-calibrate` 本身，不另做实现。
`openarm_mini` 驱动还有一个 `side` 配置（`left` / `right`），只影响读数方向翻转，
不写进电机、也不影响校准，官方 README 的命令里没带它。

## 与 SO-ARM101 的关系

电机、驱动板、波特率、控制表完全相同，所以台架的电气规程通用。
但**校准流程不同**，不能照搬 SO-101 的做法，细节见 [lerobot-openarm-mini.md](lerobot-openarm-mini.md)。
