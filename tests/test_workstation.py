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

    def test_bench_profile_accepts_its_own_supply(self) -> None:
        self.assertTrue(main.check_supply_voltage("mini_bench_5v", 5.1)["checked"])

    def test_field_profile_accepts_official_7v5(self) -> None:
        # BOM 给的是 7.5V 电源，电机额定 7.4V——这一档必须放行。
        self.assertTrue(main.check_supply_voltage("mini_field_7v5", 7.5)["checked"])

    def test_over_rated_voltage_is_refused(self) -> None:
        with self.assertRaises(RuntimeError):
            main.check_supply_voltage("mini_field_7v5", 12.0)

    def test_wrong_profile_for_the_measured_supply_is_refused(self) -> None:
        with self.assertRaises(RuntimeError):
            main.check_supply_voltage("mini_bench_5v", 7.5)


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
