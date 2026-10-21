"""纯函数单测。硬件行为在真机上按验收门验证，这里只锁住可离线判定的规则。"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import main  # noqa: E402
import messages  # noqa: E402


class MotorTableTest(unittest.TestCase):
    def test_ids_match_official_motor_table(self) -> None:
        # 官方 README「Motor IDs」：1..8 依次对应 J1..J8。
        expected = {
            "joint_1": (1, "J1"),
            "joint_2": (2, "J2"),
            "joint_3": (3, "J3"),
            "joint_4": (4, "J4"),
            "joint_5": (5, "J5"),
            "joint_6": (6, "J6"),
            "joint_7": (7, "J7"),
            "gripper": (8, "J8"),
        }
        actual = {k: (v["id"], v["part"]) for k, v in main.OPENARM_MINI_MOTORS.items()}
        self.assertEqual(actual, expected)

    def test_setup_order_is_reverse_of_driver_motor_order(self) -> None:
        # 官方 setup_motors() 用 reversed(self.bus.motors)，即 ID 从大到小。
        ids = [main.OPENARM_MINI_MOTORS[name]["id"] for name in main.MINI_SETUP_ORDER]
        self.assertEqual(ids, [8, 7, 6, 5, 4, 3, 2, 1])

    def test_setup_order_covers_every_motor(self) -> None:
        self.assertEqual(set(main.MINI_SETUP_ORDER), set(main.OPENARM_MINI_MOTORS))


class DecodingTest(unittest.TestCase):
    def test_homing_offset_uses_sign_bit_11(self) -> None:
        self.assertEqual(main._decode_homing_offset(0x0801), -1)
        self.assertEqual(main._decode_homing_offset(1), 1)
        self.assertEqual(main._decode_homing_offset(0x0FFF), -2047)

    def test_position_uses_sign_bit_15(self) -> None:
        # 略低于零的位置读成 33017 而不是 -249 的那个坑。
        self.assertEqual(main._decode_position(33017), -249)
        self.assertEqual(main._decode_position(2047), 2047)

    def test_unwrap_recovers_travel_across_the_seam(self) -> None:
        samples = [4000, 4090, 10, 100, 10, 4090, 4000]
        unwrapped = main._unwrap_positions(samples)
        self.assertEqual(max(unwrapped) - min(unwrapped), 196)

    def test_analyse_travel_flags_seam_crossing_without_inflating_span(self) -> None:
        result = main.analyse_travel([4000, 4090, 10, 100])
        self.assertTrue(result["wraps_encoder_zero"])
        self.assertEqual(result["span"], 196)
        self.assertFalse(result["over_full_turn"])

    def test_analyse_travel_reports_no_movement(self) -> None:
        result = main.analyse_travel([2000, 2001, 2000, 1999])
        self.assertFalse(result["moved"])


class SupplyVoltageTest(unittest.TestCase):
    def test_unknown_profile_is_not_a_check(self) -> None:
        self.assertFalse(main.check_supply_voltage("", 5.0)["checked"])

    def test_only_the_official_7v5_profile_exists(self) -> None:
        # 测试站只测装配好的整臂，电源按官方 BOM 一律 7.5V。
        self.assertEqual(list(main.MINI_HARDWARE_PROFILES), ["mini_field_7v5"])

    def test_field_profile_accepts_official_7v5(self) -> None:
        # BOM 给的是 7.5V 电源，电机额定 7.4V——这一档必须放行。
        self.assertTrue(main.check_supply_voltage("mini_field_7v5", 7.5)["checked"])

    def test_over_rated_voltage_is_refused(self) -> None:
        with self.assertRaises(RuntimeError):
            main.check_supply_voltage("mini_field_7v5", 12.0)

    def test_a_5v_adapter_on_the_7v5_profile_is_refused(self) -> None:
        # 接错成 5V 适配器时，电机在低压下读数不可信，不能放行。
        with self.assertRaises(RuntimeError):
            main.check_supply_voltage("mini_field_7v5", 5.0)


class SerialRuleTest(unittest.TestCase):
    def test_valid_serial(self) -> None:
        match = main.validate_serial("OAML2026092801")
        self.assertEqual(match.group(1), "L")

    def test_hint_is_part_of_the_malformed_serial_message(self) -> None:
        # 只说「格式不合规」而不给格式，操作员没法自己改对。
        with self.assertRaises(ValueError) as caught:
            main.validate_serial("BAD")
        self.assertIn(main.serial_hint(), str(caught.exception))

    def test_malformed_serial_is_refused(self) -> None:
        for bad in ("SOL20260928101", "OAMX2026092801", "OAML202609280", "oaml2026092801"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                main.validate_serial(bad)

    def test_suggest_serial_skips_used_numbers(self) -> None:
        used = {"OAML2026092801", "OAML2026092802"}
        original = main.collect_known_serials
        main.collect_known_serials = lambda: used  # type: ignore[assignment]
        try:
            result = main.suggest_serial("left", date(2026, 9, 28))
        finally:
            main.collect_known_serials = original  # type: ignore[assignment]
        self.assertEqual(result["robot_id"], "OAML2026092803")

    def test_suggest_serial_rejects_unknown_side(self) -> None:
        with self.assertRaises(ValueError):
            main.suggest_serial("middle")


class CalibrationPhaseTest(unittest.TestCase):
    """提示串逐条引自 LeRobot 上游 openarm_mini.py。

    上游改了措辞时这里先红，而不是在现场静默地匹配不到任何阶段。
    """

    TRANSCRIPT = [
        (
            "Press ENTER to use existing calibration for OAML2026092801, "
            "or type 'c' and press ENTER to run new calibration: ",
            "await_existing",
        ),
        (
            "\nCalibration: Zero Position\nPosition the arm in the following configuration:\n"
            "  - Arm hanging straight down\n  - Gripper closed\nPress ENTER when ready...",
            "await_zero",
        ),
        (
            "\nGripper Calibration\nStep 1: CLOSE the gripper fully\n"
            "Press ENTER when gripper is closed...",
            "await_gripper_closed",
        ),
        (
            "\nStep 2: OPEN the gripper fully\nPress ENTER when gripper is fully open...",
            "await_gripper_open",
        ),
        (
            "\nCalibration complete and saved to "
            "/home/u/.cache/huggingface/lerobot/calibration/teleoperators/openarm_mini/x.json",
            "saved",
        ),
    ]

    def _phase_of(self, chunk: str) -> str:
        for phase, needle in main.CalibrationSession.PHASE_PATTERNS:
            if needle in chunk:
                return phase
        return ""

    def test_every_official_prompt_maps_to_a_phase(self) -> None:
        for chunk, expected in self.TRANSCRIPT:
            with self.subTest(expected=expected):
                self.assertEqual(self._phase_of(chunk), expected)

    def test_every_waiting_phase_has_an_operator_prompt(self) -> None:
        waiting = [p for p, _ in main.CalibrationSession.PHASE_PATTERNS if p.startswith("await_")]
        for phase in waiting:
            with self.subTest(phase=phase):
                self.assertIn(phase, main.CalibrationSession.PHASE_PROMPTS)

    def test_only_the_existing_file_prompt_answers_c(self) -> None:
        # 在沿用提示处敲裸回车会让官方程序什么都不测就退出，
        # 随后的一致性核对拿电机和同一个旧文件比，会给出 8/8 的假合格。
        prompts = main.CalibrationSession.PHASE_PROMPTS
        self.assertEqual(prompts["await_existing"][1], "c")
        for phase, (_prefix, answer) in prompts.items():
            if phase != "await_existing":
                self.assertEqual(answer, "")

    def test_prompt_for_renders_all_three_fields(self) -> None:
        for phase in main.CalibrationSession.PHASE_PROMPTS:
            with self.subTest(phase=phase):
                prompt = main.CalibrationSession.prompt_for(phase)
                assert prompt is not None
                for field in ("title", "detail", "action"):
                    # 渲染不出来时 m() 回落成键名，那样现场会看到 prompt_zero_title。
                    self.assertFalse(prompt[field].startswith("prompt_"), prompt[field])

    def test_prompt_for_returns_none_outside_the_waiting_phases(self) -> None:
        self.assertIsNone(main.CalibrationSession.prompt_for("saved"))


class DiagnosisTest(unittest.TestCase):
    def test_offset_overflow_is_named(self) -> None:
        output = "ValueError: Magnitude 2729 exceeds 2047 (max for sign_bit_index=11)"
        self.assertIn("offset_overflow", main.diagnose_calibration_output(output, "failed"))

    def test_reused_existing_file_is_named_and_not_double_reported(self) -> None:
        output = "Using existing calibration for OAML2026092801"
        codes = main.diagnose_calibration_output(output, "finished_unsaved")
        self.assertEqual(codes, ["reused_existing"])

    def test_exit_zero_without_saving_is_never_silent(self) -> None:
        self.assertIn("finished_unsaved", main.diagnose_calibration_output("", "finished_unsaved"))

    def test_every_issue_code_has_a_remedy(self) -> None:
        codes = {code for code, _ in main.CALIBRATION_ISSUE_SIGNATURES} | {"finished_unsaved"}
        self.assertEqual(codes, set(main.CALIBRATION_ISSUE_CODES))
        for code in codes:
            with self.subTest(code=code):
                self.assertIn("remedy_" + code, messages.MESSAGES)
                # 缺文案时 m() 回落键名，现场就会读到 remedy_motor_mismatch。
                self.assertNotEqual(main.issue_remedy(code), "remedy_" + code)


class CalibrationPathTest(unittest.TestCase):
    def test_path_matches_lerobot_teleoperator_cache_layout(self) -> None:
        path = main._calibration_file("OAMR2026092801")
        self.assertTrue(
            str(path).endswith(
                ".cache/huggingface/lerobot/calibration/teleoperators/openarm_mini/OAMR2026092801.json"
            ),
            path,
        )


class DriverConstantsTest(unittest.TestCase):
    def test_joint_range_is_the_driver_hardcoded_full_turn(self) -> None:
        # openarm_mini.calibrate()：非夹爪关节 range_min=0, range_max=resolution-1。
        self.assertEqual((main.MINI_JOINT_RANGE_MIN, main.MINI_JOINT_RANGE_MAX), (0, 4095))

    def test_half_turn_matches_lerobot(self) -> None:
        self.assertEqual(main.HALF_TURN, 2047)

    def test_expected_phase_clears_the_angle_feedback_bit(self) -> None:
        # calibrate() 给全部电机写 Phase=12；configure_motors() 要求清掉 bit4(0x10)。
        self.assertEqual(
            main.PHASE_EXPECTED_AFTER_CALIBRATION & main.PHASE_ANGLE_FEEDBACK_BIT, 0
        )


if __name__ == "__main__":
    unittest.main()


class TeleopSupportTest(unittest.TestCase):
    """本机很可能装着老版 LeRobot，那里 --teleop.type 没有 openarm_mini 这个选项。"""

    def test_unknown_teleop_type_is_named_and_has_a_remedy(self) -> None:
        # 实测 LeRobot 0.4.4 的输出。
        output = (
            "lerobot-calibrate: error: argument --teleop.type: invalid choice: 'openarm_mini' "
            "(choose from 'openarm_leader', 'so101_leader', 'unitree_g1')"
        )
        codes = main.diagnose_calibration_output(output, "failed")
        self.assertIn("teleop_type_unknown", codes)
        self.assertIn("teleop_type_unknown", main.CALIBRATION_ISSUE_CODES)

    def test_probe_returns_none_for_a_non_executable(self) -> None:
        self.assertIsNone(main.lerobot_supports_openarm_mini("/nonexistent/lerobot-calibrate"))

    def test_probe_detects_this_interpreter_lacking_the_driver(self) -> None:
        # 用当前解释器冒充一个控制台脚本：它没装 lerobot，应判为不支持。
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix="-calibrate", delete=False) as handle:
            handle.write(f"#!{sys.executable}\n")
            script = handle.name
        try:
            self.assertFalse(main.lerobot_supports_openarm_mini(script))
        finally:
            Path(script).unlink()


class FakePortInfo:
    """pyserial ListPortInfo 里本工作站用到的那几个字段。"""

    def __init__(self, device, description="n/a", vid=None, pid=None, serial_number=None):
        self.device = device
        self.name = device.rsplit("/", 1)[-1]
        self.description = description
        self.vid = vid
        self.pid = pid
        self.serial_number = serial_number
        self.product = description if vid else None
        self.hwid = (
            f"USB VID:PID={vid:04X}:{pid:04X} SER={serial_number}" if vid else "n/a"
        )


GHOSTS = [FakePortInfo(f"/dev/ttyS{i}") for i in range(32)]
# 实测的 Waveshare 板：WCH CH343，udev 建了 by-id 别名
ADAPTER = FakePortInfo(
    "/dev/ttyACM0", "USB Single Serial", vid=0x1A86, pid=0x55D3, serial_number="5B14032307"
)
ADAPTER_ALIAS = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B14032307-if00"
SECOND = FakePortInfo(
    "/dev/ttyACM1", "USB Single Serial", vid=0x1A86, pid=0x55D3, serial_number="5B14032308"
)
SECOND_ALIAS = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B14032308-if00"


class PortDetectionTest(unittest.TestCase):
    """自动识别串口。

    本机有 32 个 /dev/ttyS* 内核占位节点，只有 1 个是真适配器；
    让操作员在 33 条里挑，是选错串口的主要来源。
    """

    def setUp(self) -> None:
        self._comports = main.list_ports.comports
        self._aliases = main._stable_port_aliases
        self._access = main.os.access
        main.os.access = lambda path, mode: True  # type: ignore[assignment]

    def tearDown(self) -> None:
        main.list_ports.comports = self._comports  # type: ignore[assignment]
        main._stable_port_aliases = self._aliases  # type: ignore[assignment]
        main.os.access = self._access  # type: ignore[assignment]

    def _given(self, infos, aliases=None):
        main.list_ports.comports = lambda: list(infos)  # type: ignore[assignment]
        main._stable_port_aliases = lambda: dict(aliases or {})  # type: ignore[assignment]

    def test_kernel_placeholders_are_not_adapters(self) -> None:
        for ghost in GHOSTS[:3]:
            with self.subTest(device=ghost.device):
                self.assertFalse(main._is_usb_adapter(ghost, ""))

    def test_usb_identity_makes_an_adapter(self) -> None:
        self.assertTrue(main._is_usb_adapter(ADAPTER, ""))

    def test_by_id_alias_makes_an_adapter(self) -> None:
        # 别名只对 USB 串口存在，所以它本身就是充分判据。
        bare = FakePortInfo("/dev/ttyACM9")
        self.assertTrue(main._is_usb_adapter(bare, "/dev/serial/by-id/whatever"))

    def test_single_adapter_is_selected_automatically(self) -> None:
        self._given(GHOSTS + [ADAPTER], {"/dev/ttyACM0": ADAPTER_ALIAS})
        result = main.detect_serial_port()
        self.assertEqual(result["status"], "one")
        # 给出的必须是稳定别名：内核名每次重新枚举都会变。
        self.assertEqual(result["port"], ADAPTER_ALIAS)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["total"], 33)

    def test_no_adapter_reports_none_and_picks_nothing(self) -> None:
        self._given(GHOSTS)
        result = main.detect_serial_port()
        self.assertEqual(result["status"], "none")
        self.assertEqual(result["port"], "")
        self.assertEqual(result["candidates"], [])

    def test_two_adapters_are_never_guessed(self) -> None:
        # 一个工位同时插着左右两条臂的适配器是正常状态；猜错会把 ID 写到另一条臂上。
        self._given(
            GHOSTS + [ADAPTER, SECOND],
            {"/dev/ttyACM0": ADAPTER_ALIAS, "/dev/ttyACM1": SECOND_ALIAS},
        )
        result = main.detect_serial_port()
        self.assertEqual(result["status"], "many")
        self.assertEqual(result["port"], "")
        self.assertEqual(len(result["candidates"]), 2)

    def test_adapters_sort_before_the_placeholders(self) -> None:
        self._given(GHOSTS + [ADAPTER], {"/dev/ttyACM0": ADAPTER_ALIAS})
        ports = main.detect_serial_port()["ports"]
        self.assertTrue(ports[0]["is_adapter"])
        self.assertFalse(ports[-1]["is_adapter"])

    def test_unwritable_adapter_is_warned_about(self) -> None:
        # 权限不足时 openPort() 会抛异常；提前说比等它失败有用。
        main.os.access = lambda path, mode: False  # type: ignore[assignment]
        self._given(GHOSTS + [ADAPTER], {"/dev/ttyACM0": ADAPTER_ALIAS})
        result = main.detect_serial_port()
        self.assertEqual(result["status"], "one")
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("dialout", result["warnings"][0])

    def test_message_follows_the_language(self) -> None:
        self._given(GHOSTS + [ADAPTER], {"/dev/ttyACM0": ADAPTER_ALIAS})
        messages.set_language("de")
        try:
            self.assertIn("automatisch erkannt", main.detect_serial_port()["message"])
        finally:
            messages.set_language(messages.DEFAULT_LANGUAGE)


class CalibrationRootTest(unittest.TestCase):
    """校准目录必须跟 LeRobot 走同一套环境变量。

    写死 ~/.cache 会让工作站在错误的目录里找文件——给一台已经校准的臂报
    「未找到校准文件」，或者拿一份过期文件去核对并报出 8/8 合格。
    优先级抄自 LeRobot utils/constants.py。
    """

    ENV_KEYS = ("HF_LEROBOT_CALIBRATION", "HF_LEROBOT_HOME", "HF_HOME", "XDG_CACHE_HOME")

    def setUp(self) -> None:
        self._saved = {k: main.os.environ.get(k) for k in self.ENV_KEYS}
        for k in self.ENV_KEYS:
            main.os.environ.pop(k, None)

    def tearDown(self) -> None:
        for k, v in self._saved.items():
            if v is None:
                main.os.environ.pop(k, None)
            else:
                main.os.environ[k] = v

    def test_default_is_the_huggingface_cache(self) -> None:
        self.assertEqual(
            main._calibration_root(),
            Path.home() / ".cache/huggingface/lerobot/calibration",
        )

    def test_xdg_cache_home_is_honoured(self) -> None:
        # huggingface_hub 的 HF_HOME 默认就是 $XDG_CACHE_HOME/huggingface。
        main.os.environ["XDG_CACHE_HOME"] = "/cache"
        self.assertEqual(
            main._calibration_root(), Path("/cache/huggingface/lerobot/calibration")
        )

    def test_hf_home_is_honoured(self) -> None:
        main.os.environ["HF_HOME"] = "/data/hf"
        self.assertEqual(main._calibration_root(), Path("/data/hf/lerobot/calibration"))

    def test_lerobot_home_beats_hf_home(self) -> None:
        main.os.environ["HF_HOME"] = "/data/hf"
        main.os.environ["HF_LEROBOT_HOME"] = "/data/lr"
        self.assertEqual(main._calibration_root(), Path("/data/lr/calibration"))

    def test_explicit_calibration_dir_wins(self) -> None:
        main.os.environ["HF_HOME"] = "/data/hf"
        main.os.environ["HF_LEROBOT_HOME"] = "/data/lr"
        main.os.environ["HF_LEROBOT_CALIBRATION"] = "/data/cal"
        self.assertEqual(main._calibration_root(), Path("/data/cal"))

    def test_teleoperator_subdirectory_matches_lerobot_layout(self) -> None:
        # Teleoperator 基类：HF_LEROBOT_CALIBRATION / "teleoperators" / self.name
        main.os.environ["HF_LEROBOT_CALIBRATION"] = "/data/cal"
        self.assertEqual(
            main._calibration_dir(), Path("/data/cal/teleoperators/openarm_mini")
        )


class LerobotResolutionTest(unittest.TestCase):
    """决定启动哪个 lerobot-calibrate。

    共享目录 ~/Projects/.venvs 被 SO-ARM101 工作站用 sorted(glob(...)) 扫描并取
    第一个匹配。在那里新建 venv 会按字母序悄悄改变**它**选中的 LeRobot，
    所以本工作站优先用项目内的 venv，并支持显式指定。
    """

    def setUp(self) -> None:
        self._env = main.os.environ.get(main.LEROBOT_ENV_VAR)
        main.os.environ.pop(main.LEROBOT_ENV_VAR, None)
        main.set_lerobot_calibrate_override(None)

    def tearDown(self) -> None:
        main.set_lerobot_calibrate_override(None)
        if self._env is None:
            main.os.environ.pop(main.LEROBOT_ENV_VAR, None)
        else:
            main.os.environ[main.LEROBOT_ENV_VAR] = self._env

    def test_cli_override_wins_over_everything(self) -> None:
        main.os.environ[main.LEROBOT_ENV_VAR] = "/bin/echo"
        main.set_lerobot_calibrate_override("/bin/true")
        result = main.resolve_lerobot_calibrate()
        self.assertEqual(result["path"], "/bin/true")
        self.assertEqual(result["source"], "--lerobot-calibrate")

    def test_env_var_is_honoured(self) -> None:
        main.os.environ[main.LEROBOT_ENV_VAR] = "/bin/echo"
        result = main.resolve_lerobot_calibrate()
        self.assertEqual(result["path"], "/bin/echo")
        self.assertEqual(result["source"], main.LEROBOT_ENV_VAR)

    def test_invalid_override_raises_instead_of_falling_back(self) -> None:
        # 路径打错却静默回退到另一个 LeRobot，正是这个参数要防的事。
        main.set_lerobot_calibrate_override("/nope/lerobot-calibrate")
        with self.assertRaises(RuntimeError) as caught:
            main.resolve_lerobot_calibrate()
        self.assertIn("/nope/lerobot-calibrate", str(caught.exception))

    def test_find_returns_none_for_an_invalid_override(self) -> None:
        main.set_lerobot_calibrate_override("/nope/lerobot-calibrate")
        self.assertIsNone(main.find_lerobot_calibrate())

    def test_project_local_venv_is_preferred_over_the_shared_directory(self) -> None:
        self.assertEqual(main.PROJECT_LEROBOT_VENVS[0], ".venv-lerobot")
        self.assertIn(".venv", main.PROJECT_LEROBOT_VENVS)

    def test_shared_directory_source_says_it_is_shared(self) -> None:
        # 现场看到「共享目录」才知道这个 LeRobot 不是本项目专有的。
        result = main.resolve_lerobot_calibrate()
        if result["source"]:
            self.assertTrue(isinstance(result["source"], str))


class FakePacketHandler:
    def __init__(self, responders):
        self.responders = responders
        self.tx_calls = 0

    def txPacket(self, port_handler, txpacket):  # noqa: N802
        self.tx_calls += 1
        port_handler.queue_responses(self.responders)
        return 0  # COMM_SUCCESS


class FakePortHandler:
    """够用的假串口：只支撑广播 ping 的收发时序。"""

    def __init__(self):
        self.buffer: list[int] = []
        self.is_using = False
        self.baudrate = 1_000_000

    def getBaudRate(self):  # noqa: N802
        return self.baudrate

    def setPacketTimeoutMillis(self, ms):  # noqa: N802
        pass

    def isPacketTimeout(self):  # noqa: N802
        return not self.buffer

    def readPort(self, length):  # noqa: N802
        chunk, self.buffer = self.buffer[:length], self.buffer[length:]
        return chunk

    def queue_responses(self, ids):
        for motor_id in ids:
            # 状态包：FF FF <id> <length> <error> <checksum>
            body = [motor_id, 2, 0]
            checksum = ~sum(body) & 0xFF
            self.buffer += [0xFF, 0xFF, *body, checksum]


class BroadcastPingTest(unittest.TestCase):
    """广播 ping 的解包，按 LeRobot 的状态包格式。

    官方 _find_single_motor_p0() 每档波特率只发一个广播包；早先这里是
    8 档 × 252 个 ID 逐个试，实测空跑 105 秒，那不是官方行为。
    """

    def _client(self, responders):
        client = main.FeetechSdkClient.__new__(main.FeetechSdkClient)
        client.scs = _FakeScs()
        client.port_handler = FakePortHandler()
        client.packet_handler = FakePacketHandler(responders)
        return client

    def test_single_responder_is_parsed(self) -> None:
        client = self._client([6])
        self.assertEqual(client.broadcast_ping(), {6: 0})

    def test_every_responder_is_returned(self) -> None:
        # 这是比官方严的关键：多接了电机能当场发现。
        client = self._client([1, 6, 8])
        self.assertEqual(sorted(client.broadcast_ping()), [1, 6, 8])

    def test_silence_returns_empty(self) -> None:
        client = self._client([])
        self.assertEqual(client.broadcast_ping(), {})

    def test_one_packet_per_call(self) -> None:
        client = self._client([3])
        client.broadcast_ping()
        self.assertEqual(client.packet_handler.tx_calls, 1)


class _FakeScs:
    COMM_SUCCESS = 0
    MAX_ID = 252
    BROADCAST_ID = 254
    PKT_ID = 2
    PKT_LENGTH = 3
    PKT_INSTRUCTION = 4
    PKT_ERROR = 4
    INST_PING = 1


class PrecheckPoseTest(unittest.TestCase):
    """校准前的单关节判据。

    2026-09-29 现场回归：一个摆在零位的关节被报成
    「折算编码器读数 -1497 超出单圈 0..4095，属多圈累计读数」并拦停。
    原因是算 actual 时漏了取模——编码器是模 4096 的，扣掉一个已有的中点偏移
    完全可能落到 0..4095 之外，那描述的是正常姿态。漏了取模会拦下每一条
    已经校准过的臂。
    """

    def test_negative_wrap_is_a_normal_pose(self) -> None:
        # 现场那一例：present 550 + homing -2047 = -1497，在 4096 的轮子上是 2599。
        verdict = main.evaluate_precheck_pose(present=550, homing=-2047)
        self.assertEqual(verdict["encoder_position"], 2599)
        self.assertTrue(verdict["ok"], verdict["reason"])
        self.assertEqual(verdict["reason"], "")

    def test_archived_gripper_case_from_the_so101_bench(self) -> None:
        # 2026-09-17 归档：夹爪 present 699、homing -1845，-1146 就是 2950。
        verdict = main.evaluate_precheck_pose(present=699, homing=-1845)
        self.assertEqual(verdict["encoder_position"], 2950)
        self.assertTrue(verdict["ok"])

    def test_positive_wrap_is_also_normal(self) -> None:
        verdict = main.evaluate_precheck_pose(present=3000, homing=2000)
        self.assertEqual(verdict["encoder_position"], (3000 + 2000) % 4096)
        self.assertTrue(verdict["ok"])

    def test_multi_turn_reading_is_blocked(self) -> None:
        # SOL20260814101 在 ID4 读到 4776，官方校准中止；断电后恢复到 680。
        verdict = main.evaluate_precheck_pose(present=4776, homing=0)
        self.assertFalse(verdict["ok"])
        self.assertIn("4776", verdict["reason"])

    def test_offset_overflow_is_reachable_at_the_top_of_the_turn(self) -> None:
        # actual == 4095 → 偏移 2048，装不进 11 位寄存器，官方会报
        # "Magnitude 2048 exceeds 2047"。所以这条检查是可达的，不是纯防御。
        verdict = main.evaluate_precheck_pose(present=4095, homing=0)
        self.assertEqual(verdict["predicted_homing_offset"], 2048)
        self.assertFalse(verdict["ok"])
        self.assertIn("2048", verdict["reason"])

    def test_bottom_of_the_turn_is_allowed(self) -> None:
        # actual == 0 → 偏移 -2047，正好在寄存器能装下的边界上。
        verdict = main.evaluate_precheck_pose(present=0, homing=0)
        self.assertEqual(verdict["predicted_homing_offset"], -2047)
        self.assertTrue(verdict["ok"])

    def test_predicted_offset_matches_the_official_formula(self) -> None:
        # feetech._get_half_turn_homings(): homing = pos - int((4096-1)/2)
        for present in (0, 137, 2047, 2048, 4095):
            with self.subTest(present=present):
                verdict = main.evaluate_precheck_pose(present=present, homing=0)
                self.assertEqual(verdict["predicted_homing_offset"], present - 2047)

    def test_every_single_turn_pose_is_allowed_except_the_very_top(self) -> None:
        # 取模之后唯一会被偏移检查拦下的就是 4095。
        blocked = [
            p for p in range(main.ENCODER_RESOLUTION)
            if not main.evaluate_precheck_pose(present=p, homing=0)["ok"]
        ]
        self.assertEqual(blocked, [4095])


class DriverGenerationTest(unittest.TestCase):
    """openarm_mini 有两代互不兼容的设计，必须分辨。

    2026-09-29 现场：装上 PyPI 0.4.4 后探测报「支持」，点开始校准却退出码 1，
    draccus 报 `The fields \\`port\\` are not valid for OpenArmMiniConfig`。
    已发布的那代是双臂版（port_right / port_left），官方硬件 README 写的单臂
    形式（--teleop.port）只有上游 main 才有。只判模块存在是不够的。
    """

    def test_exit_codes_cover_the_three_verdicts(self) -> None:
        self.assertEqual(
            main._PROBE_EXIT_CODES,
            {0: main.PROBE_SINGLE_ARM, 3: main.PROBE_MISSING, 4: main.PROBE_DUAL_ARM},
        )

    def test_probe_source_decides_by_config_field(self) -> None:
        # 判据必须是配置里有没有 port 字段，不是模块存不存在。
        self.assertIn("OpenArmMiniConfig", main._PROBE_SOURCE)
        self.assertIn("'port' in names", main._PROBE_SOURCE)

    def test_only_the_single_arm_generation_counts_as_supported(self) -> None:
        original = main.probe_openarm_mini_driver
        try:
            for verdict, expected in (
                (main.PROBE_SINGLE_ARM, True),
                (main.PROBE_DUAL_ARM, False),
                (main.PROBE_MISSING, False),
                (None, None),
            ):
                with self.subTest(verdict=verdict):
                    main.probe_openarm_mini_driver = lambda _p, v=verdict: v  # type: ignore[assignment]
                    self.assertIs(main.lerobot_supports_openarm_mini("/x"), expected)
        finally:
            main.probe_openarm_mini_driver = original  # type: ignore[assignment]

    def test_dual_arm_has_its_own_message(self) -> None:
        # 笼统报「没有驱动」会让人去重装一个装了也不行的东西。
        self.assertIn("calibrate_dual_arm_generation", messages.MESSAGES)
        for lang in messages.LANGUAGES:
            messages.set_language(lang)
            text = messages.m("calibrate_dual_arm_generation", executable="/x")
            with self.subTest(lang=lang):
                self.assertIn("port_right", text)
                self.assertIn("/x", text)
        messages.set_language(messages.DEFAULT_LANGUAGE)

    def test_probe_of_a_real_environment_returns_a_known_verdict(self) -> None:
        exe = Path(main._project_root()) / ".venv-lerobot" / "bin" / "lerobot-calibrate"
        if not exe.is_file():
            self.skipTest("本机没有 .venv-lerobot")
        self.assertIn(
            main.probe_openarm_mini_driver(str(exe)),
            {main.PROBE_SINGLE_ARM, main.PROBE_DUAL_ARM, main.PROBE_MISSING},
        )
