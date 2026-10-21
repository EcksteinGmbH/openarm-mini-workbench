"""出厂测试判据表与纯判定函数。

所有阈值集中在这里，每条带依据类型，报告原样打印。依据类型：
- official：官方硬件 README / LeRobot 源码
- spec：Feetech 规格书
- derived：由前两者推出
- tbc：待定标——先记录，首批实测后定数；定标前不参与 PASS/FAIL

判定函数是纯函数（不碰串口、不碰文案），好用现场数值钉住。
方案见 .tasks/testbench/factory-test-flow/docs/test-plan.md。
"""

from __future__ import annotations

from typing import Any

CRITERIA_VERSION = "2026-10-21.3"

ENCODER_RESOLUTION = 4096

# 测试站测装配完成的整臂，电源按官方 BOM 一律 7.5V。
# 阶段：S1 准备 → S2 装配后逐颗写 ID → S3 整臂电气与通信 → S4 关节身份 → S5 官方校准
# → S6 官方驱动读数 → S7 放行归档；S8 follower 配对、S9 增强复测为可选。
# ID 放到装配之后写：电机已经装在哪个关节上，只接这一颗、写这个关节的 ID、再动这个关节确认，
# 序号不会写错。

# ---------- 供电 ----------
SUPPLY_VOLTAGE_TOLERANCE_V = 1.0

# ---------- S2 装配后写 ID：动关节确认 ----------
FEEDBACK_MOVEMENT_COUNTS = 100
# 建议值，待定标：装好的关节至少摆 30°（J6 腕部俯仰行程较小，所以不取 90°）。
FEEDBACK_SPAN_SUGGESTED_COUNTS = 341

# ---------- S3 整臂 ----------
IDLE_TEMPERATURE_MAX_C = 40
VOLTAGE_SPREAD_SUGGESTED_V = 0.3
COMM_STABILITY_SECONDS = 60.0

# ---------- S4 关节身份 ----------
IDENTITY_MIN_SPAN_COUNTS = 100
IDENTITY_DOMINANCE_RATIO = 3.0

# ---------- S6 官方驱动读数 ----------
ZERO_POSE_TOLERANCE_DEG = 15.0
GRIPPER_CLOSED_MIN_DEG = -10.0
GRIPPER_OPEN_MAX_DEG = -50.0
READOUT_SWEEP_MIN_DEG = 10.0

# 判据表。title 是 messages.py 里的文案键（crit_<id 去点>），报告与页面共用。
CRITERIA: tuple[dict[str, Any], ...] = (
    {"id": "S1.checklist", "stage": "S1", "judged": True, "basis": "official", "limit": "all"},
    {"id": "S2.single_on_bus", "stage": "S2", "judged": True, "basis": "official", "limit": 1},
    {"id": "S2.voltage", "stage": "S2", "judged": True, "basis": "derived", "limit": SUPPLY_VOLTAGE_TOLERANCE_V, "unit": "V"},
    {"id": "S2.persisted", "stage": "S2", "judged": True, "basis": "derived", "limit": "rescan"},
    {"id": "S2.joint_confirmed", "stage": "S2", "judged": True, "basis": "derived", "limit": FEEDBACK_MOVEMENT_COUNTS, "unit": "counts"},
    {"id": "S2.joint_span", "stage": "S2", "judged": False, "basis": "tbc", "limit": FEEDBACK_SPAN_SUGGESTED_COUNTS, "unit": "counts"},
    {"id": "S3.present", "stage": "S3", "judged": True, "basis": "official", "limit": 8},
    {"id": "S3.firmware_same", "stage": "S3", "judged": True, "basis": "official", "limit": "same"},
    {"id": "S3.voltage", "stage": "S3", "judged": True, "basis": "derived", "limit": SUPPLY_VOLTAGE_TOLERANCE_V, "unit": "V"},
    {"id": "S3.temperature", "stage": "S3", "judged": True, "basis": "derived", "limit": IDLE_TEMPERATURE_MAX_C, "unit": "°C"},
    {"id": "S3.status", "stage": "S3", "judged": True, "basis": "derived", "limit": 0},
    {"id": "S3.torque_off", "stage": "S3", "judged": True, "basis": "derived", "limit": 0},
    {"id": "S3.voltage_spread", "stage": "S3", "judged": False, "basis": "tbc", "limit": VOLTAGE_SPREAD_SUGGESTED_V, "unit": "V"},
    {"id": "S3.protection_limits", "stage": "S3", "judged": False, "basis": "tbc", "limit": "record"},
    {"id": "S3.comm", "stage": "S3", "judged": True, "basis": "derived", "limit": COMM_STABILITY_SECONDS, "unit": "s"},
    {"id": "S4.identity", "stage": "S4", "judged": True, "basis": "derived", "limit": IDENTITY_DOMINANCE_RATIO},
    {"id": "S4.span", "stage": "S4", "judged": True, "basis": "derived", "limit": IDENTITY_MIN_SPAN_COUNTS, "unit": "counts"},
    {"id": "S5.precheck", "stage": "S5", "judged": True, "basis": "official", "limit": 2047},
    {"id": "S5.saved", "stage": "S5", "judged": True, "basis": "official", "limit": "saved"},
    {"id": "S5.consistent", "stage": "S5", "judged": True, "basis": "official", "limit": 8},
    {"id": "S5.consistent_power_cycled", "stage": "S5", "judged": True, "basis": "derived", "limit": 8},
    {"id": "S5.gripper_range", "stage": "S5", "judged": False, "basis": "tbc", "limit": "record", "unit": "counts"},
    {"id": "S6.calibrated", "stage": "S6", "judged": True, "basis": "official", "limit": "is_calibrated"},
    {"id": "S6.zero_pose", "stage": "S6", "judged": True, "basis": "derived", "limit": ZERO_POSE_TOLERANCE_DEG, "unit": "°"},
    {"id": "S6.gripper_closed", "stage": "S6", "judged": True, "basis": "official", "limit": GRIPPER_CLOSED_MIN_DEG, "unit": "°"},
    {"id": "S6.gripper_open", "stage": "S6", "judged": True, "basis": "official", "limit": GRIPPER_OPEN_MAX_DEG, "unit": "°"},
    {"id": "S6.remap", "stage": "S6", "judged": True, "basis": "official", "limit": "joint_6<->joint_7"},
    {"id": "S6.direction", "stage": "S6", "judged": False, "basis": "tbc", "limit": "record"},
)

CRITERIA_BY_ID = {c["id"]: c for c in CRITERIA}


def criterion_key(criterion_id: str) -> str:
    return "crit_" + criterion_id.replace(".", "_")


def check(criterion_id: str, ok: bool, value: Any = None, **extra: Any) -> dict[str, Any]:
    """一条判定结果。记录项（judged=False）的 ok 只作提示，不进放行门。"""

    criterion = CRITERIA_BY_ID[criterion_id]
    return {
        "id": criterion_id,
        "ok": bool(ok),
        "judged": criterion["judged"],
        "basis": criterion["basis"],
        "limit": criterion["limit"],
        "unit": criterion.get("unit", ""),
        "value": value,
        **extra,
    }


def judged_ok(checks: list[dict[str, Any]]) -> bool:
    return all(c["ok"] for c in checks if c["judged"])


# ---------- 编码器 ----------


def unwrap_positions(samples: list[int]) -> list[int]:
    """把模 4096 的位置流接回连续序列，跨接缝的摆动不会被看成整圈。"""

    if not samples:
        return []
    out = [samples[0]]
    for prev, cur in zip(samples, samples[1:]):
        delta = cur - prev
        if delta > ENCODER_RESOLUTION // 2:
            delta -= ENCODER_RESOLUTION
        elif delta < -(ENCODER_RESOLUTION // 2):
            delta += ENCODER_RESOLUTION
        out.append(out[-1] + delta)
    return out


def unwrapped_span(samples: list[int]) -> int:
    unwrapped = unwrap_positions(samples)
    return (max(unwrapped) - min(unwrapped)) if unwrapped else 0


def max_step(samples: list[int]) -> int:
    """相邻两次采样间的最大位移（已展开）。只记录：手摆速度差异大，定标前不判。"""

    unwrapped = unwrap_positions(samples)
    return max((abs(b - a) for a, b in zip(unwrapped, unwrapped[1:])), default=0)


# ---------- S3 整臂 ----------


def evaluate_arm_scan(
    snapshots: list[dict[str, Any]], expected_voltage_v: float | None
) -> dict[str, Any]:
    """八轴只读扫描的判定。snapshots 每项至少有 ok/motor_name，读成功的带寄存器值。

    expected_voltage_v 为 None 表示没选档位：电压无从比对，该项判失败而不是跳过——
    放行门不能因为少填一个下拉框就少判一项。
    """

    readable = [s for s in snapshots if s.get("ok")]
    checks: list[dict[str, Any]] = [
        check("S3.present", len(readable) == len(snapshots) and len(snapshots) == 8, len(readable))
    ]
    firmware = sorted({s.get("firmware", "") for s in readable})
    checks.append(check("S3.firmware_same", len(firmware) == 1 and firmware[0] != "", firmware))

    per_motor: dict[str, list[dict[str, Any]]] = {}
    for snap in readable:
        name = snap["motor_name"]
        voltage = float(snap.get("voltage_v", 0.0))
        motor_checks = [
            check(
                "S3.voltage",
                expected_voltage_v is not None
                and abs(voltage - expected_voltage_v) <= SUPPLY_VOLTAGE_TOLERANCE_V,
                voltage,
                expected=expected_voltage_v,
            ),
            check(
                "S3.temperature",
                int(snap.get("temperature_c", 999)) <= IDLE_TEMPERATURE_MAX_C,
                snap.get("temperature_c"),
            ),
            check("S3.status", int(snap.get("status_raw", -1)) == 0, snap.get("status_raw")),
            check("S3.torque_off", int(snap.get("torque_enable", -1)) == 0, snap.get("torque_enable")),
        ]
        per_motor[name] = motor_checks

    # 过压保护限值只记录：BOM 给 7.5V 电源，规格书过压阈值是 7.4V，C046 的实际默认值要读真机。
    # 若限值低于实测供电，电机会置状态告警位，S3.status 会判失败。
    limits = sorted({float(s["max_voltage_limit_v"]) for s in readable if "max_voltage_limit_v" in s})
    checks.append(
        check(
            "S3.protection_limits",
            bool(limits) and expected_voltage_v is not None and min(limits) >= expected_voltage_v,
            {"max_voltage_limit_v": limits,
             "max_temperature_limit_c": sorted({s["max_temperature_limit_c"] for s in readable
                                                if "max_temperature_limit_c" in s})},
        )
    )
    voltages = [float(s.get("voltage_v", 0.0)) for s in readable]
    spread = round(max(voltages) - min(voltages), 2) if voltages else None
    checks.append(
        check(
            "S3.voltage_spread",
            spread is not None and spread <= VOLTAGE_SPREAD_SUGGESTED_V,
            spread,
        )
    )
    all_checks = checks + [c for motor in per_motor.values() for c in motor]
    return {
        "checks": checks,
        "per_motor": per_motor,
        "judged_ok": judged_ok(all_checks),
        "firmware_versions": firmware,
        "voltage_spread_v": spread,
    }


def evaluate_comm_stability(rounds: int, failures: int, duration_sec: float) -> dict[str, Any]:
    ok = rounds > 0 and failures == 0 and duration_sec >= COMM_STABILITY_SECONDS - 0.5
    return {
        "checks": [check("S3.comm", ok, {"rounds": rounds, "failures": failures, "seconds": round(duration_sec, 1)})],
        "judged_ok": ok,
    }


# ---------- S4 关节身份 ----------


def evaluate_joint_identity(target: str, spans: dict[str, int]) -> dict[str, Any]:
    """只动一个关节时，跨度最大的必须就是它，并且明显大于其余关节。

    抓的是装错位或接错线的电机：ID 写对了，装进了别的关节。
    J6/J7 的软件对调由驱动处理，物理上仍必须 ID6=J6、ID7=J7。
    """

    target_span = int(spans.get(target, 0))
    others = {name: int(span) for name, span in spans.items() if name != target}
    runner_up_name, runner_up = max(others.items(), key=lambda item: item[1]) if others else ("", 0)
    dominant_name = max(spans, key=lambda name: spans[name]) if spans else ""
    ratio = (target_span / runner_up) if runner_up > 0 else float("inf")
    identity_ok = dominant_name == target and ratio >= IDENTITY_DOMINANCE_RATIO
    span_ok = target_span >= IDENTITY_MIN_SPAN_COUNTS
    checks = [
        check(
            "S4.identity",
            identity_ok,
            round(ratio, 2) if ratio != float("inf") else "inf",
            dominant=dominant_name,
            runner_up=runner_up_name,
        ),
        check("S4.span", span_ok, target_span),
    ]
    return {
        "checks": checks,
        "judged_ok": judged_ok(checks),
        "target_span": target_span,
        "dominant": dominant_name,
        "runner_up": runner_up_name,
        "runner_up_span": runner_up,
    }


# ---------- S6 官方驱动读数 ----------

# openarm_mini.get_action() 把 leader 的 joint_6 读数放进 follower 的 joint_7.pos，反之亦然。
JOINT_REMAP = {"joint_6": "joint_7", "joint_7": "joint_6"}


def action_key(motor: str) -> str:
    return JOINT_REMAP.get(motor, motor) + ".pos"


def evaluate_readout(mode: str, readout: dict[str, Any], motor: str = "") -> dict[str, Any]:
    """官方驱动读数的判定。readout 由 scripts/openarm_mini_readout.py 产出。

    mode:
    - zero：整臂下垂、夹爪闭合。J1–J7 读数接近 0°，夹爪接近 0°。
    - gripper_open：夹爪完全张开，读数应接近 −65°。
    - sweep：只动 motor，跨度最大的 action 键必须是驱动映射后的那一个。
    """

    mean = readout.get("mean", {})
    span = readout.get("span", {})
    checks = [check("S6.calibrated", bool(readout.get("is_calibrated")), readout.get("is_calibrated"))]

    if mode == "zero":
        joints = {k: v for k, v in mean.items() if k != "gripper.pos"}
        worst_key = max(joints, key=lambda k: abs(joints[k])) if joints else ""
        worst = abs(joints[worst_key]) if worst_key else None
        checks.append(
            check(
                "S6.zero_pose",
                len(joints) == 7 and worst is not None and worst <= ZERO_POSE_TOLERANCE_DEG,
                round(worst, 2) if worst is not None else None,
                worst_key=worst_key,
            )
        )
        gripper = mean.get("gripper.pos")
        checks.append(
            check(
                "S6.gripper_closed",
                gripper is not None and gripper >= GRIPPER_CLOSED_MIN_DEG,
                None if gripper is None else round(gripper, 2),
            )
        )
    elif mode == "gripper_open":
        gripper = mean.get("gripper.pos")
        checks.append(
            check(
                "S6.gripper_open",
                gripper is not None and gripper <= GRIPPER_OPEN_MAX_DEG,
                None if gripper is None else round(gripper, 2),
            )
        )
    elif mode == "sweep":
        expected = action_key(motor)
        dominant = max(span, key=lambda k: span[k]) if span else ""
        moved = float(span.get(expected, 0.0))
        checks.append(
            check(
                "S6.remap",
                dominant == expected and moved >= READOUT_SWEEP_MIN_DEG,
                round(moved, 2),
                expected_key=expected,
                dominant_key=dominant,
            )
        )
        first = readout.get("first", {}).get(expected)
        last = readout.get("last", {}).get(expected)
        direction = None
        if first is not None and last is not None and last != first:
            direction = "+" if last > first else "-"
        checks.append(check("S6.direction", direction is not None, direction, key=expected))
    else:
        raise ValueError(mode)

    return {"checks": checks, "judged_ok": judged_ok(checks)}


def teleoperate_command(port: str, robot_id: str, side: str) -> str:
    """交付给客户的遥操作命令。官方 README 的命令缺 --robot.* 和 --teleop.side，照抄跑不起来。"""

    return (
        "lerobot-teleoperate \\\n"
        "    --robot.type=openarm_follower --robot.port=<can0> "
        f"--robot.side={side} --robot.id=<follower_id> \\\n"
        f"    --teleop.type=openarm_mini --teleop.port={port} \\\n"
        f"    --teleop.side={side} --teleop.id={robot_id}"
    )
