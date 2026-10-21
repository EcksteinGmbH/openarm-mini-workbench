"""出厂测试流程：判据函数、放行门、检查表与归档。

放行门只看会话日志，所以这里直接造日志记录来钉规则；硬件行为在真机验收。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import criteria as crit  # noqa: E402
import gate  # noqa: E402
import main  # noqa: E402
import messages  # noqa: E402

MOTORS = main.OPENARM_MINI_MOTORS


def snapshot(name: str, **overrides):
    row = {
        "ok": True,
        "motor_name": name,
        "voltage_v": 7.4,
        "temperature_c": 28,
        "status_raw": 0,
        "torque_enable": 0,
        "firmware": "3.10",
    }
    row.update(overrides)
    return row


class ArmScanCriteriaTest(unittest.TestCase):
    def good(self):
        return [snapshot(name) for name in MOTORS]

    def test_healthy_arm_passes(self) -> None:
        result = crit.evaluate_arm_scan(self.good(), 7.5)
        self.assertTrue(result["judged_ok"])

    def test_hot_motor_fails(self) -> None:
        rows = self.good()
        rows[2]["temperature_c"] = crit.IDLE_TEMPERATURE_MAX_C + 1
        self.assertFalse(crit.evaluate_arm_scan(rows, 7.5)["judged_ok"])

    def test_mixed_firmware_fails(self) -> None:
        # LeRobot 连接时会因固件不一致直接报错，整臂阶段必须先拦下。
        rows = self.good()
        rows[0]["firmware"] = "3.9"
        self.assertFalse(crit.evaluate_arm_scan(rows, 7.5)["judged_ok"])

    def test_alarm_bit_fails(self) -> None:
        rows = self.good()
        rows[5]["status_raw"] = 0x20
        self.assertFalse(crit.evaluate_arm_scan(rows, 7.5)["judged_ok"])

    def test_missing_profile_cannot_pass(self) -> None:
        # 少选一个下拉框不能等于少判一项。
        self.assertFalse(crit.evaluate_arm_scan(self.good(), None)["judged_ok"])

    def test_unreadable_motor_fails(self) -> None:
        rows = self.good()
        rows[7] = {"ok": False, "motor_name": "gripper"}
        self.assertFalse(crit.evaluate_arm_scan(rows, 7.5)["judged_ok"])

    def test_voltage_spread_is_recorded_not_judged(self) -> None:
        rows = self.good()
        rows[0]["voltage_v"] = 7.0
        result = crit.evaluate_arm_scan(rows, 7.5)
        spread = next(c for c in result["checks"] if c["id"] == "S3.voltage_spread")
        self.assertFalse(spread["ok"])
        self.assertFalse(spread["judged"])
        self.assertTrue(result["judged_ok"])


class ProtectionLimitTest(unittest.TestCase):
    def test_limit_below_the_7v5_supply_is_flagged_but_not_judged(self) -> None:
        # 规格书过压阈值 7.4V，BOM 电源 7.5V：真机限值待读。只记录，真越限时状态位会让 S3.status 失败。
        rows = [snapshot(name, max_voltage_limit_v=7.4, max_temperature_limit_c=70) for name in MOTORS]
        result = crit.evaluate_arm_scan(rows, 7.5)
        limits = next(c for c in result["checks"] if c["id"] == "S3.protection_limits")
        self.assertFalse(limits["ok"])
        self.assertFalse(limits["judged"])
        self.assertEqual(limits["value"]["max_voltage_limit_v"], [7.4])


class JointIdentityTest(unittest.TestCase):
    def spans(self, **moved):
        base = {name: 10 for name in MOTORS}
        base.update(moved)
        return base

    def test_moving_the_target_joint_passes(self) -> None:
        self.assertTrue(crit.evaluate_joint_identity("joint_3", self.spans(joint_3=900))["judged_ok"])

    def test_wrong_motor_moving_fails(self) -> None:
        # ID 写对了，但装进了别的关节：动 J3 时 ID 4 跨度最大。
        result = crit.evaluate_joint_identity("joint_3", self.spans(joint_4=900, joint_3=20))
        self.assertFalse(result["judged_ok"])
        self.assertEqual(result["dominant"], "joint_4")

    def test_coupled_motion_below_the_ratio_fails(self) -> None:
        result = crit.evaluate_joint_identity("joint_2", self.spans(joint_2=600, joint_3=300))
        self.assertFalse(result["judged_ok"])

    def test_too_little_travel_fails(self) -> None:
        result = crit.evaluate_joint_identity("joint_1", self.spans(joint_1=60, joint_2=0))
        self.assertFalse(result["judged_ok"])


class ReadoutCriteriaTest(unittest.TestCase):
    def readout(self, mean=None, span=None, calibrated=True):
        keys = [f"{n}.pos" for n in MOTORS]
        return {
            "is_calibrated": calibrated,
            "mean": mean or {k: 0.0 for k in keys},
            "span": span or {k: 0.0 for k in keys},
            "first": {k: 0.0 for k in keys},
            "last": {k: 0.0 for k in keys},
        }

    def test_zero_pose_passes_near_zero(self) -> None:
        self.assertTrue(crit.evaluate_readout("zero", self.readout())["judged_ok"])

    def test_zero_pose_fails_when_a_joint_is_off(self) -> None:
        r = self.readout()
        r["mean"]["joint_4.pos"] = crit.ZERO_POSE_TOLERANCE_DEG + 5
        self.assertFalse(crit.evaluate_readout("zero", r)["judged_ok"])

    def test_uncalibrated_driver_fails(self) -> None:
        self.assertFalse(crit.evaluate_readout("zero", self.readout(calibrated=False))["judged_ok"])

    def test_gripper_open_needs_near_minus_65(self) -> None:
        r = self.readout()
        r["mean"]["gripper.pos"] = -64.0
        self.assertTrue(crit.evaluate_readout("gripper_open", r)["judged_ok"])
        r["mean"]["gripper.pos"] = -20.0
        self.assertFalse(crit.evaluate_readout("gripper_open", r)["judged_ok"])

    def test_sweeping_joint_6_moves_the_joint_7_key(self) -> None:
        # openarm_mini 的 JOINT_REMAP：leader joint_6 → follower joint_7.pos。
        r = self.readout()
        r["span"]["joint_7.pos"] = 40.0
        self.assertTrue(crit.evaluate_readout("sweep", r, "joint_6")["judged_ok"])
        r = self.readout()
        r["span"]["joint_6.pos"] = 40.0
        self.assertFalse(crit.evaluate_readout("sweep", r, "joint_6")["judged_ok"])

    def test_remap_matches_the_installed_driver(self) -> None:
        driver = Path(main._project_root()) / ".venv-lerobot/lib/python3.12/site-packages/lerobot/teleoperators/openarm_mini/openarm_mini.py"
        if not driver.is_file():
            self.skipTest("本机没有 .venv-lerobot")
        source = driver.read_text(encoding="utf-8")
        self.assertIn('JOINT_REMAP = {"joint_6": "joint_7", "joint_7": "joint_6"}', source)
        self.assertIn("GRIPPER_TELEOP_TO_DEGREES = -0.65", source)

    def test_delivery_command_carries_side_and_robot(self) -> None:
        command = crit.teleoperate_command("/dev/serial/by-id/x", "OAML2026102101", "left")
        self.assertIn("--teleop.side=left", command)
        self.assertIn("--robot.type=openarm_follower", command)
        self.assertIn("--teleop.id=OAML2026102101", command)


class CriteriaTableTest(unittest.TestCase):
    def test_every_criterion_has_a_translated_title(self) -> None:
        for criterion in crit.CRITERIA:
            key = crit.criterion_key(criterion["id"])
            with self.subTest(criterion=criterion["id"]):
                self.assertIn(key, messages.MESSAGES)

    def test_tbc_criteria_never_gate(self) -> None:
        # 待定标项只记录，定标前不得影响 PASS/FAIL。
        for criterion in crit.CRITERIA:
            if criterion["basis"] == "tbc":
                with self.subTest(criterion=criterion["id"]):
                    self.assertFalse(criterion["judged"])


def _req(record):
    return record["data"].get("request", {})


def rec(at: str, action: str, request=None, result=None, error=None):
    data = {"request": request or {}}
    if error is not None:
        data["error"] = error
    else:
        data["result"] = result or {}
    return {"recorded_at": at, "action": action, "robot_id": "OAML2026102101", "data": data}


def full_pass_records():
    records = []
    t = iter(f"2026-10-21T10:{m:02d}:{s:02d}+08:00" for m in range(60) for s in range(0, 60, 5))
    records.append(rec(next(t), "checklist", {"stage": "S1"}, {"ok": True, "operator": "A"}))
    for name in main.MINI_SETUP_ORDER:
        motor_id = MOTORS[name]["id"]
        records.append(rec(next(t), "scan-current", {}, {"detected": {"id": 1}}))
        records.append(rec(next(t), "init-id", {"motor": name, "hardware_profile": "mini_field_7v5"},
                           {"verified": True, "target_id": motor_id}))
        records.append(rec(next(t), "scan-current", {"initial_id": motor_id, "initial_baudrate": 1_000_000},
                           {"detected": {"id": motor_id}}))
        records.append(rec(next(t), "feedback-test", {"motor": name}, {"ok": True, "span": 900}))
    records.append(rec(next(t), "scan-all", {}, {"judged": True, "overall_ok": True,
                                                 "hardware_profile": "mini_field_7v5", "passed": 8, "total": 8}))
    records.append(rec(next(t), "comm-stability", {}, {"ok": True, "rounds": 900, "failures": 0}))
    for name in MOTORS:
        records.append(rec(next(t), "joint-identity", {"motor": name}, {"ok": True}))
    records.append(rec(next(t), "calibration/precheck", {}, {"overall_ok": True}))
    records.append(rec(next(t), "calibration/finished", {}, {"ok": True, "phase": "saved"}))
    records.append(rec(next(t), "verify-calibration", {"power_cycled": False}, {"overall_ok": True}))
    records.append(rec(next(t), "verify-calibration", {"power_cycled": True}, {"overall_ok": True}))
    records.append(rec(next(t), "official-readout", {"mode": "zero"}, {"ok": True}))
    records.append(rec(next(t), "official-readout", {"mode": "gripper_open"}, {"ok": True}))
    for name in gate.READOUT_SWEEPS:
        records.append(rec(next(t), "official-readout", {"mode": "sweep", "motor": name}, {"ok": True}))
    return records


class ReleaseGateTest(unittest.TestCase):
    def test_complete_log_passes(self) -> None:
        result = gate.evaluate(full_pass_records(), MOTORS)
        self.assertEqual(result["verdict"], "PASS", [i for i in result["items"] if i["status"] != "PASS"])

    def test_missing_stage_holds(self) -> None:
        records = [r for r in full_pass_records() if r["action"] != "comm-stability"]
        result = gate.evaluate(records, MOTORS)
        self.assertEqual(result["verdict"], "HOLD")
        self.assertEqual(result["stages"]["S3"], "MISSING")

    def test_latest_failure_fails(self) -> None:
        records = full_pass_records()
        records.append(rec("2026-10-21T23:00:00+08:00", "joint-identity", {"motor": "joint_4"}, {"ok": False}))
        self.assertEqual(gate.evaluate(records, MOTORS)["verdict"], "FAIL")

    def test_retest_after_failure_passes_but_history_is_kept(self) -> None:
        records = full_pass_records()
        records.insert(1, rec("2026-10-21T09:59:00+08:00", "scan-all", {}, error="port busy"))
        result = gate.evaluate(records, MOTORS)
        self.assertEqual(result["verdict"], "PASS")
        self.assertTrue(any(a["detail"] == "port busy" for a in gate.anomalies(records)))

    def test_checks_before_the_saved_calibration_do_not_count(self) -> None:
        # 重新校准后，旧的核对是对上一份文件的证据。
        records = full_pass_records()
        records.append(rec("2026-10-21T23:00:00+08:00", "calibration/finished", {}, {"phase": "saved"}))
        result = gate.evaluate(records, MOTORS)
        self.assertEqual(result["verdict"], "HOLD")
        self.assertEqual(result["stages"]["S5"], "MISSING")
        self.assertEqual(result["stages"]["S6"], "MISSING")

    def test_unsaved_calibration_fails(self) -> None:
        records = full_pass_records()
        records.append(rec("2026-10-21T23:00:00+08:00", "calibration/finished", {}, {"phase": "finished_unsaved"}))
        self.assertEqual(gate.evaluate(records, MOTORS)["verdict"], "FAIL")

    def test_scan_without_the_7v5_profile_does_not_count(self) -> None:
        records = full_pass_records()
        records.append(rec("2026-10-21T23:00:00+08:00", "scan-all", {},
                           {"judged": True, "overall_ok": True, "hardware_profile": ""}))
        self.assertEqual(gate.evaluate(records, MOTORS)["stages"]["S3"], "FAIL")

    def test_old_format_scan_is_ignored(self) -> None:
        # 2026-09-29 的扫描记录没有判定字段，不能当 S4 证据。
        records = [r for r in full_pass_records() if r["action"] != "scan-all"]
        records.append(rec("2026-10-21T23:00:00+08:00", "scan-all", {}, {"overall_ok": True}))
        self.assertEqual(gate.evaluate(records, MOTORS)["stages"]["S3"], "MISSING")

    def test_ids_are_part_of_the_flow(self) -> None:
        # 装配后逐颗写 ID 是必做阶段：少一颗就不能放行。
        records = [r for r in full_pass_records()
                   if not (r["action"] == "init-id" and _req(r).get("motor") == "joint_3")]
        result = gate.evaluate(records, MOTORS)
        self.assertEqual(result["verdict"], "HOLD")
        self.assertEqual(result["stages"]["S2"], "MISSING")

    def test_rescan_and_joint_check_must_follow_the_write(self) -> None:
        # 重写了 ID，之前的复扫和动关节确认就不算了。
        records = full_pass_records()
        records.append(rec("2026-10-21T23:00:00+08:00", "init-id",
                           {"motor": "gripper", "hardware_profile": "mini_field_7v5"}, {"verified": True}))
        result = gate.evaluate(records, MOTORS)
        status = {i["key"]: i["status"] for i in result["items"]}
        self.assertEqual(status["S2.gripper.rescan"], "MISSING")
        self.assertEqual(status["S2.gripper.joint"], "MISSING")

    def test_pre_assembly_writes_on_the_5v_bench_do_not_count(self) -> None:
        # 2026-09-29 那批是装配前在 5V 台架上写的；新流程要求装配后按关节重写。
        records = [r for r in full_pass_records() if r["action"] != "init-id"]
        for name in main.MINI_SETUP_ORDER:
            records.insert(1, rec("2026-10-21T09:00:00+08:00", "init-id",
                                  {"motor": name, "hardware_profile": "mini_bench_5v"}, {"verified": True}))
        self.assertEqual(gate.evaluate(records, MOTORS)["stages"]["S2"], "MISSING")

    def test_joint_check_that_saw_no_motion_fails(self) -> None:
        records = full_pass_records()
        records.append(rec("2026-10-21T23:00:00+08:00", "feedback-test", {"motor": "joint_5"}, {"ok": False, "span": 4}))
        self.assertEqual(gate.evaluate(records, MOTORS)["stages"]["S2"], "FAIL")

    def test_release_stage_follows_the_verdict(self) -> None:
        self.assertEqual(gate.evaluate(full_pass_records(), MOTORS)["stages"]["S7"], "PASS")
        records = [r for r in full_pass_records() if r["action"] != "comm-stability"]
        self.assertEqual(gate.evaluate(records, MOTORS)["stages"]["S7"], "MISSING")


class ChecklistTest(unittest.TestCase):
    def test_s1_needs_the_operator(self) -> None:
        items = {key: True for key in main.CHECKLISTS["S1"]}
        self.assertFalse(main.submit_checklist("S1", items, "")["ok"])
        self.assertTrue(main.submit_checklist("S1", items, "Peng")["ok"])

    def test_unchecked_item_fails(self) -> None:
        items = {key: True for key in main.CHECKLISTS["S1"]}
        items["daisy_chain"] = False
        self.assertFalse(main.submit_checklist("S1", items, "Peng")["ok"])

    def test_only_the_preparation_checklist_remains(self) -> None:
        # 测试站只做软件测试：装配检查归装配环节，不再在这里勾。
        self.assertEqual(list(main.CHECKLISTS), ["S1"])

    def test_every_item_is_translated(self) -> None:
        for stage, keys in main.CHECKLISTS.items():
            for key in keys:
                with self.subTest(stage=stage, key=key):
                    self.assertIn(f"checklist_{stage}_{key}", messages.MESSAGES)


class ArchiveTest(unittest.TestCase):
    def setUp(self) -> None:
        self._print_pdf = gate.print_pdf
        gate.print_pdf = lambda _html, _pdf: "skipped in tests"  # type: ignore[assignment]
        messages.set_language("zh")

    def tearDown(self) -> None:
        gate.print_pdf = self._print_pdf  # type: ignore[assignment]

    def test_archive_writes_files_index_and_increments_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = root / "s.jsonl"
            session.write_text("{}\n", encoding="utf-8")
            first = gate.write_archive(root, "OAML2026102101", "left", full_pass_records(), MOTORS,
                                       {"workstation_version": "0.2.0"}, session, None)
            self.assertEqual(first["verdict"], "PASS")
            self.assertEqual(first["doc_id"], "OAM-L-BENCH-RESULT-OAML2026102101-R01")
            second = gate.write_archive(root, "OAML2026102101", "left", full_pass_records(), MOTORS,
                                        {}, session, None)
            self.assertEqual(second["revision"], 2)
            index = (root / "编号与归档索引.md").read_text(encoding="utf-8")
            self.assertEqual(index.count("\n| OAML2026102101 |"), 2)
            report = Path(first["files"][0]).read_text(encoding="utf-8")
            self.assertIn("放行判定", report)
            self.assertIn("未执行，不得解释为通过", report)


class ReadoutScriptTest(unittest.TestCase):
    def test_script_uses_the_official_entry_points(self) -> None:
        source = main.READOUT_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("connect(calibrate=False)", source)
        self.assertIn("get_action()", source)
        self.assertNotIn("enable_torque", source)
        self.assertNotIn("send_feedback", source)

    def test_side_follows_the_serial(self) -> None:
        self.assertEqual(main.side_of("OAML2026102101"), "left")
        self.assertEqual(main.side_of("OAMR2026102101"), "right")


if __name__ == "__main__":
    unittest.main()


class ReviewFixesTest(unittest.TestCase):
    """2026-10-21 代码审查发现的问题，逐条钉住。"""

    def test_precondition_errors_do_not_count_as_results(self) -> None:
        # 通信测试跑着时误点「断电后再核对」→ 串口正忙。这不是那一项的测试结果。
        records = full_pass_records()
        busy = rec("2026-10-21T23:00:00+08:00", "verify-calibration", {"power_cycled": True}, error="busy")
        busy["data"]["precondition"] = True
        records.append(busy)
        self.assertEqual(gate.evaluate(records, MOTORS)["verdict"], "PASS")
        self.assertFalse(any(a["detail"] == "busy" for a in gate.anomalies(records)))

    def test_abandoned_reuse_prompt_keeps_the_saved_calibration(self) -> None:
        # 已有文件时在沿用提示处中止：电机和文件都没变，不能作废上一份校准的证据。
        records = full_pass_records()
        records.append(rec("2026-10-21T23:00:00+08:00", "calibration/finished", {},
                           {"phase": "failed", "had_calibration_file": True, "answers": []}))
        self.assertEqual(gate.evaluate(records, MOTORS)["verdict"], "PASS")

    def test_aborted_recalibration_still_fails(self) -> None:
        records = full_pass_records()
        records.append(rec("2026-10-21T23:00:00+08:00", "calibration/finished", {},
                           {"phase": "failed", "had_calibration_file": True, "answers": ["c", ""]}))
        self.assertEqual(gate.evaluate(records, MOTORS)["verdict"], "FAIL")

    def test_malformed_request_does_not_break_the_gate(self) -> None:
        records = full_pass_records()
        records.append(rec("2026-10-21T23:00:00+08:00", "scan-current",
                           {"initial_id": "x", "initial_baudrate": "fast"}, {"detected": {}}))
        self.assertIn(gate.evaluate(records, MOTORS)["verdict"], ("PASS", "HOLD", "FAIL"))

    def test_confirm_answers_each_prompt_once(self) -> None:
        session = main.CalibrationSession()

        class Proc:
            stdin = type("W", (), {"write": lambda self, s: None, "flush": lambda self: None})()

            def poll(self):
                return None

        session._proc = Proc()  # type: ignore[assignment]
        session._phase_state = "await_gripper_closed"
        session.confirm("", "await_gripper_closed")
        with self.assertRaises(main.PreconditionError):
            session.confirm("", "await_gripper_closed")
        with self.assertRaises(main.PreconditionError):
            session.confirm("", "await_gripper_open")


class CalibrationHoldsTheBusTest(unittest.TestCase):
    """官方校准子进程整段持有串口锁；期间其他串口操作立即被拒，退出后释放。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        fake = Path(self.tmp.name) / "lerobot-calibrate"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('Press ENTER when ready...', flush=True)\n"
            "sys.stdin.readline()\n",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        main.set_lerobot_calibrate_override(str(fake))
        self.recorded: list[tuple[str, str]] = []
        self._append = main.append_session_record
        main.append_session_record = lambda rid, action, payload: self.recorded.append((rid, action))  # type: ignore[assignment]

    def tearDown(self) -> None:
        main.append_session_record = self._append  # type: ignore[assignment]
        main.set_lerobot_calibrate_override(None)
        self.tmp.cleanup()

    def test_lock_is_held_while_running_and_released_after(self) -> None:
        import time as _time

        session = main.CalibrationSession()
        original = main.CALIBRATION
        main.CALIBRATION = session  # open() 查的是模块级实例
        try:
            session.start("/dev/null", "OAML2099010101")
            self.assertTrue(main.SERIAL_PORT_LOCK.locked())
            client = main.FeetechSdkClient.__new__(main.FeetechSdkClient)
            client._holds_lock = False
            with self.assertRaises(main.PreconditionError):
                client.open()
            session.abort()
            for _ in range(50):
                if not main.SERIAL_PORT_LOCK.locked() and self.recorded:
                    break
                _time.sleep(0.1)
            self.assertFalse(main.SERIAL_PORT_LOCK.locked())
            self.assertEqual(self.recorded, [("OAML2099010101", "calibration/finished")])
        finally:
            main.CALIBRATION = original
