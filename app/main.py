"""OpenArm Mini 测试工作站。

单进程、无框架：Feetech 硬件适配 + 领域操作 + HTTP API + 内嵌页面。

关节与 ID 取自官方仓库 pkooij/open-arms-mini 的 README 电机表；电机键名
(joint_1..joint_7, gripper) 取自 LeRobot 上游 openarm_mini 驱动，两者必须一致，
否则校准文件核对会全部落空。页面按仓库的 J1–J8 展示，代码按 LeRobot 键名存取。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import date, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from serial.tools import list_ports

from messages import LANGUAGES, field_name, get_language, motor_label, set_language
from messages import m as _m

# 关节表。ID 与 J 编号一一对应，见官方 README「Motor IDs」。
# key 是 LeRobot openarm_mini 驱动的电机名，改动会让校准文件核对失效。
# 名称在 messages.py 里按语言给（键 motor_<name>），这里只放不随语言变的事实。
OPENARM_MINI_MOTORS: dict[str, dict[str, Any]] = {
    "joint_1": {"id": 1, "part": "J1"},
    "joint_2": {"id": 2, "part": "J2"},
    "joint_3": {"id": 3, "part": "J3"},
    "joint_4": {"id": 4, "part": "J4"},
    "joint_5": {"id": 5, "part": "J5"},
    "joint_6": {"id": 6, "part": "J6"},
    "joint_7": {"id": 7, "part": "J7"},
    "gripper": {"id": 8, "part": "J8"},
}

# 官方 setup_motors() 用 `reversed(self.bus.motors)`，即从夹爪往肩部倒着走。
# 菊花链也按这个顺序从末端往回接，顺序变了会让操作员接错线。
MINI_SETUP_ORDER = ["gripper", "joint_7", "joint_6", "joint_5", "joint_4", "joint_3", "joint_2", "joint_1"]

# 编号规则：OAM + 左右臂(L/R) + YYYYMMDD + 当日两位序号。
# Mini 只有 leader 一种形态、只有 7.4V 一档，所以区分位留给左右臂——
# 左右臂的夹爪件和驱动里的方向翻转表都不同，是真实的产品差异。
MINI_SERIAL_PATTERN = re.compile(r"^OAM([LR])(\d{8})(\d{2})$")
# 提示文本随语言变，所以是函数而不是常量。
def serial_hint() -> str:
    return _m("serial_hint")

# STS3215 控制表，地址取自 LeRobot motors/feetech/tables.py
STS3215_MODEL_NUMBER = 777
ADDR_MODEL_NUMBER = 3
ADDR_ID = 5
ADDR_BAUD_RATE = 6
ADDR_RETURN_DELAY_TIME = 7
ADDR_MIN_POSITION_LIMIT = 9
ADDR_MAX_POSITION_LIMIT = 11
ADDR_MAX_TORQUE_LIMIT = 16
ADDR_PHASE = 18
ADDR_POSITION_P_COEFFICIENT = 21
ADDR_POSITION_D_COEFFICIENT = 22
ADDR_POSITION_I_COEFFICIENT = 23
ADDR_PROTECTION_CURRENT = 28
ADDR_HOMING_OFFSET = 31
ADDR_OPERATING_MODE = 33
ADDR_OVERLOAD_TORQUE = 36
ADDR_TORQUE_ENABLE = 40
ADDR_ACCELERATION = 41
ADDR_GOAL_POSITION = 42
ADDR_LOCK = 55
ADDR_PRESENT_POSITION = 56
ADDR_PRESENT_VOLTAGE = 62
ADDR_PRESENT_TEMPERATURE = 63
ADDR_STATUS = 65
ADDR_PRESENT_CURRENT = 69
ADDR_MAX_ACCELERATION = 85
STS3215_POS_MIN = 0
STS3215_POS_MAX = 4095
ENCODER_RESOLUTION = 4096
HALF_TURN = (ENCODER_RESOLUTION - 1) // 2  # 2047，与 LeRobot 完全一致
HOMING_OFFSET_LIMIT = 2047

# Phase 寄存器。configure_motors() 只要求清掉 bit4(0x10)（角度反馈模式），
# 而 openarm_mini.calibrate() 会给全部电机写 12。所以 12 是校准后的期望值，
# 清零 bit4 是底线要求，两者分开判。
PHASE_EXPECTED_AFTER_CALIBRATION = 12
PHASE_ANGLE_FEEDBACK_BIT = 0x10

# LeRobot 每次 connect() 都会重写的运行期参数（configure_motors 的默认值）。
MINI_RUNTIME_EXPECTED = {
    "return_delay_time": 0,
    "max_acceleration": 254,
    "acceleration": 254,
    "operating_mode": 0,
}
# Acceleration 在 SRAM(地址41)，断电归零，LeRobot 连接时重写。
# 断电后拿它判不合格会让每一条臂都挂掉，所以单列出来只提示不判负。
MINI_RUNTIME_ONLY_FIELDS = frozenset({"acceleration"})

# openarm_mini 的关节量程是驱动写死的整圈，只有夹爪是实测值。
# 见 openarm_mini.py calibrate()：非夹爪 range_min=0, range_max=max_res。
MINI_JOINT_RANGE_MIN = 0
MINI_JOINT_RANGE_MAX = ENCODER_RESOLUTION - 1

# 供电档位。BOM 给的是 7.5V 电源，电机额定 7.4V。
# 台架逐颗建站时沿用 5V 低压，联调和校准按官方 7.5V。
MINI_HARDWARE_PROFILES: dict[str, dict[str, Any]] = {
    "mini_bench_5v": {
        "label_key": "profile_bench_label",
        "motor_rated_voltage_v": 7.4,
        "test_supply_voltage_v": 5.0,
        "test_current_limit_a": 4.0,
        "usage_key": "profile_bench_usage",
    },
    "mini_field_7v5": {
        "label_key": "profile_field_label",
        "motor_rated_voltage_v": 7.4,
        "test_supply_voltage_v": 7.5,
        "test_current_limit_a": 2.0,
        "usage_key": "profile_field_usage",
    },
}
# 实测稳态与设定值相差约 0.3V，1.0V 足够容纳纹波，又能把 5V 和 7.5V 分开。
SUPPLY_VOLTAGE_TOLERANCE_V = 1.0

DEFAULT_BAUDRATE = 1_000_000
SCAN_BAUDRATES = [1_000_000, 500_000, 250_000, 128_000, 115_200, 57_600, 38_400, 19_200]
# Feetech STS/SMS 波特率表
STS_BAUDRATE_VALUE = {
    1_000_000: 0,
    500_000: 1,
    250_000: 2,
    128_000: 3,
    115_200: 4,
    57_600: 5,
    38_400: 6,
    19_200: 7,
}

# 只读反馈测试：Mini 是 leader 臂，工作站全程不给它上扭矩。
FEEDBACK_DEFAULT_SECONDS = 8.0
FEEDBACK_SAMPLE_INTERVAL_SEC = 0.05
FEEDBACK_MOVEMENT_COUNTS = 100


def _patch_feetech_packet_timeout(port_handler: Any, port_handler_type: type) -> None:
    """套用 LeRobot 对已发布 Feetech SDK 的超时算法。"""

    def set_packet_timeout(handler: Any, packet_length: int) -> None:
        handler.packet_start_time = handler.getCurrentTime()
        handler.packet_timeout = (
            handler.tx_time_per_byte * packet_length + handler.tx_time_per_byte * 3.0 + 50
        )

    port_handler.setPacketTimeout = set_packet_timeout.__get__(port_handler, port_handler_type)


# HTTP 服务是多线程的，两次点击会同时打开同一个 tty 并互相吃掉对方的回包。
# 所有台架操作在同一把锁上排队。
SERIAL_PORT_LOCK = threading.Lock()
SERIAL_LOCK_TIMEOUT_SEC = 30.0


class FeetechSdkClient:
    def __init__(self, port: str):
        try:
            import scservo_sdk as scs
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                _m("sdk_missing")
            ) from exc

        self.scs = scs
        self.port = port
        self.port_handler = scs.PortHandler(port)
        _patch_feetech_packet_timeout(self.port_handler, scs.PortHandler)
        self.packet_handler = scs.PacketHandler(0)  # STS3215 走协议 0
        self._opened = False
        self._holds_lock = False

    def open(self) -> None:
        if not SERIAL_PORT_LOCK.acquire(timeout=SERIAL_LOCK_TIMEOUT_SEC):
            raise RuntimeError(_m("port_busy"))
        self._holds_lock = True
        try:
            # SDK 的 openPort() 走到 setupPort() 里直接 serial.Serial(...)，
            # 打不开时**抛 pyserial 异常**而不是返回 False——照着返回值判会让
            # 一句英文的 "Could not configure port" 直接穿到页面上，不走三语、
            # 也不告诉操作员该选哪个串口。两种失败都收口到同一条文案。
            try:
                opened = self.port_handler.openPort()
            except Exception as exc:  # noqa: BLE001
                raise ConnectionError(
                    _m("port_open_failed_detail", port=self.port, error=exc)
                ) from exc
            if not opened:
                raise ConnectionError(_m("port_open_failed", port=self.port))
        except BaseException:
            self._release_lock()
            raise
        self._opened = True

    def _release_lock(self) -> None:
        if self._holds_lock:
            self._holds_lock = False
            SERIAL_PORT_LOCK.release()

    def close(self) -> None:
        try:
            if self._opened:
                self.port_handler.closePort()
                self._opened = False
        finally:
            self._release_lock()

    def set_baudrate(self, baudrate: int) -> None:
        # setBaudRate() 对不支持的值返回 False，但重新配置串口失败时同样抛
        # pyserial 异常，所以两条路都要接。
        try:
            accepted = self.port_handler.setBaudRate(baudrate)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                _m("set_baud_failed_detail", baudrate=baudrate, error=exc)
            ) from exc
        if not accepted:
            raise RuntimeError(_m("set_baud_failed", baudrate=baudrate))

    def read_model_number(self, motor_id: int) -> int | None:
        model, comm, error = self.packet_handler.read2ByteTxRx(
            self.port_handler, motor_id, ADDR_MODEL_NUMBER
        )
        if comm != self.scs.COMM_SUCCESS or error != 0:
            return None
        return int(model)

    def broadcast_ping(self) -> dict[int, int]:
        """一个广播包问出总线上所有应答的 ID，返回 {id: 状态字节}。

        逐行移植 LeRobot `FeetechMotorsBus._broadcast_ping()`。已发布的
        `scservo_sdk` 在协议 0 下没有广播 ping，所以官方自己拼的包，这里照做——
        用的原语（BROADCAST_ID / INST_PING / txPacket / setPacketTimeoutMillis /
        isPacketTimeout / readPort）在 feetech-servo-sdk 1.0.0 里都有。
        """

        scs = self.scs
        data_list: dict[int, int] = {}
        status_length = 6
        rx_length = 0
        wait_length = status_length * scs.MAX_ID

        txpacket = [0] * 6
        tx_time_per_byte = (1000.0 / self.port_handler.getBaudRate()) * 10.0
        txpacket[scs.PKT_ID] = scs.BROADCAST_ID
        txpacket[scs.PKT_LENGTH] = 2
        txpacket[scs.PKT_INSTRUCTION] = scs.INST_PING

        if self.packet_handler.txPacket(self.port_handler, txpacket) != scs.COMM_SUCCESS:
            self.port_handler.is_using = False
            return data_list

        self.port_handler.setPacketTimeoutMillis(
            (wait_length * tx_time_per_byte) + (3.0 * scs.MAX_ID) + 16.0
        )
        rxpacket: list[int] = []
        while not self.port_handler.isPacketTimeout() and rx_length < wait_length:
            rxpacket += self.port_handler.readPort(wait_length - rx_length)
            rx_length = len(rxpacket)
        self.port_handler.is_using = False

        if rx_length == 0:
            return data_list

        while True:
            if rx_length < status_length:
                return data_list
            # 找包头
            idx = 0
            for idx in range(0, rx_length - 1):
                if rxpacket[idx] == 0xFF and rxpacket[idx + 1] == 0xFF:
                    break
            if idx == 0:
                checksum = 0
                for pos in range(2, status_length - 1):  # 跳过包头与校验位
                    checksum += rxpacket[pos]
                checksum = ~checksum & 0xFF
                if rxpacket[status_length - 1] == checksum:
                    data_list[rxpacket[scs.PKT_ID]] = rxpacket[scs.PKT_ERROR]
                    del rxpacket[0:status_length]
                    rx_length -= status_length
                    if rx_length == 0:
                        return data_list
                else:
                    del rxpacket[0:2]
                    rx_length -= 2
            else:
                del rxpacket[0:idx]
                rx_length -= idx

    def find_single_sts3215(
        self,
        initial_baudrate: int | None = None,
        initial_id: int | None = None,
        deep_scan: bool = False,
    ) -> tuple[int, int]:
        """认出单独连接的那一颗电机，与官方同法。

        官方 `_find_single_motor_p0()` 每档波特率发**一个广播 ping**，最坏 8 个包。
        早先这里是逐个试 ID（8 × 254 = 2032 次单读，实测空跑 105 秒）——那是从
        SO-ARM101 工作站带过来的写法，并非官方行为。

        比官方多一道闸：广播会返回总线上**所有**应答，所以多接了电机能当场发现。
        官方只取第一个应答，看不出来；而写 ID 时多接一颗，两颗会被改成同一个 ID。

        `deep_scan` 保留逐个试 ID 的老路，默认关闭，只在某颗电机确实不响应广播时用。
        """

        if initial_id is not None and initial_baudrate is not None:
            self.set_baudrate(initial_baudrate)
            model = self.read_model_number(initial_id)
            if model == STS3215_MODEL_NUMBER:
                return initial_baudrate, initial_id
            raise RuntimeError(
                _m(
                    "initial_params_invalid",
                    baudrate=initial_baudrate,
                    id=initial_id,
                    model=model,
                )
            )

        scan_bauds = [initial_baudrate] if initial_baudrate is not None else SCAN_BAUDRATES

        for baud in scan_bauds:
            self.set_baudrate(baud)
            answered = self.broadcast_ping()
            if not answered:
                continue
            if len(answered) > 1:
                raise RuntimeError(
                    _m(
                        "multiple_motors_on_bus",
                        count=len(answered),
                        ids=", ".join(str(i) for i in sorted(answered)),
                    )
                )
            motor_id = next(iter(answered))
            model = self.read_model_number(motor_id)
            if model != STS3215_MODEL_NUMBER:
                raise RuntimeError(
                    _m(
                        "wrong_model_found",
                        baudrate=baud,
                        id=motor_id,
                        model=model,
                        expected=STS3215_MODEL_NUMBER,
                    )
                )
            return baud, motor_id

        if not deep_scan:
            raise RuntimeError(_m("no_motor_found_deep_hint"))

        for baud in scan_bauds:
            self.set_baudrate(baud)
            for motor_id in [1] + [i for i in range(0, self.scs.MAX_ID + 1) if i != 1]:
                model = self.read_model_number(motor_id)
                if model is None:
                    continue
                if model != STS3215_MODEL_NUMBER:
                    raise RuntimeError(
                        _m(
                            "wrong_model_found",
                            baudrate=baud,
                            id=motor_id,
                            model=model,
                            expected=STS3215_MODEL_NUMBER,
                        )
                    )
                return baud, motor_id

        raise RuntimeError(_m("no_motor_found"))

    def disable_torque(self, motor_id: int) -> None:
        comm, error = self.packet_handler.write1ByteTxRx(
            self.port_handler, motor_id, ADDR_TORQUE_ENABLE, 0
        )
        if comm != self.scs.COMM_SUCCESS or error != 0:
            raise RuntimeError(_m("disable_torque_failed", comm=comm, error=error))

    def write_1byte(self, motor_id: int, address: int, value: int) -> None:
        comm, error = self.packet_handler.write1ByteTxRx(
            self.port_handler, motor_id, address, int(value)
        )
        if comm != self.scs.COMM_SUCCESS or error != 0:
            raise RuntimeError(
                _m("write_register_failed", address=address, comm=comm, error=error)
            )

    def write_id(self, motor_id: int, target_id: int) -> None:
        comm, error = self.packet_handler.write1ByteTxRx(
            self.port_handler, motor_id, ADDR_ID, target_id
        )
        if comm != self.scs.COMM_SUCCESS or error != 0:
            raise RuntimeError(_m("write_id_failed", comm=comm, error=error))

    def write_baudrate(self, motor_id: int, baudrate: int) -> None:
        if baudrate not in STS_BAUDRATE_VALUE:
            raise ValueError(_m("unsupported_baudrate", baudrate=baudrate))
        comm, error = self.packet_handler.write1ByteTxRx(
            self.port_handler, motor_id, ADDR_BAUD_RATE, STS_BAUDRATE_VALUE[baudrate]
        )
        if comm != self.scs.COMM_SUCCESS or error != 0:
            raise RuntimeError(_m("write_baud_failed", comm=comm, error=error))

    # `field` 是 messages.py 里的字段键（不含 field_ 前缀），失败信息按当前语言渲染。
    def read_1byte(self, motor_id: int, address: int, field: str = "") -> int:
        value, comm, error = self.packet_handler.read1ByteTxRx(self.port_handler, motor_id, address)
        if comm != self.scs.COMM_SUCCESS or error != 0:
            raise RuntimeError(
                _m("read_fail", field=field_name(field), comm=comm, error=error)
            )
        return int(value)

    def read_2byte(self, motor_id: int, address: int, field: str = "") -> int:
        value, comm, error = self.packet_handler.read2ByteTxRx(self.port_handler, motor_id, address)
        if comm != self.scs.COMM_SUCCESS or error != 0:
            raise RuntimeError(
                _m("read_fail", field=field_name(field), comm=comm, error=error)
            )
        return int(value)

    def read_present_position(self, motor_id: int) -> int:
        return _decode_position(self.read_2byte(motor_id, ADDR_PRESENT_POSITION, "position"))

    def read_present_voltage_raw(self, motor_id: int) -> int:
        # Feetech 返回电压 ×10（52 表示 5.2V）
        return self.read_1byte(motor_id, ADDR_PRESENT_VOLTAGE, "voltage")


def _decode_sign_magnitude(raw_value: int, sign_bit: int) -> int:
    """解码 Feetech 的符号-幅值字段。

    LeRobot 的 STS_SMS_SERIES_ENCODINGS_TABLE 给出各字段的符号位：
    Homing_Offset 用 bit 11，Present_Position / Goal_Position 用 bit 15。
    不解码时一个略小于零的位置会读成 33017 而不是 -249。
    """

    flag = 1 << sign_bit
    return -(raw_value & (flag - 1)) if raw_value & flag else raw_value


def _decode_homing_offset(raw_value: int) -> int:
    return _decode_sign_magnitude(raw_value, 11)


def _decode_position(raw_value: int) -> int:
    return _decode_sign_magnitude(raw_value, 15)


def _id_to_motor_name(motor_id: int) -> str | None:
    for name, meta in OPENARM_MINI_MOTORS.items():
        if meta["id"] == motor_id:
            return name
    return None


def motor_title(motor_name: str) -> str:
    return f"{OPENARM_MINI_MOTORS[motor_name]['part']} · {motor_label(motor_name)}"


def check_supply_voltage(hardware_profile: str, voltage_v: float) -> dict[str, Any]:
    """把实测总线电压和所选档位比对。

    7.4V 的电机接上 12V 会烧，档位不能只是页面上的一个标签。
    任何 EEPROM 写入前先过这一关。
    """

    profile = MINI_HARDWARE_PROFILES.get(hardware_profile)
    if profile is None:
        return {"checked": False, "reason": _m("profile_unset")}

    expected = float(profile["test_supply_voltage_v"])
    rated = float(profile["motor_rated_voltage_v"])
    deviation = round(voltage_v - expected, 2)

    if voltage_v > rated + SUPPLY_VOLTAGE_TOLERANCE_V:
        raise RuntimeError(
            _m("voltage_over_rated", measured=f"{voltage_v:.1f}", rated=f"{rated:.1f}")
        )
    if abs(deviation) > SUPPLY_VOLTAGE_TOLERANCE_V:
        raise RuntimeError(
            _m(
                "voltage_profile_mismatch",
                measured=f"{voltage_v:.1f}",
                expected=f"{expected:.1f}",
                deviation=f"{deviation:+.1f}",
            )
        )
    return {
        "checked": True,
        "measured_v": round(voltage_v, 2),
        "expected_v": expected,
        "rated_v": rated,
        "deviation_v": deviation,
    }


def scan_current_motor(
    port: str,
    initial_baudrate: int | None = None,
    initial_id: int | None = None,
    hardware_profile: str = "",
    deep_scan: bool = False,
) -> dict[str, Any]:
    """认出当前单独连接的那一颗电机。"""

    client = FeetechSdkClient(port)
    try:
        client.open()
        found_baud, found_id = client.find_single_sts3215(
            initial_baudrate, initial_id, deep_scan=deep_scan
        )
        voltage_v = client.read_present_voltage_raw(found_id) / 10.0
        voltage_check = check_supply_voltage(hardware_profile, voltage_v)
        motor_name = _id_to_motor_name(found_id)
        return {
            "ok": True,
            "port": port,
            "voltage_v": round(voltage_v, 2),
            "voltage_check": voltage_check,
            "detected": {"baudrate": found_baud, "id": found_id},
            "deep_scan": deep_scan,
            "already_initialized": motor_name is not None,
            "motor_name": motor_name,
            "motor_title": motor_title(motor_name) if motor_name else None,
            "message": (
                _m("scan_found", id=found_id, baudrate=found_baud)
                if motor_name is None
                else _m("scan_found_known", id=found_id, title=motor_title(motor_name))
            ),
        }
    finally:
        client.close()


def initialize_motor_id(
    port: str,
    motor_name: str,
    initial_baudrate: int | None = None,
    initial_id: int | None = None,
    hardware_profile: str = "",
    deep_scan: bool = False,
) -> dict[str, Any]:
    """给单独连接的一颗电机写入目标 ID 和 1000000 波特率。

    与 LeRobot `MotorsBus.setup_motor()` 同序：先切到电机当前波特率、关扭矩、
    写 ID，再写波特率。额外解了 Lock —— STS3215 的 ID 和波特率在 EEPROM。
    """

    if motor_name not in OPENARM_MINI_MOTORS:
        raise ValueError(_m("unknown_motor", motor=motor_name))

    target_id = OPENARM_MINI_MOTORS[motor_name]["id"]
    client = FeetechSdkClient(port)
    try:
        client.open()
        found_baud, found_id = client.find_single_sts3215(
            initial_baudrate, initial_id, deep_scan=deep_scan
        )
        client.set_baudrate(found_baud)
        # 任何 EEPROM 写入前先验电压：档位选错会烧电机。
        voltage_check = check_supply_voltage(
            hardware_profile, client.read_present_voltage_raw(found_id) / 10.0
        )
        client.disable_torque(found_id)
        client.write_1byte(found_id, ADDR_LOCK, 0)
        id_write_had_timeout_but_recovered = False

        try:
            client.write_id(found_id, target_id)
        except RuntimeError as exc:
            # 有的 STS3215 换 ID 够快，旧 ID 上的应答已经丢了，但 ID 其实写进去了。
            time.sleep(0.06)
            if client.read_model_number(target_id) != STS3215_MODEL_NUMBER:
                raise RuntimeError(_m("write_id_failed_detail", error=exc)) from exc
            id_write_had_timeout_but_recovered = True

        baud_write_err: RuntimeError | None = None
        try:
            client.write_baudrate(target_id, DEFAULT_BAUDRATE)
        except RuntimeError as exc:
            # 切波特率时应答同样可能丢，下面用复读来判定。
            baud_write_err = exc

        time.sleep(0.06)
        client.set_baudrate(DEFAULT_BAUDRATE)
        verified_model = client.read_model_number(target_id)
        if verified_model != STS3215_MODEL_NUMBER:
            client.set_baudrate(found_baud)
            if client.read_model_number(target_id) == STS3215_MODEL_NUMBER:
                if baud_write_err is not None:
                    raise RuntimeError(_m("baud_not_switched")) from baud_write_err
                raise RuntimeError(_m("baud_verify_failed"))
            raise RuntimeError(_m("verify_unreachable"))

        return {
            "ok": True,
            "motor": motor_name,
            "motor_title": motor_title(motor_name),
            "target_id": target_id,
            "port": port,
            "detected": {"baudrate": found_baud, "id": found_id},
            "default_baudrate": DEFAULT_BAUDRATE,
            "verified": True,
            "model_number": verified_model,
            "id_write_timeout_recovered": id_write_had_timeout_but_recovered,
            "voltage_check": voltage_check,
            "message": _m(
                "init_success",
                title=motor_title(motor_name),
                id=target_id,
                baudrate=DEFAULT_BAUDRATE,
            ),
        }
    finally:
        client.close()


def _read_motor_snapshot(client: FeetechSdkClient, motor_name: str) -> dict[str, Any]:
    meta = OPENARM_MINI_MOTORS[motor_name]
    motor_id = meta["id"]
    model = client.read_model_number(motor_id)
    if model != STS3215_MODEL_NUMBER:
        raise RuntimeError(
            _m(
                "snapshot_model_mismatch",
                id=motor_id,
                model=model,
                expected=STS3215_MODEL_NUMBER,
            )
        )

    homing_raw = client.read_2byte(motor_id, ADDR_HOMING_OFFSET, "homing_offset")
    voltage_raw = client.read_1byte(motor_id, ADDR_PRESENT_VOLTAGE, "voltage")
    phase = client.read_1byte(motor_id, ADDR_PHASE, "phase")
    return {
        "motor_name": motor_name,
        "motor_title": motor_title(motor_name),
        "part": meta["part"],
        "motor_id": motor_id,
        "model_number": model,
        "baudrate": DEFAULT_BAUDRATE,
        "return_delay_time": client.read_1byte(motor_id, ADDR_RETURN_DELAY_TIME, "return_delay"),
        "min_position_limit": client.read_2byte(motor_id, ADDR_MIN_POSITION_LIMIT, "min_position"),
        "max_position_limit": client.read_2byte(motor_id, ADDR_MAX_POSITION_LIMIT, "max_position"),
        "max_torque_limit": client.read_2byte(motor_id, ADDR_MAX_TORQUE_LIMIT, "max_torque"),
        "phase": phase,
        "angle_feedback_bit_set": bool(phase & PHASE_ANGLE_FEEDBACK_BIT),
        "position_p_coefficient": client.read_1byte(motor_id, ADDR_POSITION_P_COEFFICIENT, "p_coefficient"),
        "position_d_coefficient": client.read_1byte(motor_id, ADDR_POSITION_D_COEFFICIENT, "d_coefficient"),
        "position_i_coefficient": client.read_1byte(motor_id, ADDR_POSITION_I_COEFFICIENT, "i_coefficient"),
        "protection_current": client.read_2byte(motor_id, ADDR_PROTECTION_CURRENT, "protection_current"),
        "homing_offset_raw": homing_raw,
        "homing_offset": _decode_homing_offset(homing_raw),
        "operating_mode": client.read_1byte(motor_id, ADDR_OPERATING_MODE, "operating_mode"),
        "overload_torque": client.read_1byte(motor_id, ADDR_OVERLOAD_TORQUE, "overload_torque"),
        "torque_enable": client.read_1byte(motor_id, ADDR_TORQUE_ENABLE, "torque_enable"),
        "acceleration": client.read_1byte(motor_id, ADDR_ACCELERATION, "acceleration"),
        "max_acceleration": client.read_1byte(motor_id, ADDR_MAX_ACCELERATION, "max_acceleration"),
        "present_position": client.read_present_position(motor_id),
        "voltage_raw": voltage_raw,
        "voltage_v": round(voltage_raw / 10.0, 2),
        "temperature_c": client.read_1byte(motor_id, ADDR_PRESENT_TEMPERATURE, "temperature"),
        "status_raw": client.read_1byte(motor_id, ADDR_STATUS, "status"),
        "present_current_raw": client.read_2byte(motor_id, ADDR_PRESENT_CURRENT, "current"),
    }


def scan_all_motors_read_only(port: str) -> dict[str, Any]:
    """读遍 8 颗电机，不开扭矩、不下发目标位置、不写 EEPROM。"""

    client = FeetechSdkClient(port)
    results: list[dict[str, Any]] = []
    try:
        client.open()
        client.set_baudrate(DEFAULT_BAUDRATE)
        for motor_name in sorted(OPENARM_MINI_MOTORS, key=lambda n: OPENARM_MINI_MOTORS[n]["id"]):
            try:
                snapshot = _read_motor_snapshot(client, motor_name)
                snapshot["ok"] = True
                snapshot["reason"] = ""
                results.append(snapshot)
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "ok": False,
                        "motor_name": motor_name,
                        "motor_title": motor_title(motor_name),
                        "part": OPENARM_MINI_MOTORS[motor_name]["part"],
                        "motor_id": OPENARM_MINI_MOTORS[motor_name]["id"],
                        "reason": str(exc),
                    }
                )

        passed = sum(1 for r in results if r["ok"])
        return {
            "ok": True,
            "read_only": True,
            "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "port": port,
            "overall_ok": passed == len(OPENARM_MINI_MOTORS),
            "passed": passed,
            "total": len(OPENARM_MINI_MOTORS),
            "results": results,
        }
    finally:
        client.close()


def get_motor_params(port: str, motor_name: str) -> dict[str, Any]:
    if motor_name not in OPENARM_MINI_MOTORS:
        raise ValueError(_m("unknown_motor", motor=motor_name))
    client = FeetechSdkClient(port)
    try:
        client.open()
        client.set_baudrate(DEFAULT_BAUDRATE)
        return {"ok": True, "port": port, **_read_motor_snapshot(client, motor_name)}
    finally:
        client.close()


def _unwrap_positions(samples: list[int]) -> list[int]:
    """把模 4096 的位置流接回连续序列。

    直接对模数流取 min/max 会把跨过 4095→0 接缝的一次摆动看成整圈，
    先展开才能量出真实行程。
    """

    out = [samples[0]]
    for prev, cur in zip(samples, samples[1:]):
        delta = cur - prev
        if delta > ENCODER_RESOLUTION // 2:
            delta -= ENCODER_RESOLUTION
        elif delta < -(ENCODER_RESOLUTION // 2):
            delta += ENCODER_RESOLUTION
        out.append(out[-1] + delta)
    return out


def analyse_travel(samples: list[int]) -> dict[str, Any]:
    """把一次手动摆动换算成行程跨度。

    openarm_mini 给 joint_1..joint_7 写死整圈量程（range 0..4095），所以这里
    不需要像 SO-101 那样算停放窗口——量出跨度只为证明关节能动、编码器读数连续。
    夹爪例外：它的量程是校准时实测的闭合/张开位置，跨度直接对应校准质量。
    """

    unwrapped = _unwrap_positions(samples)
    span = max(unwrapped) - min(unwrapped)
    crossings = sum(
        1 for prev, cur in zip(samples, samples[1:]) if abs(cur - prev) > ENCODER_RESOLUTION // 2
    )
    return {
        "span": span,
        "moved": span >= FEEDBACK_MOVEMENT_COUNTS,
        "over_full_turn": span > ENCODER_RESOLUTION,
        "zero_crossings": crossings,
        "wraps_encoder_zero": crossings > 0,
        "observed_min": min(samples),
        "observed_max": max(samples),
        "current_position": samples[-1],
    }


def feedback_test(
    port: str, motor_name: str, duration_sec: float = FEEDBACK_DEFAULT_SECONDS
) -> dict[str, Any]:
    """只读反馈测试：操作员手动摆动关节，工作站记录读数。

    Mini 是 leader 臂，正常使用时人手驱动、电机只做编码器。工作站因此全程
    不开扭矩、不下发目标位置——给一条手持臂上扭矩既没有对应的使用场景，
    也会在装配阶段把人和结构件都置于风险里。
    """

    if motor_name not in OPENARM_MINI_MOTORS:
        raise ValueError(_m("unknown_motor", motor=motor_name))
    duration_sec = max(2.0, min(float(duration_sec), 30.0))
    motor_id = OPENARM_MINI_MOTORS[motor_name]["id"]

    client = FeetechSdkClient(port)
    samples: list[int] = []
    try:
        client.open()
        client.set_baudrate(DEFAULT_BAUDRATE)
        model = client.read_model_number(motor_id)
        if model != STS3215_MODEL_NUMBER:
            raise RuntimeError(_m("model_mismatch_at_id", id=motor_id, model=model))
        torque_enable = client.read_1byte(motor_id, ADDR_TORQUE_ENABLE, "torque_enable")
        homing = _decode_homing_offset(
            client.read_2byte(motor_id, ADDR_HOMING_OFFSET, "homing_offset")
        )
        start_temperature = client.read_1byte(motor_id, ADDR_PRESENT_TEMPERATURE, "temperature")
        voltage_raw = client.read_present_voltage_raw(motor_id)
        deadline = time.monotonic() + duration_sec
        while time.monotonic() < deadline:
            present = client.read_present_position(motor_id)
            # 折算回机械编码器读数，跟中点偏移无关，复测之间才可比。
            samples.append((present + homing) % ENCODER_RESOLUTION)
            time.sleep(FEEDBACK_SAMPLE_INTERVAL_SEC)
    finally:
        client.close()

    analysis = analyse_travel(samples)
    reason = ""
    if not analysis["moved"]:
        reason = _m(
            "feedback_no_movement",
            seconds=f"{duration_sec:.0f}",
            counts=FEEDBACK_MOVEMENT_COUNTS,
        )
    return {
        "ok": analysis["moved"],
        "read_only": True,
        "motor_name": motor_name,
        "motor_title": motor_title(motor_name),
        "motor_id": motor_id,
        "duration_sec": duration_sec,
        "samples": len(samples),
        "torque_enable_before": torque_enable,
        "homing_offset": homing,
        "temperature_c": start_temperature,
        "voltage_v": round(voltage_raw / 10.0, 2),
        "reason": reason,
        **analysis,
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def evaluate_precheck_pose(present: int, homing: int) -> dict[str, Any]:
    """单个关节的校准前判据。纯函数，好用现场实测的数值钉住。

    **必须取模**：编码器是模 4096 的，扣掉一个已有的中点偏移完全可能落到
    0..4095 之外，而那描述的是一个完全正常的姿态。漏了取模会把每一条已经
    校准过的臂都拦下来——2026-09-29 现场就报出 `encoder=-1497` 并拦停了一个
    摆在零位的关节，而 -1497 在 4096 计数的轮子上就是 2599。

    两条拦截各对应官方程序真会中止的情形：
    - `present > 4095`：多圈累计读数。断电重上电能让它回到单圈内。
    - `|actual − 2047| > 2047`：偏移装不进 11 位符号-幅值寄存器。取模之后
      只有 `actual == 4095` 这一个值能触发（偏移 2048），所以它是可达的，
      不是纯防御性检查。
    """

    actual = (present + homing) % ENCODER_RESOLUTION
    predicted_homing = actual - HALF_TURN
    reason = ""
    if present > STS3215_POS_MAX:
        reason = _m("precheck_multiturn", present=present, max=STS3215_POS_MAX)
    elif abs(predicted_homing) > HOMING_OFFSET_LIMIT:
        reason = _m(
            "precheck_offset_overflow",
            actual=actual,
            offset=predicted_homing,
            limit=HOMING_OFFSET_LIMIT,
        )
    return {
        "ok": not reason,
        "present_position": present,
        "homing_offset": homing,
        "encoder_position": actual,
        "predicted_homing_offset": predicted_homing,
        "reason": reason,
    }


def precheck_calibration_poses(port: str) -> dict[str, Any]:
    """校准前只读预检：拦下单次读数真能证伪的那一件事。

    `set_half_turn_homings()` 先 `reset_calibration()`（homing 归零、量程 0..4095）
    再读位置，然后写 `homing = 位置 − 2047`。偏移存在 11 位符号-幅值寄存器里，
    装不下超过 ±2047 的值。位置读数超出一圈（多圈累计）时官方程序会直接报错中止，
    断电 5 秒重新上电就能让读数回到单圈内。

    关节落在编码器物理零点两侧是正常的：openarm_mini 给 joint_1..joint_7 写死
    整圈量程，不存在「行程必须落进停放位 ±2047」这条 SO-101 式的约束，
    所以这里不做停放窗口判断，也不需要行程试扫。
    """

    client = FeetechSdkClient(port)
    results: list[dict[str, Any]] = []
    try:
        client.open()
        client.set_baudrate(DEFAULT_BAUDRATE)
        for motor_name in sorted(OPENARM_MINI_MOTORS, key=lambda n: OPENARM_MINI_MOTORS[n]["id"]):
            motor_id = OPENARM_MINI_MOTORS[motor_name]["id"]
            try:
                model = client.read_model_number(motor_id)
                if model != STS3215_MODEL_NUMBER:
                    raise RuntimeError(f"model={model}, expected={STS3215_MODEL_NUMBER}")
                homing = _decode_homing_offset(
                    client.read_2byte(motor_id, ADDR_HOMING_OFFSET, "homing_offset")
                )
                present = client.read_present_position(motor_id)
                phase = client.read_1byte(motor_id, ADDR_PHASE, "phase")
                # 官方读的是 reset_calibration() 之后的值，等于机械编码器读数。
                # **必须取模**：编码器是模 4096 的，扣掉一个已有的中点偏移完全
                # 可能落到 0..4095 之外，而那描述的是一个正常姿态。漏了取模会把
                # 每一条校准过的臂都拦下来——现场报出 encoder=-1497 就是这个 bug，
                # -1497 在 4096 计数的轮子上就是 2599。
                verdict = evaluate_precheck_pose(present, homing)
                results.append(
                    {
                        "motor_name": motor_name,
                        "motor_title": motor_title(motor_name),
                        "part": OPENARM_MINI_MOTORS[motor_name]["part"],
                        "motor_id": motor_id,
                        "phase": phase,
                        "angle_feedback_bit_set": bool(phase & PHASE_ANGLE_FEEDBACK_BIT),
                        **verdict,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "ok": False,
                        "motor_name": motor_name,
                        "motor_title": motor_title(motor_name),
                        "part": OPENARM_MINI_MOTORS[motor_name]["part"],
                        "motor_id": motor_id,
                        "reason": str(exc),
                    }
                )
    finally:
        client.close()

    passed = sum(1 for r in results if r["ok"])
    return {
        "ok": True,
        "read_only": True,
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "port": port,
        "overall_ok": passed == len(OPENARM_MINI_MOTORS),
        "passed": passed,
        "total": len(OPENARM_MINI_MOTORS),
        "results": results,
        "note": _m("precheck_note"),
    }


def _stable_port_aliases() -> dict[str, str]:
    """把 /dev/ttyACMx 映射到 /dev/serial/by-id 别名。

    内核名每次重新枚举都会变，by-id 别名由 USB 序列号生成，拔插后不变。
    """

    aliases: dict[str, str] = {}
    by_id = Path("/dev/serial/by-id")
    if not by_id.is_dir():
        return aliases
    for link in by_id.iterdir():
        try:
            aliases[str(link.resolve())] = str(link)
        except OSError:
            continue
    return aliases


# 内核给每个板载 UART 都建一个 /dev/ttyS* 节点，插没插东西都在——本机就有 32 个。
# 让操作员在 33 条里找出那一条适配器，是选错串口的主要来源。真适配器有 USB 身份
# （vid/pid），并且 udev 会给它建 /dev/serial/by-id 别名；两者都不满足的就不是候选。
def _is_usb_adapter(info: Any, stable_alias: str) -> bool:
    if stable_alias:
        return True
    if getattr(info, "vid", None) is not None:
        return True
    return bool(re.match(r"^tty(USB|ACM)\d+$", Path(info.device).name))


def list_serial_ports() -> list[dict[str, Any]]:
    aliases = _stable_port_aliases()
    ports = []
    for p in list_ports.comports():
        stable = aliases.get(str(Path(p.device).resolve()), "")
        device = stable or p.device
        ports.append(
            {
                "device": device,
                "kernel_device": p.device,
                "stable_device": stable,
                "description": p.description,
                "hwid": p.hwid,
                "serial_number": p.serial_number or "",
                "product": p.product or "",
                "is_adapter": _is_usb_adapter(p, stable),
                # 权限不足时 openPort() 会抛异常，提前说比等它失败有用。
                "writable": os.access(p.device, os.R_OK | os.W_OK),
            }
        )
    # 候选排前面，操作员不用滚动
    ports.sort(key=lambda entry: (not entry["is_adapter"], entry["device"]))
    return ports


def detect_serial_port() -> dict[str, Any]:
    """挑出那一个 USB 串口适配器。

    只有一个候选时直接给出它，页面不必让人选。多个候选时不猜——两条臂的
    适配器同时插着是正常的工位状态，猜错会把 ID 写到另一条臂上。
    """

    ports = list_serial_ports()
    candidates = [entry for entry in ports if entry["is_adapter"]]

    if not candidates:
        status, port, message = "none", "", _m("port_detect_none")
    elif len(candidates) == 1:
        chosen = candidates[0]
        status, port = "one", chosen["device"]
        message = _m(
            "port_detect_one",
            description=chosen["description"] or chosen["device"],
            serial=chosen["serial_number"] or "-",
        )
    else:
        status, port = "many", ""
        message = _m("port_detect_many", count=len(candidates))

    warnings = [
        _m("port_not_writable", port=entry["kernel_device"])
        for entry in candidates
        if not entry["writable"]
    ]
    return {
        "ok": True,
        "status": status,
        "port": port,
        "message": message,
        "warnings": warnings,
        "candidates": candidates,
        "ports": ports,
        "total": len(ports),
    }


def reconnect_port(port: str) -> dict[str, Any]:
    client = FeetechSdkClient(port)
    try:
        client.open()
        client.set_baudrate(DEFAULT_BAUDRATE)
        return {"ok": True, "port": port, "message": _m("reconnect_ok", port=port)}
    finally:
        client.close()


def _archive_root() -> Path:
    return Path(__file__).resolve().parent.parent / "test_reports"


def _session_dir() -> Path:
    return _archive_root() / ".sessions"


def validate_serial(robot_id: str) -> re.Match[str]:
    match = MINI_SERIAL_PATTERN.fullmatch(robot_id)
    if match is None:
        raise ValueError(_m("serial_malformed", robot_id=robot_id, hint=serial_hint()))
    return match


def append_session_record(robot_id: str, action: str, payload: dict[str, Any]) -> None:
    """把一次操作追加进这条臂的会话日志。

    页面状态只在浏览器内存里，关掉标签页就把整份测试记录带走了。
    这份 jsonl 是归档要用的持久副本。记日志失败绝不能打断台架操作。
    """

    if not robot_id or MINI_SERIAL_PATTERN.fullmatch(robot_id) is None:
        return
    record = {
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "action": action,
        "robot_id": robot_id,
        "data": payload,
    }
    try:
        directory = _session_dir()
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / f"{robot_id}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_session_records(robot_id: str) -> list[dict[str, Any]]:
    validate_serial(robot_id)
    path = _session_dir() / f"{robot_id}.jsonl"
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _calibration_root() -> Path:
    """解析 LeRobot 存校准文件的根目录。

    照抄 LeRobot `utils/constants.py` 的优先级：
    `HF_LEROBOT_CALIBRATION` > `HF_LEROBOT_HOME/calibration` >
    `HF_HOME/lerobot/calibration` > `XDG_CACHE_HOME`（默认 ~/.cache）
    `/huggingface/lerobot/calibration`。

    写死 ~/.cache 曾经是个真 bug：装机时把 HF_HOME 指到大盘是常见做法，
    那样工作站会在错误的目录里找文件，给一台**已经校准**的臂报「未找到校准文件」，
    或者更糟——拿一份过期的旧文件去核对。
    """

    explicit = os.getenv("HF_LEROBOT_CALIBRATION")
    if explicit:
        return Path(explicit).expanduser()
    lerobot_home = os.getenv("HF_LEROBOT_HOME")
    if lerobot_home:
        return Path(lerobot_home).expanduser() / "calibration"
    hf_home = os.getenv("HF_HOME")
    if hf_home:
        return Path(hf_home).expanduser() / "lerobot" / "calibration"
    xdg_cache = os.getenv("XDG_CACHE_HOME")
    base = Path(xdg_cache).expanduser() if xdg_cache else Path.home() / ".cache"
    return base / "huggingface" / "lerobot" / "calibration"


def _calibration_dir() -> Path:
    # LeRobot 按 teleoperator 的 name 建子目录，openarm_mini 驱动的 name = "openarm_mini"。
    return _calibration_root() / "teleoperators" / "openarm_mini"


def _calibration_file(robot_id: str) -> Path:
    validate_serial(robot_id)
    return _calibration_dir() / f"{robot_id}.json"


def collect_known_serials() -> set[str]:
    """收集今天已经用掉的编号。

    只看归档目录会漏掉已校准但还没归档的臂，导致重复发号，所以校准缓存也要扫。
    """

    known: set[str] = set()
    for directory in (_session_dir(), _archive_root(), _calibration_dir()):
        if not directory.is_dir():
            continue
        for entry in directory.iterdir():
            candidate = entry.name.split(".")[0]
            if MINI_SERIAL_PATTERN.fullmatch(candidate):
                known.add(candidate)
    return known


def suggest_serial(side: str, on_date: date | None = None) -> dict[str, Any]:
    if side not in ("left", "right"):
        raise ValueError(_m("side_invalid"))
    day = (on_date or date.today()).strftime("%Y%m%d")
    code = "L" if side == "left" else "R"
    known = collect_known_serials()
    for index in range(1, 100):
        candidate = f"OAM{code}{day}{index:02d}"
        if candidate not in known:
            return {
                "robot_id": candidate,
                "side": side,
                "date": day,
                "sequence": index,
                "known_count": len(known),
            }
    raise RuntimeError(_m("serial_exhausted", day=day, code=code))


def verify_calibration_and_config(port: str, robot_id: str) -> dict[str, Any]:
    """比对 LeRobot 校准文件、电机 EEPROM 和运行期配置。

    期望量程不是从文件里照抄的：joint_1..joint_7 的量程由 openarm_mini 驱动
    写死成整圈，文件里出现别的值本身就说明这份文件不是该驱动生成的。
    夹爪的量程是校准时实测的闭合/张开位置，只能以文件为准。
    """

    path = _calibration_file(robot_id)
    if not path.is_file():
        raise FileNotFoundError(_m("calibration_file_missing", path=path))
    calibration = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(calibration, dict):
        raise ValueError(_m("calibration_file_invalid"))

    scan = scan_all_motors_read_only(port)
    snapshot_by_name = {r["motor_name"]: r for r in scan["results"] if r.get("ok")}
    results: list[dict[str, Any]] = []

    for motor_name in sorted(OPENARM_MINI_MOTORS, key=lambda n: OPENARM_MINI_MOTORS[n]["id"]):
        snapshot = snapshot_by_name.get(motor_name)
        cached = calibration.get(motor_name)
        if snapshot is None or not isinstance(cached, dict):
            results.append(
                {
                    "ok": False,
                    "motor_name": motor_name,
                    "motor_title": motor_title(motor_name),
                    "motor_id": OPENARM_MINI_MOTORS[motor_name]["id"],
                    "reason": (
                        _m("motor_read_failed")
                        if snapshot is None
                        else _m("calibration_missing_joint")
                    ),
                    "checks": [],
                }
            )
            continue

        expected: dict[str, int] = {
            "motor_id": int(cached.get("id", -1)),
            "homing_offset": int(cached.get("homing_offset", 0)),
            "min_position_limit": int(cached.get("range_min", -1)),
            "max_position_limit": int(cached.get("range_max", -1)),
            "phase": PHASE_EXPECTED_AFTER_CALIBRATION,
            **MINI_RUNTIME_EXPECTED,
        }

        checks = []
        for field, expected_value in expected.items():
            actual_value = snapshot.get(field)
            checks.append(
                {
                    "field": field,
                    "expected": expected_value,
                    "actual": actual_value,
                    "ok": actual_value == expected_value,
                    "runtime_only": field in MINI_RUNTIME_ONLY_FIELDS,
                }
            )

        driver_range_note = ""
        if motor_name != "gripper":
            file_min = int(cached.get("range_min", -1))
            file_max = int(cached.get("range_max", -1))
            if (file_min, file_max) != (MINI_JOINT_RANGE_MIN, MINI_JOINT_RANGE_MAX):
                driver_range_note = _m(
                    "driver_range_mismatch",
                    file_min=file_min,
                    file_max=file_max,
                    min=MINI_JOINT_RANGE_MIN,
                    max=MINI_JOINT_RANGE_MAX,
                )

        failed = [c["field"] for c in checks if not c["ok"] and not c["runtime_only"]]
        runtime_pending = [c["field"] for c in checks if not c["ok"] and c["runtime_only"]]
        reason = ""
        if failed:
            reason = _m("fields_inconsistent", fields=", ".join(failed))
        elif runtime_pending:
            reason = _m("runtime_fields_pending", fields=", ".join(runtime_pending))
        if driver_range_note:
            reason = f"{reason}；{driver_range_note}" if reason else driver_range_note

        results.append(
            {
                "ok": not failed and not driver_range_note,
                "motor_name": motor_name,
                "motor_title": motor_title(motor_name),
                "motor_id": OPENARM_MINI_MOTORS[motor_name]["id"],
                "reason": reason,
                "runtime_pending": runtime_pending,
                "checks": checks,
            }
        )

    passed = sum(1 for r in results if r["ok"])
    return {
        "ok": True,
        "read_only": True,
        "robot_id": robot_id,
        "calibration_file": str(path),
        "teleop_type": "openarm_mini",
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "overall_ok": passed == len(OPENARM_MINI_MOTORS),
        "passed": passed,
        "total": len(OPENARM_MINI_MOTORS),
        "runtime_fields_pending": sorted(
            {f for r in results for f in r.get("runtime_pending", [])}
        ),
        "results": results,
        "motor_scan": scan,
    }


LEROBOT_ENV_VAR = "OPENARM_MINI_LEROBOT_CALIBRATE"
# 本工作站专用的 LeRobot 环境放在**项目目录内**，不要放到 ~/Projects/.venvs/。
# 那个共享目录被 SO-ARM101 工作站用 sorted(glob(...)) 扫描并取第一个匹配，
# 在那里新建一个 venv 会按字母序悄悄改变它选中的 LeRobot。放项目内它看不见。
PROJECT_LEROBOT_VENVS = (".venv-lerobot", ".venv")
_lerobot_override: str | None = None


def set_lerobot_calibrate_override(path: str | None) -> None:
    """记下 --lerobot-calibrate 指定的路径（启动时调用一次）。"""

    global _lerobot_override
    _lerobot_override = path or None


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_lerobot_calibrate() -> dict[str, Any]:
    """解析要启动哪个 lerobot-calibrate，并说明是从哪来的。

    显式指定优先，其次项目内的 venv，然后才是 PATH 和共享 venv 目录。
    显式指定的路径不存在时**直接报错**，不静默回退——路径打错了却回退到
    另一个 LeRobot，正是这个参数要防的事。
    """

    explicit = _lerobot_override or os.getenv(LEROBOT_ENV_VAR) or ""
    if explicit:
        source = "--lerobot-calibrate" if _lerobot_override else LEROBOT_ENV_VAR
        candidate = Path(explicit).expanduser()
        if not (candidate.is_file() and os.access(candidate, os.X_OK)):
            raise RuntimeError(
                _m("lerobot_override_missing", path=candidate, env=LEROBOT_ENV_VAR)
            )
        return {"path": str(candidate), "source": source}

    for name in PROJECT_LEROBOT_VENVS:
        candidate = _project_root() / name / "bin" / "lerobot-calibrate"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return {
                    "path": str(candidate),
                    "source": _m("lerobot_source_project", name=name),
                }

    on_path = shutil.which("lerobot-calibrate")
    if on_path:
        return {"path": on_path, "source": "PATH"}

    for root in (Path.home() / "Projects/.venvs", Path.home() / ".venvs"):
        if not root.is_dir():
            continue
        for candidate in sorted(root.glob("*/bin/lerobot-calibrate")):
            if os.access(candidate, os.X_OK):
                return {
                    "path": str(candidate),
                    "source": _m("lerobot_source_shared", name=root.name),
                }

    return {"path": "", "source": ""}


def find_lerobot_calibrate() -> str | None:
    """只要路径。解析失败或显式路径无效时返回 None，由调用方给出文案。"""

    try:
        return resolve_lerobot_calibrate()["path"] or None
    except RuntimeError:
        return None


# openarm_mini 是较新加入 LeRobot 的遥操作臂。本机上很可能同时装着别的、
# 更老的 LeRobot 环境——那些版本的 --teleop.type 根本没有这个选项，
# 启动后只会被 argparse 以退出码 2 顶回来。探测一次，别让操作员对着
# 一段 argparse 用法输出猜原因。
_TELEOP_SUPPORT_CACHE: dict[tuple[str, float], bool] = {}


def _executable_python(executable: str) -> str | None:
    """取控制台脚本 shebang 里的解释器，用来探测它所在环境装了什么。"""

    try:
        with open(executable, "rb") as handle:
            first_line = handle.readline(512).decode("utf-8", errors="replace").strip()
    except OSError:
        return None
    if first_line.startswith("#!"):
        interpreter = first_line[2:].strip().split(" ")[0]
        if interpreter and os.access(interpreter, os.X_OK):
            return interpreter
    sibling = Path(executable).resolve().parent / "python"
    return str(sibling) if os.access(sibling, os.X_OK) else None


def lerobot_supports_openarm_mini(executable: str) -> bool | None:
    """这套 LeRobot 里有没有 openarm_mini 驱动。None 表示探测不出来。"""

    try:
        stamp = Path(executable).stat().st_mtime
    except OSError:
        return None
    key = (executable, stamp)
    if key in _TELEOP_SUPPORT_CACHE:
        return _TELEOP_SUPPORT_CACHE[key]

    interpreter = _executable_python(executable)
    if interpreter is None:
        return None
    try:
        completed = subprocess.run(  # noqa: S603
            [
                interpreter,
                "-c",
                "import importlib.util as u, sys; "
                "sys.exit(0 if u.find_spec('lerobot.teleoperators.openarm_mini') else 3)",
            ],
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode not in (0, 3):
        return None
    supported = completed.returncode == 0
    _TELEOP_SUPPORT_CACHE[key] = supported
    return supported


# 官方程序可能停在的失败点，每条都配一个操作员在台架上就能做完的处置。
# 特征串逐条引自 LeRobot 上游源码；版本升级改了措辞时，tests 会先报错，
# 而不是在现场静默地匹配不到任何东西。
CALIBRATION_ISSUE_SIGNATURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # encoding_utils.py:23 —— 中点偏移装不进 11 位寄存器
    ("offset_overflow", ("Magnitude", "exceeds")),
    # motors_bus.py:538 —— 串口根本打不开
    ("port_unavailable", ("Could not connect on port",)),
    # motors_bus.py:497 —— 菊花链上的电机与预期不符
    ("motor_mismatch", ("Full expected motor list",)),
    # openarm_mini.py calibrate() —— 沿用了旧校准文件，什么都没测
    ("reused_existing", ("Using existing calibration for",)),
    # draccus/argparse —— 这套 LeRobot 根本没有 openarm_mini 这个选项
    ("teleop_type_unknown", ("invalid choice: 'openarm_mini'",)),
)

# 每个失败码都有一条处置文案，键是 remedy_<码>。tests 锁住一一对应。
CALIBRATION_ISSUE_CODES: tuple[str, ...] = (
    "offset_overflow",
    "port_unavailable",
    "motor_mismatch",
    "reused_existing",
    "teleop_type_unknown",
    "finished_unsaved",
)


def issue_remedy(code: str) -> str:
    return _m("remedy_" + code)


def diagnose_calibration_output(output: str, phase: str) -> list[str]:
    """说清楚哪里出了问题，页面才能给处置而不是只甩一段日志。"""

    codes = [
        code
        for code, needles in CALIBRATION_ISSUE_SIGNATURES
        if all(needle in output for needle in needles)
    ]
    if phase == "finished_unsaved" and "reused_existing" not in codes:
        codes.append("finished_unsaved")
    return codes


class CalibrationSession:
    """把官方 lerobot-calibrate 当子进程跑。

    工作站不重新实现校准算法，只驱动官方程序，所以保存下来的文件和在终端里
    直接跑完全一样，不存在实现分叉。openarm_mini 的 calibrate() 用的是普通
    `input()`，管道可用，三到四次确认因此能映射成页面按钮。
    """

    # 阶段按时间顺序排列。openarm_mini 的流程与 SO-101 不同：
    # 零位一次确认（整臂下垂、夹爪闭合），随后夹爪闭合、张开各一次，
    # joint_1..joint_7 不采集行程——驱动给它们写死整圈量程。
    PHASE_PATTERNS = (
        ("await_existing", "press ENTER to run new calibration"),
        ("reused_existing", "Using existing calibration for"),
        ("await_zero", "Press ENTER when ready..."),
        ("await_gripper_closed", "Press ENTER when gripper is closed..."),
        ("await_gripper_open", "Press ENTER when gripper is fully open..."),
        ("saved", "Calibration complete and saved to"),
    )
    # 沿用旧文件的提示必须回答字面量 "c" 才会真的重新校准；其余都是裸回车。
    ANSWER_RECALIBRATE = "c"
    # 阶段 → (文案键前缀, 该提示要回答什么)。文案在 status() 时按当前语言渲染，
    # 所以操作员中途换语言，下一次轮询就跟着变。
    PHASE_PROMPTS: dict[str, tuple[str, str]] = {
        "await_existing": ("prompt_existing", ANSWER_RECALIBRATE),
        "await_zero": ("prompt_zero", ""),
        "await_gripper_closed": ("prompt_gripper_closed", ""),
        "await_gripper_open": ("prompt_gripper_open", ""),
    }

    @classmethod
    def prompt_for(cls, phase: str) -> dict[str, str] | None:
        entry = cls.PHASE_PROMPTS.get(phase)
        if entry is None:
            return None
        prefix, answer = entry
        return {
            "title": _m(prefix + "_title"),
            "detail": _m(prefix + "_detail"),
            "action": _m(prefix + "_action"),
            "answer": answer,
        }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[str] | None = None
        self._buffer = ""
        self._phase_state = ""
        self._robot_id = ""
        self._started_at = ""
        self._reader: threading.Thread | None = None
        self._answers: list[str] = []
        self._had_calibration_file = False
        self._command: list[str] = []

    def _is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def is_running(self) -> bool:
        with self._lock:
            return self._is_running()

    def _pump(self, proc: subprocess.Popen[str]) -> None:
        """抽干 stdout，见到标记就把阶段锁存下来。

        两个坑：`input("提示")` 写提示时不带换行，按行读会等到操作员已经答完
        才看见它；而日志会不断刷新，固定窗口里见过一次的标记会被冲走——
        阶段必须在标记到达时锁存，不能事后重新推导。
        """

        assert proc.stdout is not None
        fd = proc.stdout.fileno()
        pending = ""
        while True:
            try:
                raw = os.read(fd, 4096)
            except OSError:
                break
            if not raw:
                break
            chunk = raw.decode("utf-8", errors="replace")
            pending = (pending + chunk)[-600:]
            with self._lock:
                self._buffer += chunk
                if len(self._buffer) > 200_000:
                    self._buffer = self._buffer[-100_000:]
                for phase, needle in self.PHASE_PATTERNS:
                    if needle in pending:
                        self._phase_state = phase
                        pending = ""
                        break

    def start(self, port: str, robot_id: str) -> dict[str, Any]:
        validate_serial(robot_id)
        # 用 resolve 而不是 find：显式路径写错时要报「指定的路径无效」，
        # 而不是笼统的「找不到 lerobot-calibrate」。
        executable = resolve_lerobot_calibrate()["path"] or None
        if executable is None:
            raise RuntimeError(_m("calibrate_not_found"))
        if lerobot_supports_openarm_mini(executable) is False:
            raise RuntimeError(_m("calibrate_no_driver", executable=executable))
        with self._lock:
            if self._is_running():
                raise RuntimeError(_m("calibration_already_running"))
            self._buffer = ""
            self._phase_state = ""
            self._robot_id = robot_id
            self._started_at = datetime.now().astimezone().isoformat(timespec="seconds")
            self._answers = []
            self._had_calibration_file = _calibration_file(robot_id).is_file()

        # 参数与官方 README 的校准命令逐字一致。
        flags = [
            "--teleop.type=openarm_mini",
            f"--teleop.port={port}",
            f"--teleop.id={robot_id}",
        ]
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        proc = subprocess.Popen(  # noqa: S603
            [executable, *flags],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        with self._lock:
            self._proc = proc
            self._command = [executable, *flags]
            self._reader = threading.Thread(target=self._pump, args=(proc,), daemon=True)
            self._reader.start()
        return {"ok": True, "command": [executable, *flags], "robot_id": robot_id}

    def _phase(self, running: bool, returncode: int | None) -> str:
        # 还没跑过：不是失败，页面不该为一场没开始的校准给处置。
        if self._proc is None:
            return ""
        if self._phase_state == "saved":
            return "saved" if not running else "saving"
        if not running:
            if returncode != 0:
                return "failed"
            # 退出码 0 却没有保存标记不算成功：最常见的原因就是在沿用提示处
            # 敲了裸回车，官方程序把旧参数写回电机就返回，什么都没测。
            return "finished_unsaved"
        return self._phase_state or "running"

    def status(self) -> dict[str, Any]:
        with self._lock:
            running = self._is_running()
            returncode = self._proc.poll() if self._proc is not None else None
            phase = self._phase(running, returncode)
            issues = diagnose_calibration_output(self._buffer, phase)
            return {
                "ok": True,
                "started": self._proc is not None,
                "running": running,
                "returncode": returncode,
                "robot_id": self._robot_id,
                "started_at": self._started_at,
                "command": list(self._command),
                "phase": phase,
                "prompt": self.prompt_for(phase),
                "had_calibration_file": self._had_calibration_file,
                "answers": list(self._answers),
                "issues": issues,
                "remedies": [issue_remedy(code) for code in issues],
                "output": self._buffer,
            }

    def confirm(self, answer: str = "") -> dict[str, Any]:
        with self._lock:
            if not self._is_running() or self._proc is None or self._proc.stdin is None:
                raise RuntimeError(_m("calibration_not_running"))
            self._proc.stdin.write(f"{answer}\n")
            self._proc.stdin.flush()
            self._answers.append(answer)
        return {"ok": True, "answer": answer}

    def abort(self) -> dict[str, Any]:
        with self._lock:
            if self._proc is None or not self._is_running():
                return {"ok": True, "message": _m("calibration_not_running")}
            self._proc.terminate()
            proc = self._proc
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return {"ok": True, "message": _m("calibration_aborted")}


CALIBRATION = CalibrationSession()


def build_test_export(robot_id: str) -> dict[str, Any]:
    """汇总这条臂的全部会话记录，供归档下载。"""

    validate_serial(robot_id)
    records = read_session_records(robot_id)
    by_action: dict[str, int] = {}
    for record in records:
        action = str(record.get("action", ""))
        by_action[action] = by_action.get(action, 0) + 1
    calibration_path = _calibration_file(robot_id)
    calibration: dict[str, Any] | None = None
    if calibration_path.is_file():
        try:
            calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            calibration = None
    return {
        "ok": True,
        "robot_id": robot_id,
        "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "teleop_type": "openarm_mini",
        "motors": OPENARM_MINI_MOTORS,
        "record_count": len(records),
        "records_by_action": by_action,
        "calibration_file": str(calibration_path) if calibration_path.is_file() else "",
        "calibration": calibration,
        "records": records,
    }


INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>OpenArm Mini</title>
<style>
  :root {
    --bg: #eef2f7; --card: #ffffff; --text: #1d2733; --muted: #5d6b7a;
    --line: #d6dee8; --accent: #1f6feb; --ok: #1a7f4b; --warn: #a15c00; --bad: #b3261e;
    --chip: #f1f5fa;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text);
    font: 15px/1.6 -apple-system, 'Noto Sans CJK SC', 'Segoe UI', 'Microsoft YaHei', sans-serif; }
  header { background: #16232f; color: #fff; padding: 18px 24px;
    display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap; }
  header .brand { flex: 1 1 320px; min-width: 0; }
  header h1 { margin: 0; font-size: 19px; }
  header p { margin: 4px 0 0; color: #9fb2c4; font-size: 13px; }
  .lang { display: flex; gap: 8px; align-items: center; flex: none; }
  .lang label { color: #9fb2c4; font-size: 12px; }
  .lang select { padding: 5px 8px; border-radius: 6px; border: 1px solid #38495a;
    background: #223140; color: #fff; font-size: 13px; }
  main { max-width: 1120px; margin: 0 auto; padding: 20px 16px 80px; }
  .stages { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px; }
  .stage { flex: 1 1 160px; padding: 8px 12px; border-radius: 8px; background: #dfe7f0;
    color: var(--muted); font-size: 13px; border: 1px solid transparent; }
  .stage.active { background: var(--accent); color: #fff; border-color: var(--accent); }
  .stage.done { background: #d8f0e2; color: var(--ok); border-color: #b6e0c8; }
  section { background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 18px 20px; margin-bottom: 16px; }
  section h2 { margin: 0 0 4px; font-size: 16px; }
  section .hint { margin: 0 0 14px; color: var(--muted); font-size: 13px; }
  .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end; margin-bottom: 12px; }
  .field { display: flex; flex-direction: column; gap: 4px; min-width: 190px; flex: 1 1 190px; }
  .field.tight { flex: 0 0 auto; min-width: 0; }
  .field label { font-size: 12px; color: var(--muted); }
  select, input { padding: 8px 10px; border: 1px solid var(--line); border-radius: 7px;
    background: #fff; color: var(--text); font-size: 14px; }
  button { padding: 8px 14px; border: 0; border-radius: 7px; background: var(--accent);
    color: #fff; font-size: 14px; cursor: pointer; }
  button.ghost { background: #e6ecf4; color: var(--text); }
  button:disabled { opacity: .45; cursor: not-allowed; }
  .steps { display: grid; gap: 10px; }
  .step { display: flex; gap: 12px; align-items: center; padding: 10px 12px;
    border: 1px solid var(--line); border-radius: 9px; }
  .step .num { width: 24px; height: 24px; border-radius: 50%; background: var(--chip);
    display: grid; place-items: center; font-size: 12px; color: var(--muted); flex: none; }
  .step.done .num { background: #d8f0e2; color: var(--ok); }
  .step .body { flex: 1; min-width: 0; }
  .step .body b { font-size: 14px; }
  .step .body p { margin: 2px 0 0; font-size: 12.5px; color: var(--muted); }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; margin: 10px 0; }
  .chip { padding: 4px 9px; border-radius: 20px; background: var(--chip); font-size: 12px;
    color: var(--muted); border: 1px solid var(--line); cursor: pointer; }
  .chip.current { background: var(--accent); color: #fff; border-color: var(--accent); }
  .chip.done { background: #d8f0e2; color: var(--ok); border-color: #b6e0c8; }
  .note { padding: 10px 12px; border-radius: 8px; font-size: 13px; margin: 10px 0; }
  .note.info { background: #eaf1fc; color: #1a4a91; }
  .note.warn { background: #fdf2e0; color: var(--warn); }
  .note.bad { background: #fdecea; color: var(--bad); }
  .note.ok { background: #e7f5ec; color: var(--ok); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); }
  th { color: var(--muted); font-weight: 600; font-size: 12px; }
  pre { background: #131b24; color: #d6e2ee; padding: 12px; border-radius: 8px;
    font-size: 12px; max-height: 320px; overflow: auto; white-space: pre-wrap; }
  .log { font-size: 12.5px; max-height: 220px; overflow: auto; }
  .log div { padding: 3px 0; border-bottom: 1px dashed var(--line); color: var(--muted); }
  code { background: var(--chip); padding: 1px 5px; border-radius: 4px; font-size: 12.5px; }
  label.inline { display: flex; gap: 6px; align-items: center; font-size: 12.5px;
    color: var(--muted); white-space: nowrap; padding-bottom: 8px; }
  .tag { display: inline-block; padding: 1px 7px; border-radius: 10px; font-size: 11px;
    margin-left: 6px; vertical-align: 1px; font-weight: 600; }
  .tag.official { background: #dde9fb; color: #1a4a91; }
  .tag.local { background: #ece6f7; color: #5b3a94; }
</style>
</head>
<body>
<header>
  <div class="brand">
    <h1 data-i18n="app_title"></h1>
    <p data-i18n-html="app_subtitle"></p>
  </div>
  <div class="lang">
    <label for="langSelect" data-i18n="lang_label"></label>
    <select id="langSelect">
      <option value="zh">中文</option>
      <option value="en">English</option>
      <option value="de">Deutsch</option>
    </select>
  </div>
</header>
<main>
  <div class="stages" id="stages"></div>

  <section>
    <h2 data-i18n="card_prep_title"></h2>
    <p class="hint" data-i18n="card_prep_hint"></p>
    <div class="row">
      <div class="field">
        <label data-i18n="f_side"></label>
        <select id="side">
          <option value="left" data-i18n="side_left"></option>
          <option value="right" data-i18n="side_right"></option>
        </select>
      </div>
      <div class="field">
        <label data-i18n="f_robot_id"></label>
        <input id="robotId" placeholder="OAML2026092801" />
      </div>
      <div class="field tight">
        <label>&nbsp;</label>
        <button class="ghost" id="suggestSerial" data-i18n="btn_suggest"></button>
      </div>
      <div class="field">
        <label data-i18n="f_profile"></label>
        <select id="profile"></select>
      </div>
    </div>
    <div class="row">
      <div class="field" style="flex:2 1 320px">
        <label data-i18n="f_port"></label>
        <select id="port"></select>
      </div>
      <div class="field tight">
        <label>&nbsp;</label>
        <button class="ghost" id="refreshPorts" data-i18n="btn_redetect"></button>
      </div>
      <div class="field tight">
        <label>&nbsp;</label>
        <button class="ghost" id="reconnectPort" data-i18n="btn_reconnect"></button>
      </div>
      <div class="field tight">
        <label class="inline">
          <input type="checkbox" id="showAllPorts" />
          <span data-i18n="port_show_all"></span>
        </label>
      </div>
    </div>
    <div id="portNote" class="note info"></div>
    <div id="supplyNote" class="note info"></div>
  </section>

  <section>
    <h2 data-i18n="card_ids_title"></h2>
    <p class="hint" data-i18n-html="card_ids_hint"></p>
    <div class="chips" id="motorChips"></div>
    <div class="note warn" data-i18n="single_motor_warn"></div>
    <div class="steps">
      <div class="step" id="stepScan">
        <div class="num">1</div>
        <div class="body">
          <b data-i18n="step_scan_title"></b><span class="tag official" data-i18n="tag_official"></span>
          <p data-i18n="step_scan_desc"></p>
          <p data-i18n="step_scan_broadcast_note"></p>
          <label class="inline" style="padding:4px 0 0">
            <input type="checkbox" id="deepScan" />
            <span data-i18n="deep_scan_label"></span>
          </label>
          <p data-i18n="deep_scan_hint"></p>
        </div>
        <button id="btnScan" data-i18n="btn_scan"></button>
      </div>
      <div class="step" id="stepWrite">
        <div class="num">2</div>
        <div class="body"><b data-i18n="step_write_title"></b><span class="tag official" data-i18n="tag_official"></span><p id="writeTarget"></p></div>
        <button id="btnWrite" data-i18n="btn_write" disabled></button>
      </div>
      <div class="step" id="stepRescan">
        <div class="num">3</div>
        <div class="body"><b data-i18n="step_rescan_title"></b><span class="tag local" data-i18n="tag_local"></span><p data-i18n="step_rescan_desc"></p></div>
        <button id="btnRescan" data-i18n="btn_rescan" disabled></button>
      </div>
      <div class="step" id="stepFeedback">
        <div class="num">4</div>
        <div class="body"><b data-i18n="step_feedback_title"></b><span class="tag local" data-i18n="tag_local"></span><p data-i18n="step_feedback_desc"></p></div>
        <button id="btnFeedback" disabled></button>
      </div>
    </div>
    <div id="motorResult"></div>
  </section>

  <section>
    <h2 data-i18n="card_scan_title"></h2><span class="tag local" data-i18n="tag_local"></span>
    <p class="hint" data-i18n="card_scan_hint"></p>
    <div class="row"><button id="btnScanAll" data-i18n="btn_scan_all"></button></div>
    <div id="scanAllResult"></div>
  </section>

  <section>
    <h2 data-i18n="card_calib_title"></h2>
    <p class="hint" data-i18n-html="card_calib_hint"></p>
    <div class="row">
      <button class="ghost" id="btnPrecheck" data-i18n="btn_precheck"></button>
      <button id="btnCalStart" data-i18n="btn_cal_start" disabled></button>
      <button class="ghost" id="btnCalAbort" data-i18n="btn_cal_abort" disabled></button>
      <button class="ghost" id="btnVerify" data-i18n="btn_verify"></button>
    </div>
    <p class="hint">
      <span data-i18n="btn_precheck"></span><span class="tag local" data-i18n="tag_local"></span>
      <span data-i18n="btn_cal_start"></span><span class="tag official" data-i18n="tag_official"></span>
      <span data-i18n="btn_verify"></span><span class="tag local" data-i18n="tag_local"></span>
    </p>
    <div id="calSource" class="hint"></div>
    <div id="precheckResult"></div>
    <div id="calPrompt"></div>
    <pre id="calOutput" hidden></pre>
    <div id="verifyResult"></div>
  </section>

  <section>
    <h2 data-i18n="card_export_title"></h2><span class="tag local" data-i18n="tag_local"></span>
    <p class="hint" data-i18n-html="card_export_hint"></p>
    <div class="row"><button id="btnExport" data-i18n="btn_export"></button></div>
    <div id="exportResult"></div>
  </section>

  <section>
    <h2 data-i18n="card_log_title"></h2>
    <div class="log" id="log"></div>
  </section>
</main>
<script>
const I18N = {
  zh: {
    lang_label: "语言",
    app_title: "OpenArm Mini 测试工作站",
    app_subtitle: "7 DOF + 夹爪 · 8× Feetech STS3215-C046 · LeRobot <code>openarm_mini</code> 遥操作臂",
    stage_prep: "1 准备", stage_ids: "2 写 ID 与质检", stage_scan: "3 八轴扫描",
    stage_calib: "4 校准与核对", stage_export: "5 导出归档",
    card_prep_title: "1 · 准备",
    card_prep_hint: "选左右臂、生成编号、确认供电档位和串口。后面每一步都靠这四项。",
    f_side: "臂侧", side_left: "左臂 Left", side_right: "右臂 Right",
    f_robot_id: "机械臂编号", btn_suggest: "推荐编号", f_profile: "供电档位", f_port: "串口",
    btn_redetect: "重新识别", btn_reconnect: "重连测试",
    port_show_all: "显示全部串口",
    port_placeholder_tag: "（内核占位，不是适配器）",
    port_manual_hint: "手动模式：列出全部 {total} 个串口节点，其中只有 {count} 个是 USB 适配器。",
    port_unplugged: "原先选中的 {port} 已经不在了，适配器可能被拔掉或重新枚举了。",
    supply_note: "本档位期望实测 <b>{expected}V</b>（限流 {limit}A）。扫描、写 ID 前工作站会读电机实际电压比对，偏差超过 1.0V 或超过额定 {rated}V 直接拒绝执行。工作站只记录档位，改不了实体电源——仍需人工核对红正黑负、OCP 关闭和 OUTPUT 状态。",
    card_ids_title: "2 · 逐颗写 ID 与只读质检",
    card_ids_hint: "官方 <code>setup_motors()</code> 从夹爪倒着走到肩部。<b>每次只连接一颗电机</b>，四步全部通过才进入下一颗。",
    single_motor_warn: "安全前提：写 ID 时总线上只能挂当前这一颗电机。多颗同时在线会一起被改成同一个 ID。",
    step_scan_title: "扫描当前电机", step_scan_desc: "确认只有一颗在线，并读出它现在的 ID 和波特率。",
    btn_scan: "扫描",
    btn_busy: "进行中… {sec}s",
    tag_official: "官方流程",
    tag_local: "本地质检",
    step_scan_broadcast_note: "与官方 _find_single_motor_p0() 同法：每档波特率发一个广播 ping，最坏 8 个包。广播会返回总线上所有应答，所以多接了电机能当场发现——官方只取第一个应答，发现不了。",
    deep_scan_label: "深度扫描",
    deep_scan_hint: "深度扫描 = 逐个试 ID（8 档 × 252 个，实测约 110 秒）。只在某颗电机确实不响应广播时勾选；这不是官方行为。",
    cal_source: "将启动：{exe}（来源：{source}）",
    step_write_title: "写入本步骤 ID 与 1000000 波特率",
    write_target: "目标：{title} → ID {id}，波特率 {baudrate}。",
    btn_write: "写入",
    step_rescan_title: "断电 5 秒后复扫",
    step_rescan_desc: "ID 和波特率在 EEPROM，断电复扫通过才算真的写进去了。",
    btn_rescan: "复扫",
    step_feedback_title: "只读反馈测试",
    step_feedback_desc: "测试期间用手来回摆动这一颗电机的输出轴。工作站全程不上扭矩。",
    btn_feedback: "开始（{sec} 秒）", btn_feedback_running: "读取中，请摆动关节…",
    card_scan_title: "3 · 八轴只读扫描",
    card_scan_hint: "恢复 1→8 菊花链、接 Waveshare 板并上电，读遍 8 颗电机的 ID、型号、位置、电压、温度与关键配置。",
    btn_scan_all: "开始八轴扫描",
    card_calib_title: "4 · 官方校准与一致性核对",
    card_calib_hint: "工作站不重写校准算法，只把官方 <code>lerobot-calibrate</code> 当子进程驱动，把它的每次确认映射成这里的按钮。",
    btn_precheck: "先做只读预检", btn_cal_start: "开始官方校准", btn_cal_abort: "中止",
    btn_verify: "一致性核对",
    card_export_title: "5 · 导出归档",
    card_export_hint: "每次扫描、写 ID、质检、预检、校准和核对都已落盘到 <code>test_reports/.sessions/</code>，这里导出本次测试的完整 JSON。",
    btn_export: "下载本次测试 JSON",
    card_log_title: "操作记录",
    col_joint: "关节", col_id: "ID", col_result: "结果", col_position: "位置",
    col_voltage: "电压", col_temperature: "温度", col_phase: "Phase", col_note: "说明",
    col_present: "当前位置", col_homing: "现中点偏移", col_encoder: "折算编码器",
    col_predicted: "预算新偏移",
    res_pass: "通过", res_fail: "失败", res_can_calibrate: "可校准", res_blocked: "拦截",
    res_consistent: "一致", res_inconsistent: "不一致",
    scan_all_summary: "八轴只读扫描：{passed}/{total} 通过。",
    precheck_summary: "预检 {passed}/{total} 通过。",
    verify_summary: "核对 {passed}/{total} 一致。校准文件：<code>{file}</code>",
    err_need_port: "请先选择串口。",
    err_need_serial: "请先填写或生成机械臂编号。",
    scan_already_id: "这颗电机的 ID 已经是 {id}。若是复扫，直接做反馈测试即可；若是新电机，请确认没有接错。",
    scan_voltage: "实测电压 {v}V。",
    rescan_ok: "断电复扫通过：ID {id} @ {baudrate}，电压 {v}V。",
    rescan_fail: "复扫失败：{error}<br/>如果这一步失败，说明设置没有写进 EEPROM，请重新执行第 2 步。",
    feedback_ok: "反馈正常：{samples} 次采样，行程跨度 {span} 计数（{min}–{max}），温度 {temp}℃。",
    feedback_wrap_note: "本次摆动跨过了编码器 0 点，属正常——驱动给 joint_1..joint_7 写死整圈量程。",
    cal_missing_exec: "未找到 <code>lerobot-calibrate</code>，第 4 步无法启动官方校准。请先在一个装有 openarm_mini 驱动的环境里安装 LeRobot。",
    cal_no_driver: "找到的 <code>{exe}</code> 所在环境<b>没有 openarm_mini 驱动</b>（它是较新版本才加入 LeRobot 的）。第 4 步会被拦下。请升级该环境的 LeRobot，或把工作站指向装有它的虚拟环境。",
    cal_unknown_support: "无法确认 <code>{exe}</code> 是否带 openarm_mini 驱动，第 4 步仍可尝试；若被 argparse 顶回来，看处置建议。",
    remedy_heading: "处置建议",
    cal_saved_note: "官方校准已完成并保存。请断电 5 秒后再做一次一致性核对。",
    cal_unsaved_note: "退出码 0，但没有出现保存标记——本次没有测量任何数据，不得当作合格。",
    cal_failed_note: "校准进程异常退出（returncode={code}）。",
    cal_running_note: "官方程序运行中…",
    export_done: "已导出 {count} 条记录。", export_with_file: "含校准文件 <code>{file}</code>。",
    export_no_file: "本次尚未生成校准文件。",
    log_ready: "工作站就绪。",
    log_port_detected: "已识别串口 {port}",
    log_port_none: "未检测到 USB 串口适配器",
    log_port_many: "检测到 {count} 个 USB 串口适配器，请手动选择",
    log_suggested: "推荐编号 {id}（已扫描 {count} 个在用编号）",
    log_scanned: "扫描到 ID={id} @ {baudrate}",
    log_rescanned: "复扫通过 ID={id}",
    log_feedback_ok: "{title} 反馈测试通过，跨度 {span}",
    log_feedback_bad: "反馈测试未通过：{reason}",
    log_scan_all: "八轴扫描 {passed}/{total}",
    log_precheck: "校准预检 {passed}/{total}",
    log_verify: "一致性核对 {passed}/{total}",
    log_cal_started: "已启动：{command}",
    log_cal_confirmed: "已确认：{title}",
    log_cal_saved: "校准已保存，自动执行一致性核对。",
    log_exported: "已导出 {count} 条记录",
  },
  en: {
    lang_label: "Language",
    app_title: "OpenArm Mini Test Workstation",
    app_subtitle: "7 DOF + gripper · 8× Feetech STS3215-C046 · LeRobot <code>openarm_mini</code> leader arm",
    stage_prep: "1 Prepare", stage_ids: "2 IDs and QC", stage_scan: "3 Eight-axis scan",
    stage_calib: "4 Calibrate and verify", stage_export: "5 Export",
    card_prep_title: "1 · Prepare",
    card_prep_hint: "Pick the arm side, generate a serial, confirm the supply profile and the port. Every later step relies on these four.",
    f_side: "Arm side", side_left: "Left arm", side_right: "Right arm",
    f_robot_id: "Arm serial", btn_suggest: "Suggest serial", f_profile: "Supply profile",
    f_port: "Serial port",
    btn_redetect: "Detect again", btn_reconnect: "Test reconnect",
    port_show_all: "Show all ports",
    port_placeholder_tag: "(kernel placeholder, not an adapter)",
    port_manual_hint: "Manual mode: all {total} serial nodes are listed, of which only {count} are USB adapters.",
    port_unplugged: "The previously selected {port} is gone — the adapter may have been unplugged or re-enumerated.",
    supply_note: "This profile expects a measured <b>{expected}V</b> (current limit {limit}A). Before every scan and ID write the workstation reads the actual motor voltage and compares: a deviation above 1.0V, or anything above the {rated}V rating, is refused outright. The workstation only records the profile — it cannot change the physical supply, so still check polarity, that OCP is off, and the OUTPUT state by hand.",
    card_ids_title: "2 · Write IDs and read-only QC",
    card_ids_hint: "The official <code>setup_motors()</code> walks backwards from the gripper to the shoulder. <b>Connect one motor at a time</b>; all four steps must pass before the next motor.",
    single_motor_warn: "Safety precondition: only the current motor may be on the bus while writing an ID. Several motors online at once all get the same ID.",
    step_scan_title: "Scan the connected motor",
    step_scan_desc: "Confirm only one motor is online and read its current ID and baud rate.",
    btn_scan: "Scan",
    btn_busy: "Working… {sec}s",
    tag_official: "official flow",
    tag_local: "local QC",
    step_scan_broadcast_note: "Same method as the official _find_single_motor_p0(): one broadcast ping per baud rate, 8 packets worst case. A broadcast returns every responder, so an extra connected motor shows up immediately — the official code takes the first answer and cannot see it.",
    deep_scan_label: "Deep scan",
    deep_scan_hint: "Deep scan probes IDs one by one (8 baud rates × 252 IDs, measured at about 110 seconds). Tick it only if a motor genuinely does not answer a broadcast; it is not official behaviour.",
    cal_source: "Will launch: {exe} (from {source})",
    step_write_title: "Write this step's ID and 1000000 baud",
    write_target: "Target: {title} → ID {id} at {baudrate} baud.",
    btn_write: "Write",
    step_rescan_title: "Power down 5 s, then rescan",
    step_rescan_desc: "ID and baud rate live in EEPROM; only a rescan after a power cycle proves they were really stored.",
    btn_rescan: "Rescan",
    step_feedback_title: "Read-only feedback test",
    step_feedback_desc: "Move this motor's output shaft back and forth by hand during the test. The workstation never enables torque.",
    btn_feedback: "Start ({sec} s)", btn_feedback_running: "Reading — move the joint…",
    card_scan_title: "3 · Eight-axis read-only scan",
    card_scan_hint: "Restore the 1→8 daisy chain, connect the Waveshare board and power up, then read ID, model, position, voltage, temperature and the key settings of all eight motors.",
    btn_scan_all: "Start eight-axis scan",
    card_calib_title: "4 · Official calibration and consistency check",
    card_calib_hint: "The workstation does not reimplement the calibration. It drives the official <code>lerobot-calibrate</code> as a child process and maps each of its confirmations onto a button here.",
    btn_precheck: "Run read-only precheck", btn_cal_start: "Start official calibration",
    btn_cal_abort: "Abort", btn_verify: "Consistency check",
    card_export_title: "5 · Export for the archive",
    card_export_hint: "Every scan, ID write, QC run, precheck, calibration and check is already on disk under <code>test_reports/.sessions/</code>; this exports the full JSON for this test.",
    btn_export: "Download this test as JSON",
    card_log_title: "Operation log",
    col_joint: "Joint", col_id: "ID", col_result: "Result", col_position: "Position",
    col_voltage: "Voltage", col_temperature: "Temp.", col_phase: "Phase", col_note: "Note",
    col_present: "Present position", col_homing: "Current homing offset",
    col_encoder: "Derived encoder", col_predicted: "Predicted new offset",
    res_pass: "pass", res_fail: "fail", res_can_calibrate: "ready", res_blocked: "blocked",
    res_consistent: "consistent", res_inconsistent: "inconsistent",
    scan_all_summary: "Eight-axis read-only scan: {passed}/{total} passed.",
    precheck_summary: "Precheck: {passed}/{total} passed.",
    verify_summary: "Check: {passed}/{total} consistent. Calibration file: <code>{file}</code>",
    err_need_port: "Select a serial port first.",
    err_need_serial: "Enter or generate an arm serial first.",
    scan_already_id: "This motor already has ID {id}. If this is a rescan, go straight to the feedback test; if it is a new motor, make sure it is the right one.",
    scan_voltage: "Measured {v}V.",
    rescan_ok: "Rescan after power cycle passed: ID {id} @ {baudrate}, {v}V.",
    rescan_fail: "Rescan failed: {error}<br/>A failure here means the settings never reached EEPROM. Run step 2 again.",
    feedback_ok: "Feedback is good: {samples} samples, travel span {span} counts ({min}–{max}), temperature {temp}°C.",
    feedback_wrap_note: "This sweep crossed encoder zero, which is normal — the driver hardcodes a full turn for joint_1..joint_7.",
    cal_missing_exec: "<code>lerobot-calibrate</code> was not found, so step 4 cannot start the official calibration. Install LeRobot in an environment that has the openarm_mini driver.",
    cal_no_driver: "The environment behind <code>{exe}</code> <b>has no openarm_mini driver</b> (it was only added to LeRobot in a newer version). Step 4 will be refused. Upgrade LeRobot there, or point the workstation at the virtualenv that has it.",
    cal_unknown_support: "Could not confirm whether <code>{exe}</code> carries the openarm_mini driver. Step 4 can still be attempted; if argparse refuses it, read the remedy.",
    remedy_heading: "Remedy",
    cal_saved_note: "The official calibration finished and was saved. Power down for 5 seconds, then run the consistency check once more.",
    cal_unsaved_note: "Exit code 0 but no saved marker appeared — nothing was measured in this run and it must not count as a pass.",
    cal_failed_note: "The calibration process exited abnormally (returncode={code}).",
    cal_running_note: "The official program is running…",
    export_done: "Exported {count} records.", export_with_file: "Includes calibration file <code>{file}</code>.",
    export_no_file: "No calibration file has been produced yet.",
    log_ready: "Workstation ready.",
    log_port_detected: "Detected serial port {port}",
    log_port_none: "No USB serial adapter detected",
    log_port_many: "{count} USB serial adapters detected — pick one manually",
    log_suggested: "Suggested serial {id} ({count} serials already in use)",
    log_scanned: "Found ID={id} @ {baudrate}",
    log_rescanned: "Rescan passed for ID={id}",
    log_feedback_ok: "{title} feedback test passed, span {span}",
    log_feedback_bad: "Feedback test failed: {reason}",
    log_scan_all: "Eight-axis scan {passed}/{total}",
    log_precheck: "Calibration precheck {passed}/{total}",
    log_verify: "Consistency check {passed}/{total}",
    log_cal_started: "Started: {command}",
    log_cal_confirmed: "Confirmed: {title}",
    log_cal_saved: "Calibration saved; running the consistency check automatically.",
    log_exported: "Exported {count} records",
  },
  de: {
    lang_label: "Sprache",
    app_title: "OpenArm Mini Prüfplatz",
    app_subtitle: "7 DOF + Greifer · 8× Feetech STS3215-C046 · LeRobot-<code>openarm_mini</code>-Führungsarm",
    stage_prep: "1 Vorbereiten", stage_ids: "2 IDs und Prüfung", stage_scan: "3 Scan aller acht Achsen",
    stage_calib: "4 Kalibrieren und abgleichen", stage_export: "5 Export",
    card_prep_title: "1 · Vorbereiten",
    card_prep_hint: "Armseite wählen, Seriennummer erzeugen, Versorgungsprofil und Port bestätigen. Alle weiteren Schritte bauen auf diesen vier auf.",
    f_side: "Armseite", side_left: "Linker Arm", side_right: "Rechter Arm",
    f_robot_id: "Arm-Seriennummer", btn_suggest: "Seriennummer vorschlagen",
    f_profile: "Versorgungsprofil", f_port: "Serieller Port",
    btn_redetect: "Erneut erkennen", btn_reconnect: "Verbindung testen",
    port_show_all: "Alle Ports anzeigen",
    port_placeholder_tag: "(Kernel-Platzhalter, kein Adapter)",
    port_manual_hint: "Manueller Modus: alle {total} seriellen Knoten werden aufgelistet, davon sind nur {count} USB-Adapter.",
    port_unplugged: "Der zuvor gewählte Port {port} ist nicht mehr vorhanden — der Adapter wurde möglicherweise abgezogen oder neu erkannt.",
    supply_note: "Dieses Profil erwartet gemessene <b>{expected}V</b> (Strombegrenzung {limit}A). Vor jedem Scan und jedem ID-Schreibvorgang liest der Prüfplatz die tatsächliche Motorspannung und vergleicht: eine Abweichung über 1,0V oder ein Wert über der Nennspannung von {rated}V wird direkt abgelehnt. Der Prüfplatz protokolliert nur das Profil und kann das Netzteil nicht ändern — Polarität, ausgeschaltete OCP und OUTPUT-Zustand bleiben manuell zu prüfen.",
    card_ids_title: "2 · IDs schreiben und Nur-Lese-Prüfung",
    card_ids_hint: "Das offizielle <code>setup_motors()</code> läuft vom Greifer rückwärts zur Schulter. <b>Immer nur einen Motor anschließen</b>; erst wenn alle vier Schritte bestanden sind, folgt der nächste Motor.",
    single_motor_warn: "Sicherheitsvoraussetzung: Beim Schreiben einer ID darf nur der aktuelle Motor am Bus hängen. Mehrere gleichzeitig angeschlossene Motoren erhalten alle dieselbe ID.",
    step_scan_title: "Angeschlossenen Motor scannen",
    step_scan_desc: "Bestätigen, dass nur ein Motor online ist, und dessen aktuelle ID und Baudrate lesen.",
    btn_scan: "Scannen",
    btn_busy: "Läuft… {sec}s",
    tag_official: "offizieller Ablauf",
    tag_local: "lokale Prüfung",
    step_scan_broadcast_note: "Dieselbe Methode wie das offizielle _find_single_motor_p0(): ein Broadcast-Ping pro Baudrate, im schlechtesten Fall 8 Pakete. Ein Broadcast liefert alle Antwortenden, ein zusätzlich angeschlossener Motor fällt daher sofort auf — der offizielle Code nimmt die erste Antwort und kann das nicht erkennen.",
    deep_scan_label: "Tiefenscan",
    deep_scan_hint: "Der Tiefenscan prüft die IDs einzeln (8 Baudraten × 252 IDs, gemessen etwa 110 Sekunden). Nur aktivieren, wenn ein Motor wirklich nicht auf einen Broadcast antwortet; das ist kein offizielles Verhalten.",
    cal_source: "Wird gestartet: {exe} (Quelle: {source})",
    step_write_title: "ID dieses Schritts und 1000000 Baud schreiben",
    write_target: "Ziel: {title} → ID {id} bei {baudrate} Baud.",
    btn_write: "Schreiben",
    step_rescan_title: "5 s ausschalten, dann erneut scannen",
    step_rescan_desc: "ID und Baudrate liegen im EEPROM; erst ein erneuter Scan nach dem Aus- und Einschalten beweist, dass sie wirklich gespeichert wurden.",
    btn_rescan: "Erneut scannen",
    step_feedback_title: "Nur-Lese-Rückmeldungstest",
    step_feedback_desc: "Die Abtriebsachse dieses Motors während des Tests von Hand hin und her bewegen. Der Prüfplatz aktiviert nie das Drehmoment.",
    btn_feedback: "Starten ({sec} s)", btn_feedback_running: "Wird gelesen — Gelenk bewegen…",
    card_scan_title: "3 · Nur-Lese-Scan aller acht Achsen",
    card_scan_hint: "Die Kette 1→8 wiederherstellen, das Waveshare-Board anschließen und einschalten, dann ID, Modell, Position, Spannung, Temperatur und die wichtigsten Einstellungen aller acht Motoren lesen.",
    btn_scan_all: "Scan aller acht Achsen starten",
    card_calib_title: "4 · Offizielle Kalibrierung und Abgleich",
    card_calib_hint: "Der Prüfplatz implementiert die Kalibrierung nicht neu. Er steuert das offizielle <code>lerobot-calibrate</code> als Unterprozess und bildet jede Bestätigung auf eine Schaltfläche hier ab.",
    btn_precheck: "Nur-Lese-Vorprüfung", btn_cal_start: "Offizielle Kalibrierung starten",
    btn_cal_abort: "Abbrechen", btn_verify: "Abgleich",
    card_export_title: "5 · Export für das Archiv",
    card_export_hint: "Jeder Scan, jedes ID-Schreiben, jede Prüfung, Vorprüfung, Kalibrierung und jeder Abgleich liegt bereits unter <code>test_reports/.sessions/</code>; hier wird das vollständige JSON dieses Tests exportiert.",
    btn_export: "Diesen Test als JSON herunterladen",
    card_log_title: "Protokoll",
    col_joint: "Gelenk", col_id: "ID", col_result: "Ergebnis", col_position: "Position",
    col_voltage: "Spannung", col_temperature: "Temp.", col_phase: "Phase", col_note: "Hinweis",
    col_present: "Aktuelle Position", col_homing: "Aktueller Offset",
    col_encoder: "Abgeleiteter Encoderwert", col_predicted: "Erwarteter neuer Offset",
    res_pass: "bestanden", res_fail: "fehlgeschlagen", res_can_calibrate: "bereit",
    res_blocked: "gesperrt", res_consistent: "übereinstimmend", res_inconsistent: "abweichend",
    scan_all_summary: "Nur-Lese-Scan aller acht Achsen: {passed}/{total} bestanden.",
    precheck_summary: "Vorprüfung: {passed}/{total} bestanden.",
    verify_summary: "Abgleich: {passed}/{total} übereinstimmend. Kalibrierdatei: <code>{file}</code>",
    err_need_port: "Zuerst einen seriellen Port wählen.",
    err_need_serial: "Zuerst eine Arm-Seriennummer eintragen oder erzeugen.",
    scan_already_id: "Dieser Motor hat bereits ID {id}. Bei einem erneuten Scan direkt zum Rückmeldungstest; bei einem neuen Motor prüfen, ob der richtige angeschlossen ist.",
    scan_voltage: "Gemessen {v}V.",
    rescan_ok: "Erneuter Scan nach Aus- und Einschalten bestanden: ID {id} @ {baudrate}, {v}V.",
    rescan_fail: "Erneuter Scan fehlgeschlagen: {error}<br/>Ein Fehler hier bedeutet, dass die Einstellungen nie im EEPROM angekommen sind. Schritt 2 erneut ausführen.",
    feedback_ok: "Rückmeldung in Ordnung: {samples} Messpunkte, Wegspanne {span} Zählschritte ({min}–{max}), Temperatur {temp}°C.",
    feedback_wrap_note: "Diese Bewegung hat den Encoder-Nullpunkt überschritten, das ist normal — der Treiber legt für joint_1..joint_7 eine ganze Umdrehung fest.",
    cal_missing_exec: "<code>lerobot-calibrate</code> wurde nicht gefunden, Schritt 4 kann die offizielle Kalibrierung nicht starten. LeRobot in einer Umgebung mit dem openarm_mini-Treiber installieren.",
    cal_no_driver: "Die Umgebung hinter <code>{exe}</code> <b>hat keinen openarm_mini-Treiber</b> (er wurde erst in einer neueren LeRobot-Version ergänzt). Schritt 4 wird abgelehnt. Dort LeRobot aktualisieren oder den Prüfplatz auf die passende virtuelle Umgebung verweisen.",
    cal_unknown_support: "Es ließ sich nicht feststellen, ob <code>{exe}</code> den openarm_mini-Treiber enthält. Schritt 4 kann trotzdem versucht werden; falls argparse ablehnt, den Hinweis lesen.",
    remedy_heading: "Empfohlenes Vorgehen",
    cal_saved_note: "Die offizielle Kalibrierung ist abgeschlossen und gespeichert. 5 Sekunden ausschalten und den Abgleich noch einmal ausführen.",
    cal_unsaved_note: "Exit-Code 0, aber keine Speicherbestätigung — in diesem Durchlauf wurde nichts gemessen, er darf nicht als bestanden gelten.",
    cal_failed_note: "Der Kalibriervorgang wurde unerwartet beendet (returncode={code}).",
    cal_running_note: "Das offizielle Programm läuft…",
    export_done: "{count} Datensätze exportiert.",
    export_with_file: "Enthält die Kalibrierdatei <code>{file}</code>.",
    export_no_file: "Es wurde noch keine Kalibrierdatei erzeugt.",
    log_ready: "Prüfplatz bereit.",
    log_port_detected: "Serieller Port {port} erkannt",
    log_port_none: "Kein USB-Seriell-Adapter erkannt",
    log_port_many: "{count} USB-Seriell-Adapter erkannt — bitte manuell wählen",
    log_suggested: "Vorgeschlagene Seriennummer {id} ({count} bereits belegt)",
    log_scanned: "ID={id} @ {baudrate} gefunden",
    log_rescanned: "Erneuter Scan für ID={id} bestanden",
    log_feedback_ok: "{title} Rückmeldungstest bestanden, Spanne {span}",
    log_feedback_bad: "Rückmeldungstest nicht bestanden: {reason}",
    log_scan_all: "Scan aller acht Achsen {passed}/{total}",
    log_precheck: "Kalibrier-Vorprüfung {passed}/{total}",
    log_verify: "Abgleich {passed}/{total}",
    log_cal_started: "Gestartet: {command}",
    log_cal_confirmed: "Bestätigt: {title}",
    log_cal_saved: "Kalibrierung gespeichert; Abgleich wird automatisch ausgeführt.",
    log_exported: "{count} Datensätze exportiert",
  },
};

const S = {
  lang: "zh", config: null, motors: {}, order: [], cursor: 0,
  step: { scanned: false, written: false, rescanned: false, tested: false },
  doneMotors: new Set(), scannedAll: false, precheckOk: false, verified: false,
  lastScan: null, calTimer: null, calSupport: undefined,
  detect: null, portSignature: "", portTimer: null,
};
const $ = (id) => document.getElementById(id);
const esc = (v) => String(v).replace(/[&<>]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const tr = (key) => (I18N[S.lang] || I18N.zh)[key] || I18N.zh[key] || key;
function tf(key, vars) {
  let text = tr(key);
  Object.entries(vars || {}).forEach(([k, v]) => { text = text.replaceAll('{' + k + '}', String(v)); });
  return text;
}

function log(text, kind) {
  const el = document.createElement('div');
  const locale = S.lang === 'zh' ? 'zh-CN' : S.lang === 'de' ? 'de-DE' : 'en-US';
  el.textContent = new Date().toLocaleTimeString(locale, { hour12: false }) + '  ' + text;
  if (kind === 'bad') el.style.color = 'var(--bad)';
  if (kind === 'ok') el.style.color = 'var(--ok)';
  $('log').prepend(el);
}
function note(target, kind, html) {
  $(target).innerHTML = '<div class="note ' + kind + '">' + html + '</div>';
}
async function api(path, body) {
  const url = body === undefined
    ? path + (path.includes('?') ? '&' : '?') + 'lang=' + S.lang
    : path;
  const options = body === undefined
    ? {}
    : { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.assign({ lang: S.lang }, body)) };
  const response = await fetch(url, options);
  const data = await response.json();
  if (!data.ok && data.error) throw new Error(data.error);
  return data;
}
const robotId = () => $('robotId').value.trim();
const port = () => $('port').value;
const profile = () => $('profile').value;
function requireBasics() {
  if (!port()) throw new Error(tr('err_need_port'));
  if (!robotId()) throw new Error(tr('err_need_serial'));
}
function currentMotor() { return S.order[S.cursor]; }

function applyLanguage(lang) {
  S.lang = lang;
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : lang;
  document.title = tr('app_title');
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = tr(el.dataset.i18n);
  });
  document.querySelectorAll('[data-i18n-html]').forEach((el) => {
    el.innerHTML = tr(el.dataset.i18nHtml);
  });
  $('btnFeedback').textContent = tf('btn_feedback', { sec: 8 });
  renderStages();
}

// 请求期间把按钮置灰并显示已耗时。默认的广播 ping 约 8 秒，勾了深度扫描约 110 秒；
// 没有这层，页面看起来就是卡死，而且连点会直接撞上「串口正忙」。
// 不改任何硬件路径，纯页面行为。
async function withBusy(id, run) {
  const button = $(id);
  const original = button.textContent;
  const started = Date.now();
  const tick = () => {
    button.textContent = tf('btn_busy', { sec: Math.round((Date.now() - started) / 1000) });
  };
  button.disabled = true;
  tick();
  const timer = setInterval(tick, 1000);
  try {
    await run();
  } finally {
    clearInterval(timer);
    button.textContent = original;
    // 分步按钮的可用性由 renderMotors() 按流程状态决定，这里只解除本次占用。
    button.disabled = false;
  }
}

function renderStages() {
  const stages = [
    ['stage_prep', !!port() && !!robotId()],
    ['stage_ids', S.doneMotors.size === S.order.length && S.order.length > 0],
    ['stage_scan', S.scannedAll],
    ['stage_calib', S.verified],
    ['stage_export', false],
  ];
  let active = stages.findIndex(([, done]) => !done);
  if (active < 0) active = stages.length - 1;
  $('stages').innerHTML = stages.map(([key, done], index) => {
    const cls = done ? 'stage done' : (index === active ? 'stage active' : 'stage');
    return '<div class="' + cls + '">' + esc(tr(key)) + '</div>';
  }).join('');
}

function renderMotors() {
  $('motorChips').innerHTML = S.order.map((name, index) => {
    const meta = S.motors[name];
    const cls = S.doneMotors.has(name) ? 'chip done' : (index === S.cursor ? 'chip current' : 'chip');
    return '<span class="' + cls + '" data-index="' + index + '">' +
      esc(meta.title) + ' (ID ' + meta.id + ')</span>';
  }).join('');
  document.querySelectorAll('#motorChips .chip').forEach((chip) => {
    chip.onclick = () => { S.cursor = Number(chip.dataset.index); resetSteps(); renderMotors(); };
  });
  const meta = S.motors[currentMotor()];
  $('writeTarget').textContent = meta
    ? tf('write_target', { title: meta.title, id: meta.id, baudrate: S.config.default_baudrate })
    : '';
  for (const [id, key] of [['stepScan','scanned'],['stepWrite','written'],['stepRescan','rescanned'],['stepFeedback','tested']]) {
    $(id).classList.toggle('done', S.step[key]);
  }
  $('btnWrite').disabled = !S.step.scanned;
  $('btnRescan').disabled = !S.step.written;
  $('btnFeedback').disabled = !S.step.rescanned;
  renderStages();
}
function resetSteps() {
  S.step = { scanned: false, written: false, rescanned: false, tested: false };
  $('motorResult').innerHTML = '';
}

function renderTable(rows, columns) {
  const head = '<tr>' + columns.map((c) => '<th>' + esc(tr(c[0])) + '</th>').join('') + '</tr>';
  const body = rows.map((row) => '<tr>' + columns.map((c) => '<td>' + esc(c[1](row)) + '</td>').join('') + '</tr>').join('');
  return '<table>' + head + body + '</table>';
}

async function loadConfig() {
  const data = await api('/api/config');
  S.config = data;
  S.motors = data.motors;
  S.order = data.setup_order;
  const keep = $('profile').value;
  $('profile').innerHTML = Object.entries(data.hardware_profiles).map(
    ([key, p]) => '<option value="' + key + '">' + esc(p.label) + ' — ' + esc(p.usage) +
      ' (' + p.test_supply_voltage_v + 'V / ' + p.test_current_limit_a + 'A)</option>'
  ).join('');
  if (keep) $('profile').value = keep;
  S.calSupport = data.calibration;
  updateSupplyNote();
  renderMotors();
  renderCalSupport();
}
function renderCalSupport() {
  const cal = S.calSupport;
  if (!cal) return;
  $('calSource').innerHTML = cal.available
    ? esc(tf('cal_source', { exe: cal.executable, source: cal.source }))
    : '';
  if (cal.resolve_error) {
    note('calPrompt', 'bad', esc(cal.resolve_error));
    return;
  }
  if (!cal.available) {
    note('calPrompt', 'warn', tr('cal_missing_exec'));
  } else if (cal.openarm_mini_supported === false) {
    note('calPrompt', 'bad', tf('cal_no_driver', { exe: esc(cal.executable) }));
  } else if (cal.openarm_mini_supported === null) {
    note('calPrompt', 'warn', tf('cal_unknown_support', { exe: esc(cal.executable) }));
  }
}
function updateSupplyNote() {
  const p = S.config.hardware_profiles[profile()];
  if (!p) return;
  $('supplyNote').innerHTML = tf('supply_note', {
    expected: p.test_supply_voltage_v, limit: p.test_current_limit_a,
    rated: p.motor_rated_voltage_v,
  });
}
// 自动识别串口。本机有 32 个 /dev/ttyS* 内核占位节点，只有 1 个是适配器，
// 让操作员在 33 条里挑是选错串口的主要来源。
async function detectPorts(options) {
  const opts = options || {};
  const data = await api('/api/detect-port');
  S.detect = data;
  const manual = $('showAllPorts').checked;
  const signature = manual + '|' + data.status + '|' +
    data.candidates.map((p) => p.device).join(',');
  // 轮询时候选没变就不重建下拉框——操作员正展开着它会被打断。
  if (signature === S.portSignature && !opts.force) return;
  const previous = $('port').value;
  S.portSignature = signature;

  const list = manual ? data.ports : data.candidates;
  $('port').innerHTML = list.map((p) => {
    const tag = p.is_adapter ? '' : ' ' + tr('port_placeholder_tag');
    return '<option value="' + p.device + '">' + p.device + ' — ' +
      esc(p.description) + esc(tag) + '</option>';
  }).join('');

  const stillThere = list.some((p) => p.device === previous);
  if (stillThere) {
    $('port').value = previous;
  } else if (!manual && data.status === 'one') {
    $('port').value = data.port;
  }

  const blocks = [];
  const kind = data.status === 'one' ? 'ok' : (data.status === 'none' ? 'warn' : 'info');
  blocks.push('<div class="note ' + kind + '">' + esc(data.message) + '</div>');
  if (previous && !stillThere && data.status !== 'none') {
    blocks.push('<div class="note warn">' + esc(tf('port_unplugged', { port: previous })) + '</div>');
  }
  (data.warnings || []).forEach((w) => {
    blocks.push('<div class="note bad">' + esc(w) + '</div>');
  });
  if (manual) {
    blocks.push('<div class="note info">' + esc(tf('port_manual_hint', {
      total: data.total, count: data.candidates.length })) + '</div>');
  }
  $('portNote').innerHTML = blocks.join('');

  if (!opts.silent) {
    if (data.status === 'one') log(tf('log_port_detected', { port: data.port }), 'ok');
    else if (data.status === 'none') log(tr('log_port_none'), 'bad');
    else log(tf('log_port_many', { count: data.candidates.length }));
  }
  renderStages();
}

$('langSelect').onchange = async () => {
  applyLanguage($('langSelect').value);
  // 关节名、档位文案和识别结果都由服务端按语言渲染，换语言要重新取一次。
  try { await loadConfig(); await detectPorts({ force: true, silent: true }); }
  catch (e) { log(e.message, 'bad'); }
};
$('refreshPorts').onclick = () => detectPorts({ force: true }).catch((e) => log(e.message, 'bad'));
$('showAllPorts').onchange = () => detectPorts({ force: true }).catch((e) => log(e.message, 'bad'));
$('profile').onchange = updateSupplyNote;
$('side').onchange = () => { $('robotId').value = ''; renderStages(); };
$('robotId').oninput = renderStages;
$('suggestSerial').onclick = () => withBusy('suggestSerial', async () => {
  try {
    const data = await api('/api/next-serial?side=' + encodeURIComponent($('side').value));
    $('robotId').value = data.robot_id;
    log(tf('log_suggested', { id: data.robot_id, count: data.known_count }), 'ok');
    renderStages();
  } catch (e) { log(e.message, 'bad'); }
});
$('reconnectPort').onclick = () => withBusy('reconnectPort', async () => {
  try {
    const data = await api('/api/reconnect-port', { port: port() });
    log(data.message, 'ok');
  } catch (e) { log(e.message, 'bad'); }
});

$('btnScan').onclick = () => withBusy('btnScan', async () => {
  try {
    requireBasics();
    const data = await api('/api/scan-current', { port: port(), hardware_profile: profile(),
      robot_id: robotId(), deep_scan: $('deepScan').checked });
    S.lastScan = data;
    S.step.scanned = true;
    const expected = S.motors[currentMotor()];
    let kind = 'ok', extra = '';
    if (data.detected.id === expected.id) {
      kind = 'info';
      extra = '<br/>' + tf('scan_already_id', { id: expected.id });
    }
    note('motorResult', kind, esc(data.message) + '<br/>' +
      tf('scan_voltage', { v: data.voltage_v }) + extra);
    log(tf('log_scanned', { id: data.detected.id, baudrate: data.detected.baudrate }), 'ok');
  } catch (e) { note('motorResult', 'bad', esc(e.message)); log(e.message, 'bad'); }
  renderMotors();
});
$('btnWrite').onclick = () => withBusy('btnWrite', async () => {
  try {
    requireBasics();
    const data = await api('/api/init-id', {
      port: port(), motor: currentMotor(), hardware_profile: profile(), robot_id: robotId(),
      initial_baudrate: S.lastScan ? S.lastScan.detected.baudrate : null,
      initial_id: S.lastScan ? S.lastScan.detected.id : null,
    });
    S.step.written = true;
    note('motorResult', 'ok', esc(data.message));
    log(data.message, 'ok');
  } catch (e) { note('motorResult', 'bad', esc(e.message)); log(e.message, 'bad'); }
  renderMotors();
});
$('btnRescan').onclick = () => withBusy('btnRescan', async () => {
  try {
    requireBasics();
    const expected = S.motors[currentMotor()];
    const data = await api('/api/scan-current', {
      port: port(), hardware_profile: profile(), robot_id: robotId(),
      initial_baudrate: S.config.default_baudrate, initial_id: expected.id,
    });
    S.step.rescanned = true;
    note('motorResult', 'ok', tf('rescan_ok', {
      id: data.detected.id, baudrate: data.detected.baudrate, v: data.voltage_v }));
    log(tf('log_rescanned', { id: data.detected.id }), 'ok');
  } catch (e) {
    note('motorResult', 'bad', tf('rescan_fail', { error: esc(e.message) }));
    log(e.message, 'bad');
  }
  renderMotors();
});
$('btnFeedback').onclick = async () => {
  const button = $('btnFeedback');
  button.disabled = true; button.textContent = tr('btn_feedback_running');
  try {
    requireBasics();
    const data = await api('/api/feedback-test', {
      port: port(), motor: currentMotor(), robot_id: robotId(), duration_sec: 8,
    });
    if (data.ok) {
      S.step.tested = true;
      S.doneMotors.add(currentMotor());
      note('motorResult', 'ok', tf('feedback_ok', {
        samples: data.samples, span: data.span, min: data.observed_min,
        max: data.observed_max, temp: data.temperature_c,
      }) + (data.wraps_encoder_zero ? '<br/>' + tr('feedback_wrap_note') : ''));
      log(tf('log_feedback_ok', { title: S.motors[currentMotor()].title, span: data.span }), 'ok');
      const next = S.order.findIndex((name) => !S.doneMotors.has(name));
      if (next >= 0) { S.cursor = next; resetSteps(); }
    } else {
      note('motorResult', 'bad', esc(data.reason));
      log(tf('log_feedback_bad', { reason: data.reason }), 'bad');
    }
  } catch (e) { note('motorResult', 'bad', esc(e.message)); log(e.message, 'bad'); }
  button.textContent = tf('btn_feedback', { sec: 8 });
  renderMotors();
};

$('btnScanAll').onclick = () => withBusy('btnScanAll', async () => {
  try {
    requireBasics();
    const data = await api('/api/scan-all', { port: port(), robot_id: robotId() });
    S.scannedAll = data.overall_ok;
    const table = renderTable(data.results, [
      ['col_joint', (r) => r.motor_title || r.motor_name],
      ['col_id', (r) => r.motor_id],
      ['col_result', (r) => (r.ok ? tr('res_pass') : tr('res_fail'))],
      ['col_position', (r) => (r.ok ? r.present_position : '-')],
      ['col_voltage', (r) => (r.ok ? r.voltage_v + 'V' : '-')],
      ['col_temperature', (r) => (r.ok ? r.temperature_c + '°C' : '-')],
      ['col_phase', (r) => (r.ok ? r.phase : '-')],
      ['col_note', (r) => r.reason || ''],
    ]);
    $('scanAllResult').innerHTML = '<div class="note ' + (data.overall_ok ? 'ok' : 'bad') + '">' +
      esc(tf('scan_all_summary', { passed: data.passed, total: data.total })) + '</div>' + table;
    log(tf('log_scan_all', { passed: data.passed, total: data.total }), data.overall_ok ? 'ok' : 'bad');
  } catch (e) { note('scanAllResult', 'bad', esc(e.message)); log(e.message, 'bad'); }
  renderStages();
});

$('btnPrecheck').onclick = () => withBusy('btnPrecheck', async () => {
  try {
    requireBasics();
    const data = await api('/api/calibration/precheck', { port: port(), robot_id: robotId() });
    S.precheckOk = data.overall_ok;
    $('btnCalStart').disabled = !data.overall_ok;
    const table = renderTable(data.results, [
      ['col_joint', (r) => r.motor_title || r.motor_name],
      ['col_present', (r) => (r.present_position === undefined ? '-' : r.present_position)],
      ['col_homing', (r) => (r.homing_offset === undefined ? '-' : r.homing_offset)],
      ['col_encoder', (r) => (r.encoder_position === undefined ? '-' : r.encoder_position)],
      ['col_predicted', (r) => (r.predicted_homing_offset === undefined ? '-' : r.predicted_homing_offset)],
      ['col_result', (r) => (r.ok ? tr('res_can_calibrate') : tr('res_blocked'))],
      ['col_note', (r) => r.reason || ''],
    ]);
    $('precheckResult').innerHTML = '<div class="note ' + (data.overall_ok ? 'ok' : 'bad') + '">' +
      esc(tf('precheck_summary', { passed: data.passed, total: data.total })) + ' ' +
      esc(data.note) + '</div>' + table;
    log(tf('log_precheck', { passed: data.passed, total: data.total }), data.overall_ok ? 'ok' : 'bad');
  } catch (e) { note('precheckResult', 'bad', esc(e.message)); log(e.message, 'bad'); }
});
$('btnCalStart').onclick = () => withBusy('btnCalStart', async () => {
  try {
    requireBasics();
    const data = await api('/api/calibration/start', { port: port(), robot_id: robotId() });
    log(tf('log_cal_started', { command: data.command.join(' ') }), 'ok');
    $('calOutput').hidden = false;
    pollCalibration();
  } catch (e) { note('calPrompt', 'bad', esc(e.message)); log(e.message, 'bad'); }
});
$('btnCalAbort').onclick = async () => {
  try {
    const data = await api('/api/calibration/abort', { robot_id: robotId() });
    log(data.message, 'bad');
  } catch (e) { log(e.message, 'bad'); }
};
function pollCalibration() {
  if (S.calTimer) clearInterval(S.calTimer);
  S.calTimer = setInterval(async () => {
    try {
      const status = await api('/api/calibration/status');
      $('calOutput').textContent = status.output;
      $('calOutput').hidden = !status.started;
      $('btnCalAbort').disabled = !status.running;
      renderCalPrompt(status);
      if (!status.running && status.started) {
        clearInterval(S.calTimer); S.calTimer = null;
        if (status.phase === 'saved') {
          log(tr('log_cal_saved'), 'ok');
          $('btnVerify').click();
        }
      }
    } catch (e) { log(e.message, 'bad'); }
  }, 900);
}
function renderCalPrompt(status) {
  const blocks = [];
  if (status.remedies && status.remedies.length) {
    blocks.push('<div class="note bad"><b>' + esc(tr('remedy_heading')) + '</b><br/>' +
      status.remedies.map(esc).join('<br/>') + '</div>');
  }
  if (status.prompt) {
    blocks.push('<div class="note info"><b>' + esc(status.prompt.title) + '</b><br/>' +
      esc(status.prompt.detail) + '<br/><br/><button id="btnCalConfirm">' +
      esc(status.prompt.action) + '</button></div>');
  } else if (status.phase === 'saved') {
    blocks.push('<div class="note ok">' + esc(tr('cal_saved_note')) + '</div>');
  } else if (status.phase === 'finished_unsaved') {
    blocks.push('<div class="note bad">' + esc(tr('cal_unsaved_note')) + '</div>');
  } else if (status.phase === 'failed') {
    blocks.push('<div class="note bad">' +
      esc(tf('cal_failed_note', { code: status.returncode })) + '</div>');
  } else if (status.running) {
    blocks.push('<div class="note info">' + esc(tr('cal_running_note')) + '</div>');
  }
  $('calPrompt').innerHTML = blocks.join('');
  const confirmButton = $('btnCalConfirm');
  if (confirmButton) {
    confirmButton.onclick = async () => {
      confirmButton.disabled = true;
      try {
        await api('/api/calibration/confirm', { answer: status.prompt.answer, robot_id: robotId() });
        log(tf('log_cal_confirmed', { title: status.prompt.title }), 'ok');
      } catch (e) { log(e.message, 'bad'); }
    };
  }
}
$('btnVerify').onclick = () => withBusy('btnVerify', async () => {
  try {
    requireBasics();
    const data = await api('/api/verify-calibration', { port: port(), robot_id: robotId() });
    S.verified = data.overall_ok;
    const table = renderTable(data.results, [
      ['col_joint', (r) => r.motor_title || r.motor_name],
      ['col_id', (r) => r.motor_id],
      ['col_result', (r) => (r.ok ? tr('res_consistent') : tr('res_inconsistent'))],
      ['col_note', (r) => r.reason || ''],
    ]);
    $('verifyResult').innerHTML = '<div class="note ' + (data.overall_ok ? 'ok' : 'bad') + '">' +
      tf('verify_summary', { passed: data.passed, total: data.total,
        file: esc(data.calibration_file) }) + '</div>' + table;
    log(tf('log_verify', { passed: data.passed, total: data.total }), data.overall_ok ? 'ok' : 'bad');
  } catch (e) { note('verifyResult', 'bad', esc(e.message)); log(e.message, 'bad'); }
  renderStages();
});

$('btnExport').onclick = () => withBusy('btnExport', async () => {
  try {
    if (!robotId()) throw new Error(tr('err_need_serial'));
    const data = await api('/api/export?robot_id=' + encodeURIComponent(robotId()));
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = robotId() + '_openarm_mini_test.json';
    link.click();
    URL.revokeObjectURL(link.href);
    note('exportResult', 'ok', esc(tf('export_done', { count: data.record_count })) + ' ' +
      (data.calibration_file
        ? tf('export_with_file', { file: esc(data.calibration_file) })
        : esc(tr('export_no_file'))));
    log(tf('log_exported', { count: data.record_count }), 'ok');
  } catch (e) { note('exportResult', 'bad', esc(e.message)); log(e.message, 'bad'); }
});

applyLanguage($('langSelect').value);
loadConfig()
  .then(() => detectPorts({ force: true }))
  .then(() => log(tr('log_ready')))
  .catch((e) => log(e.message, 'bad'));
// 适配器插上或拔掉后不必点任何按钮，页面自己跟上。
S.portTimer = setInterval(() => {
  detectPorts({ silent: true }).catch(() => { /* 后端暂时不可达，下一轮再试 */ });
}, 3000);
setInterval(async () => {
  try {
    const status = await api('/api/calibration/status');
    if (status.running && !S.calTimer) pollCalibration();
  } catch (e) { /* 页面刚打开时后端还没就绪，忽略 */ }
}, 4000);
</script>
</body>
</html>
"""


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, data: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _html(self, html: str, status: int = HTTPStatus.OK) -> None:
        payload = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        set_language((query.get("lang") or [""])[0].strip())

        if parsed.path in ("/", "/index.html"):
            self._html(INDEX_HTML)
            return
        if parsed.path == "/api/ports":
            self._json({"ok": True, "ports": list_serial_ports()})
            return
        if parsed.path == "/api/detect-port":
            self._json(detect_serial_port())
            return
        if parsed.path == "/api/calibration/status":
            self._json(CALIBRATION.status())
            return
        if parsed.path == "/api/config":
            resolution: dict[str, Any] = {}
            resolve_error = ""
            try:
                resolution = resolve_lerobot_calibrate()
            except RuntimeError as exc:
                resolve_error = str(exc)
            executable = resolution.get("path") or None
            self._json(
                {
                    "ok": True,
                    "language": get_language(),
                    "languages": list(LANGUAGES),
                    "motors": {
                        name: {**meta, "label": motor_label(name), "title": motor_title(name)}
                        for name, meta in OPENARM_MINI_MOTORS.items()
                    },
                    "setup_order": MINI_SETUP_ORDER,
                    "hardware_profiles": {
                        key: {
                            **{k: v for k, v in profile.items() if not k.endswith("_key")},
                            "label": _m(profile["label_key"]),
                            "usage": _m(profile["usage_key"]),
                        }
                        for key, profile in MINI_HARDWARE_PROFILES.items()
                    },
                    "default_baudrate": DEFAULT_BAUDRATE,
                    "serial_rule": {
                        "pattern": MINI_SERIAL_PATTERN.pattern,
                        "hint": serial_hint(),
                    },
                    "feedback_profile": {
                        "default_seconds": FEEDBACK_DEFAULT_SECONDS,
                        "movement_counts": FEEDBACK_MOVEMENT_COUNTS,
                        "read_only": True,
                    },
                    "upstream_reference": {
                        "hardware": "https://github.com/pkooij/open-arms-mini",
                        "driver": "lerobot/teleoperators/openarm_mini",
                        "teleop_type": "openarm_mini",
                    },
                    "calibration": {
                        "executable": executable or "lerobot-calibrate",
                        "available": executable is not None,
                        "source": resolution.get("source", ""),
                        "resolve_error": resolve_error,
                        "env_var": LEROBOT_ENV_VAR,
                        "openarm_mini_supported": (
                            lerobot_supports_openarm_mini(executable)
                            if executable is not None
                            else False
                        ),
                        "flags": [
                            "--teleop.type=openarm_mini",
                            "--teleop.port={port}",
                            "--teleop.id={robot_id}",
                        ],
                        "calibration_dir": str(_calibration_dir()),
                    },
                }
            )
            return
        if parsed.path == "/api/next-serial":
            side = (query.get("side") or ["left"])[0].strip()
            try:
                self._json({"ok": True, **suggest_serial(side)})
            except Exception as exc:  # noqa: BLE001
                self._json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/export":
            robot_id = (query.get("robot_id") or [""])[0].strip()
            try:
                self._json(build_test_export(robot_id))
            except Exception as exc:  # noqa: BLE001
                self._json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        self._json({"ok": False, "error": "Not found."}, status=HTTPStatus.NOT_FOUND)

    # 路由到领域操作。每一项都会记进会话日志——包括失败，
    # 因为归档最需要解释的恰恰是失败的那几次。
    def _dispatch(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        port = str(payload.get("port", "")).strip()
        motor = str(payload.get("motor", "")).strip()
        baud_raw = payload.get("initial_baudrate")
        initial_baudrate = int(baud_raw) if baud_raw not in (None, "") else None
        id_raw = payload.get("initial_id")
        initial_id = int(id_raw) if id_raw not in (None, "") else None
        hardware_profile = str(payload.get("hardware_profile", "")).strip()
        robot_id = str(payload.get("robot_id", "")).strip()
        deep_scan = bool(payload.get("deep_scan", False))

        if path == "/api/calibration/confirm":
            return CALIBRATION.confirm(str(payload.get("answer", "")).strip())
        if path == "/api/calibration/abort":
            return CALIBRATION.abort()

        if path == "/api/calibration/start":
            return CALIBRATION.start(port, robot_id)

        if not port:
            raise ValueError(_m("need_port"))

        if path == "/api/scan-current":
            return scan_current_motor(
                port, initial_baudrate, initial_id, hardware_profile, deep_scan
            )
        if path == "/api/init-id":
            return initialize_motor_id(
                port, motor, initial_baudrate, initial_id, hardware_profile, deep_scan
            )
        if path == "/api/feedback-test":
            duration = float(payload.get("duration_sec", FEEDBACK_DEFAULT_SECONDS))
            return feedback_test(port, motor, duration)
        if path == "/api/scan-all":
            return scan_all_motors_read_only(port)
        if path == "/api/motor-params":
            return get_motor_params(port, motor)
        if path == "/api/reconnect-port":
            return reconnect_port(port)
        if path == "/api/calibration/precheck":
            return precheck_calibration_poses(port)
        if path == "/api/verify-calibration":
            return verify_calibration_and_config(port, robot_id)
        raise ValueError(_m("unknown_endpoint", path=path))

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        known = {
            "/api/scan-current",
            "/api/init-id",
            "/api/feedback-test",
            "/api/scan-all",
            "/api/motor-params",
            "/api/reconnect-port",
            "/api/calibration/precheck",
            "/api/calibration/start",
            "/api/calibration/confirm",
            "/api/calibration/abort",
            "/api/verify-calibration",
        }
        if path not in known:
            self._json({"ok": False, "error": "Not found."}, status=HTTPStatus.NOT_FOUND)
            return

        payload: dict[str, Any] = {}
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length)
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            set_language(str(payload.get("lang", "")).strip())
            result = self._dispatch(path, payload)
        except Exception as exc:  # noqa: BLE001
            error = {"ok": False, "error": str(exc)}
            append_session_record(
                str(payload.get("robot_id", "")).strip(),
                path.removeprefix("/api/"),
                {"request": payload, "error": str(exc)},
            )
            self._json(error, status=HTTPStatus.BAD_REQUEST)
            return

        append_session_record(
            str(payload.get("robot_id", "")).strip(),
            path.removeprefix("/api/"),
            {"request": payload, "result": result},
        )
        self._json(result)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenArm Mini 测试工作站")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=8788, help="监听端口，默认 8788")
    parser.add_argument(
        "--lerobot-calibrate",
        default="",
        help=(
            "官方 lerobot-calibrate 可执行文件路径。"
            f"也可用环境变量 {LEROBOT_ENV_VAR}。"
            "不指定时按「项目内 .venv-lerobot / .venv → PATH → 共享 venv 目录」查找。"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_lerobot_calibrate_override(args.lerobot_calibrate)
    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"OpenArm Mini 测试工作站: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
