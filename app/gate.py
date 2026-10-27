"""放行门与归档报告。

只从会话日志判定：页面状态、内存、人工转述都不算证据。规则：
- 每个必做项取**最近一次**记录；最近一次失败 → FAIL，没有记录 → MISSING。
- 校准之后的项（核对、断电核对、官方读数）必须晚于最近一次「已保存」的校准，
  否则那是对上一份校准文件的证据，不算。
- 结论：全部 PASS → PASS；任一 FAIL → FAIL；其余 → HOLD。
- 历史失败不删，保留在内部会话日志与机读放行文件；客户报告只展示最终有效记录。

SO-ARM101 的教训：判定只在前端算、归档脚本按默认值写「通过」，结果三台 Leader 的
质检节是「本次未采集」而结论仍是通过。这里缺项一律 HOLD。
"""

from __future__ import annotations

import base64
import html
import json
import re
import shutil
import subprocess
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import criteria as crit
import messages
from messages import m as _m

# 测试站测装配好的整臂。S1 准备 → S2 装配后逐颗写 ID → S3 整臂电气与通信 → S4 关节身份
# → S5 官方校准 → S6 官方驱动读数 → S7 放行；S8 follower 配对、S9 增强复测可选。
STAGES = ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9")
REQUIRED_STAGES = ("S1", "S2", "S3", "S4", "S5", "S6")
OPTIONAL_STAGES = ("S8", "S9")
DEFAULT_BAUDRATE = 1_000_000
FIELD_PROFILE = "mini_field_7v5"
# S6 必做的扫动：J6/J7 验证驱动的对调，其余关节的身份已由 S4 在寄存器层验证。
READOUT_SWEEPS = ("joint_6", "joint_7")
REPORT_FILE_LABEL = "OpenArmMini_基础测试记录"
REPORT_LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "eckstein_logo.png"
REPORT_DOCUMENT_REVISION = 1

PASS, FAIL, MISSING = "PASS", "FAIL", "MISSING"


def _request(record: dict[str, Any]) -> dict[str, Any]:
    return (record.get("data") or {}).get("request") or {}


def _result(record: dict[str, Any]) -> dict[str, Any]:
    return (record.get("data") or {}).get("result") or {}


def _error(record: dict[str, Any]) -> str:
    return str((record.get("data") or {}).get("error") or "")


def _precondition(record: dict[str, Any]) -> bool:
    """还没碰到硬件就被拦下（串口正忙、没选串口等）。不是那一项的测试结果。"""

    return bool((record.get("data") or {}).get("precondition"))


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _calibration_attempted(record: dict[str, Any]) -> bool:
    """这次校准有没有真的重新测量。

    已有文件时在沿用提示处中止、或敲裸回车沿用，电机和文件都没变，
    不能让它把上一份已保存校准的证据作废。
    """

    result = _result(record)
    if not result.get("had_calibration_file"):
        return True
    return "c" in (result.get("answers") or []) or result.get("phase") == "saved"


def _latest(
    records: list[dict[str, Any]],
    action: str,
    where: Callable[[dict[str, Any]], bool] = lambda _r: True,
    after: str = "",
) -> dict[str, Any] | None:
    found = None
    for record in records:
        if record.get("action") != action or _precondition(record):
            continue
        if after and str(record.get("recorded_at", "")) < after:
            continue
        if where(record):
            found = record
    return found


def _item(
    stage: str,
    key: str,
    label: str,
    record: dict[str, Any] | None,
    passed: Callable[[dict[str, Any]], bool],
    detail: Callable[[dict[str, Any]], str] = lambda _r: "",
) -> dict[str, Any]:
    if record is None:
        status, at, text = MISSING, "", ""
    elif _error(record):
        status, at, text = FAIL, record.get("recorded_at", ""), _error(record)
    else:
        ok = passed(record)
        status = PASS if ok else FAIL
        at = record.get("recorded_at", "")
        text = detail(record) or ("" if ok else str(_result(record).get("reason", "")))
    return {"stage": stage, "key": key, "label": label, "status": status, "at": at, "detail": text}


def motor_title(motors: dict[str, dict[str, Any]], name: str) -> str:
    return f"{motors[name]['part']} · {messages.motor_label(name)}"


def evaluate(records: list[dict[str, Any]], motors: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """按会话日志算放行门。motors 是 OPENARM_MINI_MOTORS（键名 → id/part）。"""

    items: list[dict[str, Any]] = []
    ordered = sorted(motors, key=lambda n: motors[n]["id"])

    # S1 准备：工位检查表（含操作员）
    record = _latest(records, "checklist", lambda r: _request(r).get("stage") == "S1")
    items.append(_item("S1", "S1.checklist", _m("gate_checklist"), record,
                       lambda r: bool(_result(r).get("ok"))))

    # S2：装配后逐颗写 ID → 断电复扫 → 只动这个关节确认（官方顺序夹爪 → J1）
    for name in reversed(ordered):
        target = motors[name]["id"]
        title = motor_title(motors, name)
        # 只认 7.5V 档下写的 ID：0.2.0 及以前是装配前在 5V 台架上写的，不是「装配后按关节写」。
        write = _latest(records, "init-id", lambda r, n=name: _request(r).get("motor") == n
                        and _request(r).get("hardware_profile") == FIELD_PROFILE)
        items.append(_item("S2", f"S2.{name}.write", _m("gate_write", title=title), write,
                           lambda r: bool(_result(r).get("verified"))))
        rescan = _latest(
            records,
            "scan-current",
            lambda r, t=target: _as_int(_request(r).get("initial_id")) == t
            and _as_int(_request(r).get("initial_baudrate")) == DEFAULT_BAUDRATE,
            after=write.get("recorded_at", "") if write else "",
        )
        items.append(_item("S2", f"S2.{name}.rescan", _m("gate_rescan", title=title),
                           rescan if write else None,
                           lambda r, t=target: (_result(r).get("detected") or {}).get("id") == t))
        confirm = _latest(records, "feedback-test", lambda r, n=name: _request(r).get("motor") == n,
                          after=write.get("recorded_at", "") if write else "")
        items.append(_item("S2", f"S2.{name}.joint", _m("gate_joint_confirm", title=title),
                           confirm if write else None,
                           lambda r: bool(_result(r).get("ok")),
                           lambda r: _m("gate_detail_span", span=_result(r).get("span", "-"))))

    # S3：判过的整臂扫描（旧格式记录不算）+ 通信稳定
    scan = _latest(records, "scan-all", lambda r: bool(_result(r).get("judged")) or bool(_error(r)))

    def scan_passed(record: dict[str, Any]) -> bool:
        result = _result(record)
        return bool(result.get("overall_ok")) and result.get("hardware_profile") == FIELD_PROFILE

    def scan_detail(record: dict[str, Any]) -> str:
        result = _result(record)
        if result.get("hardware_profile") != FIELD_PROFILE:
            return _m("gate_detail_need_field_profile")
        return _m("gate_detail_scan", passed=result.get("passed", 0), total=result.get("total", 8))

    items.append(_item("S3", "S3.scan", _m("gate_scan"), scan, scan_passed, scan_detail))
    comm = _latest(records, "comm-stability")
    items.append(_item("S3", "S3.comm", _m("gate_comm"), comm, lambda r: bool(_result(r).get("ok")),
                       lambda r: _m("gate_detail_comm", rounds=_result(r).get("rounds", 0),
                                    failures=_result(r).get("failures", "-"))))

    # S4：逐关节身份
    for name in ordered:
        record = _latest(records, "joint-identity", lambda r, n=name: _request(r).get("motor") == n)
        items.append(_item("S4", f"S4.{name}", _m("gate_identity", title=motor_title(motors, name)),
                           record, lambda r: bool(_result(r).get("ok"))))

    # S5：预检 → 校准保存 → 核对 → 断电核对
    precheck = _latest(records, "calibration/precheck")
    items.append(_item("S5", "S5.precheck", _m("gate_precheck"), precheck,
                       lambda r: bool(_result(r).get("overall_ok"))))
    finished = _latest(records, "calibration/finished", _calibration_attempted)
    items.append(_item("S5", "S5.saved", _m("gate_saved"), finished,
                       lambda r: _result(r).get("phase") == "saved",
                       lambda r: "" if _result(r).get("phase") == "saved"
                       else _m("gate_detail_phase", phase=_result(r).get("phase", "-"))))
    saved = _latest(records, "calibration/finished", lambda r: _result(r).get("phase") == "saved")
    saved_at = saved.get("recorded_at", "") if saved else ""
    for key, power_cycled, label in (("S5.verify", False, "gate_verify"),
                                     ("S5.verify_power_cycled", True, "gate_verify_power_cycled")):
        record = _latest(
            records,
            "verify-calibration",
            lambda r, pc=power_cycled: bool(_request(r).get("power_cycled")) == pc,
            after=saved_at,
        ) if saved else None
        items.append(_item("S5", key, _m(label), record, lambda r: bool(_result(r).get("overall_ok"))))

    # S6：官方驱动读数，必须晚于这份校准
    readouts = [("zero", ""), ("gripper_open", "")] + [("sweep", n) for n in READOUT_SWEEPS]
    for mode, name in readouts:
        record = _latest(
            records,
            "official-readout",
            lambda r, md=mode, n=name: _request(r).get("mode") == md
            and (not n or _request(r).get("motor") == n),
            after=saved_at,
        ) if saved else None
        label = (_m("gate_readout_sweep", title=motor_title(motors, name)) if name
                 else _m("gate_readout_" + mode))
        items.append(_item("S6", f"S6.{mode}{'.' + name if name else ''}", label, record,
                           lambda r: bool(_result(r).get("ok"))))

    statuses = {item["status"] for item in items}
    verdict = PASS if statuses == {PASS} else (FAIL if FAIL in statuses else "HOLD")
    stages = {}
    for stage in STAGES:
        stage_items = [i for i in items if i["stage"] == stage]
        if stage == "S7":
            # S7 是放行本身：前面全部通过即通过。
            stages[stage] = PASS if verdict == PASS else MISSING
        elif not stage_items:
            stages[stage] = "optional"
        elif all(i["status"] == PASS for i in stage_items):
            stages[stage] = PASS
        elif any(i["status"] == FAIL for i in stage_items):
            stages[stage] = FAIL
        else:
            stages[stage] = MISSING
    return {
        "verdict": verdict,
        "items": items,
        "stages": stages,
        "counts": {s: sum(1 for i in items if i["status"] == s) for s in (PASS, FAIL, MISSING)},
        "calibration_saved_at": saved_at,
        "criteria_version": crit.CRITERIA_VERSION,
    }


def anomalies(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    """所有失败过的操作。复测通过后也保留——归档最需要解释的恰恰是失败的那几次。"""

    rows = []
    for record in records:
        if _precondition(record):
            continue
        result = _result(record)
        error = _error(record)
        failed = bool(error)
        if not failed and record.get("action") in ("scan-all", "calibration/precheck", "verify-calibration"):
            failed = result.get("overall_ok") is False
        elif not failed and "ok" in result:
            failed = result.get("ok") is False
        if failed:
            rows.append(
                {
                    "at": str(record.get("recorded_at", "")),
                    "action": str(record.get("action", "")),
                    "detail": error or str(result.get("reason") or result.get("phase") or ""),
                }
            )
    return rows


# ---------- 报告 ----------

Block = tuple[str, Any]


@lru_cache(maxsize=1)
def _report_logo_data_uri() -> str:
    """把正式企业标识嵌入报告，保证单独交付 HTML/PDF 时不丢图。"""

    payload = REPORT_LOGO_PATH.read_bytes()
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError(f"invalid report logo: {REPORT_LOGO_PATH}")
    return "data:image/png;base64," + base64.b64encode(payload).decode("ascii")


def _fmt(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if isinstance(value, (list, tuple)):
        return ", ".join(_fmt(v) for v in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}={_fmt(v)}" for k, v in value.items())
    return str(value)


def report_document_id(robot_id: str, side: str) -> str:
    """客户文档版次独立于工作站内部归档次数。"""

    code = "L" if side == "left" else "R"
    return f"OAM-{code}-BENCH-RESULT-{robot_id}-R{REPORT_DOCUMENT_REVISION:02d}"


def _build_report_language(
    robot_id: str,
    side: str,
    records: list[dict[str, Any]],
    motors: dict[str, dict[str, Any]],
    context: dict[str, Any],
    revision: int,
) -> tuple[list[Block], dict[str, Any]]:
    """使用当前文案语言构建一个完整的报告区块。"""

    result = evaluate(records, motors)
    ordered = sorted(motors, key=lambda n: motors[n]["id"])
    doc_id = report_document_id(robot_id, side)
    s1_record = _latest(records, "checklist", lambda r: _request(r).get("stage") == "S1")
    operator = _result(s1_record).get("operator", "") if s1_record else ""
    project_lead = str(context.get("project_lead") or "-")
    language = messages.get_language()
    blocks: list[Block] = [
        ("h1", _m("report_title", robot_id=robot_id)),
        ("table", ([_m("report_col_item"), _m("report_col_content")], [
            [_m("report_document_id"), doc_id],
            [_m("report_language"), _m("report_language_" + language)],
            [_m("report_serial_side"),
             f"{robot_id} / {_m('report_side_left' if side == 'left' else 'report_side_right')}"],
            [_m("report_generated_at"), datetime.now().astimezone().isoformat(timespec="seconds")],
            [_m("report_verdict"), result["verdict"]],
            [_m("report_operator"), operator or "-"],
            [_m("report_project_lead"), project_lead],
            [_m("report_workstation_version"), context.get("workstation_version", "-")],
            [_m("report_criteria_version"), crit.CRITERIA_VERSION],
            ["LeRobot", f"{context.get('lerobot', {}).get('version', '-')} "
                        f"({context.get('lerobot', {}).get('source', '-')})"],
            [_m("report_hardware_basis"), "pkooij/open-arms-mini README/BOM; lerobot teleoperators/openarm_mini"],
            [_m("report_supply"), _m("report_supply_value")],
        ])),
        ("p", _m("report_intro")),
        ("h2", _m("report_section_release")),
        ("table", ([_m("report_col_stage"), _m("report_col_test_item"), _m("report_col_result"),
                    _m("report_col_recorded_at"), _m("report_col_notes")],
                   [[i["stage"], i["label"], i["status"], i["at"] or "-", i["detail"] or ""]
                    for i in result["items"]])),
        ("h2", _m("report_section_preparation")),
        _checklist_table(s1_record, "S1"),
    ]

    # S2
    rows = []
    for name in reversed(ordered):
        write = _latest(records, "init-id", lambda r, n=name: _request(r).get("motor") == n
                        and _request(r).get("hardware_profile") == FIELD_PROFILE)
        after = write.get("recorded_at", "") if write else ""
        rescan = _latest(records, "scan-current",
                         lambda r, t=motors[name]["id"]: _as_int(_request(r).get("initial_id")) == t,
                         after=after)
        confirm = _latest(records, "feedback-test", lambda r, n=name: _request(r).get("motor") == n,
                          after=after)
        wr = _result(write) if write else {}
        cf = _result(confirm) if confirm else {}
        baseline = _result(rescan).get("baseline", {}) if rescan else {}
        rows.append([
            motor_title(motors, name),
            _fmt((wr.get("detected") or {}).get("id")),
            _fmt(wr.get("target_id")),
            _m("report_yes") if rescan and not _error(rescan) else "-",
            _fmt(cf.get("span")),
            _fmt(cf.get("voltage_v")),
            _fmt(baseline.get("firmware")),
            _m("report_passed") if cf.get("ok") else (_m("report_failed") if confirm else _m("report_no_record")),
        ])
    blocks += [
        ("h2", _m("report_section_write_ids")),
        ("p", _m("report_write_ids_intro")),
        ("table", ([_m("report_col_joint"), _m("report_col_original_id"), _m("report_col_written_id"),
                    _m("report_col_power_cycle_rescan"), _m("report_col_confirmation_span"),
                    _m("report_col_voltage"), _m("report_col_firmware"), _m("report_col_confirmation")], rows)),
    ]

    # S3
    scan = _latest(records, "scan-all", lambda r: bool(_result(r).get("judged")))
    blocks.append(("h2", _m("report_section_electrical")))
    if scan:
        sr = _result(scan)
        blocks.append(("table", (
            [_m("report_col_joint"), "ID", _m("report_col_position"), _m("report_col_voltage"),
             _m("report_col_temperature"), _m("report_col_status"), _m("report_col_torque"),
             _m("report_col_firmware"), _m("report_col_overvoltage_limit"),
             _m("report_col_overtemperature_limit"), "Phase", "Max_Acc", _m("report_col_judgement")],
            [[motor_title(motors, r["motor_name"]) if r.get("motor_name") in motors
              else r.get("motor_title", r.get("motor_name")), _fmt(r.get("motor_id")),
              _fmt(r.get("present_position")), _fmt(r.get("voltage_v")), _fmt(r.get("temperature_c")),
              _fmt(r.get("status_raw")), _fmt(r.get("torque_enable")), _fmt(r.get("firmware")),
              _fmt(r.get("max_voltage_limit_v")), _fmt(r.get("max_temperature_limit_c")),
              _fmt(r.get("phase")), _fmt(r.get("max_acceleration")),
              _m("report_passed") if r.get("judged_ok") else _m("report_failed")]
             for r in sr.get("results", [])],
        )))
        blocks.append(("p", _m(
            "report_scan_summary",
            profile=sr.get("hardware_profile") or "-",
            firmware=_fmt(sr.get("firmware_versions")),
            spread=_fmt(sr.get("voltage_spread_v")),
            recorded_at=scan.get("recorded_at"),
        )))
    else:
        blocks.append(("p", _m("report_no_record") + "."))
    comm = _latest(records, "comm-stability")
    if comm:
        cr = _result(comm)
        blocks.append(("p", _m(
            "report_comm_summary",
            duration=_fmt(cr.get("duration_sec")),
            rounds=_fmt(cr.get("rounds")),
            reads=_fmt(cr.get("reads")),
            failures=_fmt(cr.get("failures")),
        )))

    # S4
    rows = []
    for name in ordered:
        record = _latest(records, "joint-identity", lambda r, n=name: _request(r).get("motor") == n)
        rr = _result(record) if record else {}
        rows.append([motor_title(motors, name), _fmt(rr.get("target_span")),
                     motor_title(motors, rr["dominant"]) if rr.get("dominant") in motors else "-",
                     _fmt(rr.get("runner_up_span")),
                     _m("report_passed") if rr.get("ok")
                     else (_m("report_failed") if record else _m("report_no_record"))])
    blocks += [
        ("h2", _m("report_section_identity")),
        ("table", ([_m("report_col_tested_joint"), _m("report_col_span_counts"),
                    _m("report_col_largest_span_motor"), _m("report_col_runner_up_span"),
                    _m("report_col_judgement")], rows)),
        ("p", _m("report_identity_criterion", ratio=f"{crit.IDENTITY_DOMINANCE_RATIO:g}",
                  minimum=crit.IDENTITY_MIN_SPAN_COUNTS)),
    ]

    # S5
    blocks.append(("h2", _m("report_section_calibration")))
    saved = _latest(records, "calibration/finished", lambda r: _result(r).get("phase") == "saved")
    saved_at = saved.get("recorded_at", "") if saved else ""
    calibration = context.get("calibration") or (_result(saved).get("calibration") if saved else None)
    if isinstance(calibration, dict):
        blocks.append(("table", (
            [_m("report_col_joint"), "id", "drive_mode", "homing_offset", "range_min", "range_max"],
            [[motor_title(motors, n) if n in motors else n, _fmt(v.get("id")), _fmt(v.get("drive_mode")),
              _fmt(v.get("homing_offset")), _fmt(v.get("range_min")), _fmt(v.get("range_max"))]
             for n, v in calibration.items() if isinstance(v, dict)],
        )))
    else:
        blocks.append(("p", _m("report_no_calibration")))
    if saved:
        blocks.append(("p", _m(
            "report_calibration_saved",
            recorded_at=saved.get("recorded_at"),
        )))

    # S6：客户报告只展示当前校准之后每个必测项的最终有效记录。
    # 历史失败与被后续复测覆盖的记录仍保留在会话日志和机读放行文件中。
    blocks.append(("h2", _m("report_section_readout")))
    rows = []
    readouts = [("zero", ""), ("gripper_open", "")] + [("sweep", n) for n in READOUT_SWEEPS]
    for mode, name in readouts:
        record = _latest(
            records,
            "official-readout",
            lambda r, md=mode, n=name: _request(r).get("mode") == md
            and (not n or _request(r).get("motor") == n),
            after=saved_at,
        ) if saved else None
        if record is None or _error(record):
            continue
        rr = _result(record)
        values = "; ".join(f"{c['id']}={_fmt(c.get('value'))}" for c in rr.get("checks", []))
        title = motor_title(motors, name) if name else ""
        mode_label = _m("report_mode_" + mode)
        rows.append([record.get("recorded_at", ""), mode_label, title,
                     values, _m("report_passed") if rr.get("ok") else _m("report_failed")])
    blocks.append(("table", ([_m("report_col_time"), _m("report_col_mode"), _m("report_col_joint"),
                              _m("report_col_readings"), _m("report_col_judgement")], rows))
                  if rows else ("p", _m("report_no_record") + "."))
    last_readout = _latest(
        records,
        "official-readout",
        lambda r: bool(_result(r).get("delivery_command")),
        after=saved_at,
    ) if saved else None
    if last_readout:
        blocks += [("p", _m("report_delivery_command")),
                   ("code", _result(last_readout)["delivery_command"])]

    # 客户报告只列参与放行的判据。待定标/仅记录项继续保留在 criteria.py 与内部数据中。
    basis_labels = {
        "official": _m("report_basis_official"),
        "spec": _m("report_basis_spec"),
        "derived": _m("report_basis_derived"),
    }
    blocks += [
        ("h2", _m("report_section_criteria")),
        ("table", ([_m("report_col_number"), _m("report_col_description"), _m("report_col_limit"),
                    _m("report_col_basis")],
                   [[c["id"], messages.m(crit.criterion_key(c["id"])),
                     f"{_fmt(c['limit'])} {c.get('unit', '')}".strip(),
                     basis_labels[c["basis"]]]
                    for c in crit.CRITERIA if c["judged"]])),
    ]
    blocks += [
        ("h2", _m("report_section_boundaries")),
        ("p", _m("report_boundaries")),
        ("h2", _m("report_section_signoff")),
        ("table", ([_m("report_col_role"), _m("report_col_name"), _m("report_col_signature"),
                    _m("report_col_date")],
                   [[_m("report_role_tester"), operator or "", "", ""],
                    [_m("report_project_lead"), project_lead, "", ""],
                    [_m("report_role_reviewer"), "", "", ""]])),
    ]
    return blocks, {
        **result,
        "doc_id": doc_id,
        "language": language,
        "operator": operator,
        "project_lead": project_lead,
    }


def build_report(
    robot_id: str,
    side: str,
    records: list[dict[str, Any]],
    motors: dict[str, dict[str, Any]],
    context: dict[str, Any],
    revision: int,
    language: str,
) -> tuple[list[Block], dict[str, Any]]:
    """用指定语言生成一份独立报告，不依赖当前 HTTP 请求语言。"""

    if language not in messages.LANGUAGES:
        raise ValueError(f"unsupported report language: {language}")
    original_language = messages.get_language()
    try:
        messages.set_language(language)
        return _build_report_language(robot_id, side, records, motors, context, revision)
    finally:
        messages.set_language(original_language)


def _checklist_table(record: dict[str, Any] | None, stage: str) -> Block:
    if record is None:
        return ("p", _m("report_no_record") + ".")
    items = _result(record).get("items", {})
    rows = [[messages.m(f"checklist_{stage}_{k}"), "✔" if v else "✘"] for k, v in items.items()]
    return ("table", ([_m("report_col_check_item"), _m("report_col_result")],
                      rows + [[_m("report_col_recorded_at"), record.get("recorded_at", "")]]))


def render_markdown(blocks: list[Block]) -> str:
    out: list[str] = []
    for kind, content in blocks:
        if kind == "h1":
            out.append(f"# {content}\n")
        elif kind == "h2":
            out.append(f"## {content}\n")
        elif kind == "p":
            out.append(f"{content}\n")
        elif kind == "code":
            out.append(f"```\n{content}\n```\n")
        elif kind == "table":
            head, rows = content
            cell = lambda v: str(v).replace("|", "\\|").replace("\n", " ")  # noqa: E731
            out.append("| " + " | ".join(cell(h) for h in head) + " |")
            out.append("|" + "---|" * len(head))
            out += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
            out.append("")
    return "\n".join(out)


def render_html(blocks: list[Block], title: str, language: str) -> str:
    parts = []
    title_rendered = False
    table_index = 0
    logo_uri = _report_logo_data_uri()
    for kind, content in blocks:
        if kind == "h1" and not title_rendered:
            parts.append(
                "<header class='report-header'>"
                "<div class='report-brand'>"
                f"<img class='report-logo' src='{logo_uri}' alt='ECKSTEIN'>"
                "<div class='report-product'>OPENARM MINI</div>"
                "</div>"
                f"<h1>{html.escape(str(content))}</h1>"
                "</header>"
            )
            title_rendered = True
        elif kind in ("h1", "h2"):
            parts.append(f"<{kind}>{html.escape(str(content))}</{kind}>")
        elif kind == "p":
            text = html.escape(str(content))
            text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
            parts.append(f"<p>{text}</p>")
        elif kind == "code":
            parts.append(f"<pre>{html.escape(str(content))}</pre>")
        elif kind == "table":
            table_index += 1
            head, rows = content
            body = "".join(
                "<tr>" + "".join(f"<td class='{_status_class(v)}'>{html.escape(str(v))}</td>" for v in row) + "</tr>"
                for row in rows
            )
            table_class = " class='report-meta'" if table_index == 1 else ""
            parts.append(f"<table{table_class}><thead><tr>" + "".join(f"<th>{html.escape(str(h))}</th>" for h in head)
                         + f"</tr></thead><tbody>{body}</tbody></table>")
    style = (
        "*{box-sizing:border-box}"
        "body{font:13px/1.55 'Noto Sans CJK SC','Microsoft YaHei',Arial,sans-serif;"
        "margin:0;color:#1d2733}"
        ".report-header{display:grid;grid-template-columns:180px 1fr;gap:22px;align-items:center;"
        "padding:0 0 12px;border-bottom:2px solid #2d5873;margin-bottom:14px;break-inside:avoid}"
        ".report-brand{min-width:0;border-left:4px solid #f47a00;padding-left:10px}"
        ".report-logo{display:block;width:168px;max-height:42px;object-fit:contain;object-position:left center}"
        ".report-product{margin-top:4px;color:#647888;font-size:9px;font-weight:700;"
        "letter-spacing:.16em}"
        "h1{font-size:20px;line-height:1.25;margin:0;text-align:right;color:#2d5873}"
        "h2{font-size:15px;color:#2d5873;margin-top:22px;padding-bottom:3px;"
        "border-bottom:1px solid #c8d5de;break-after:avoid}"
        "table{border-collapse:collapse;width:100%;margin:8px 0}"
        ".report-meta{margin-top:0;break-inside:avoid}"
        "th,td{border:1px solid #d6dee8;padding:4px 6px;text-align:left;vertical-align:top}"
        "th{background:#edf3f6;color:#2d5873}"
        "pre{background:#f1f5fa;padding:8px;white-space:pre-wrap;border-left:3px solid #f47a00}"
        ".PASS{color:#1a7f4b;font-weight:600}.FAIL{color:#b3261e;font-weight:600}.MISSING{color:#a15c00}"
        "@page{size:A4;margin:14mm}"
        "@media print{.report-header,.report-meta,tr{break-inside:avoid}}"
    )
    html_language = "zh-CN" if language == "zh" else language
    return (f"<!doctype html><html lang='{html_language}'><head><meta charset='utf-8'>"
            f"<title>{html.escape(title)}</title>"
            f"<style>{style}</style></head><body>{''.join(parts)}</body></html>")


def _status_class(value: Any) -> str:
    return str(value) if value in (PASS, FAIL, MISSING) else ""


def chromium_binary() -> str | None:
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    return None


def print_pdf(html_path: Path, pdf_path: Path) -> str:
    """用 Chromium 打印 PDF。失败不阻断归档：保留 md/html，返回错误说明。"""

    binary = chromium_binary()
    if binary is None:
        return "chromium not found"
    try:
        completed = subprocess.run(  # noqa: S603
            [binary, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()],
            capture_output=True, text=True, timeout=90,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return str(exc)
    if completed.returncode != 0 or not pdf_path.is_file():
        return (completed.stderr or completed.stdout or f"returncode={completed.returncode}")[-800:]
    return ""


def write_archive(
    archive_root: Path,
    robot_id: str,
    side: str,
    records: list[dict[str, Any]],
    motors: dict[str, dict[str, Any]],
    context: dict[str, Any],
    session_file: Path,
    calibration_file: Path | None,
) -> dict[str, Any]:
    """生成归档目录 test_reports/Leader/<编号>/。旧修订不删，新修订递增 R0n。"""

    directory = archive_root / "Leader" / robot_id
    directory.mkdir(parents=True, exist_ok=True)
    base = f"{robot_id}_{REPORT_FILE_LABEL}"
    revision = _next_archive_revision(directory, base)
    stem = base if revision == 1 else f"{base}_R{revision:02d}"
    suffix = "" if revision == 1 else f"_R{revision:02d}"

    files: list[Path] = []
    reports: dict[str, dict[str, Any]] = {}
    canonical_result: dict[str, Any] | None = None
    for language in messages.LANGUAGES:
        blocks, language_result = build_report(
            robot_id, side, records, motors, context, revision, language
        )
        language_stem = f"{stem}_{language}"
        md_path = directory / f"{language_stem}.md"
        html_path = directory / f"{language_stem}.html"
        pdf_path = directory / f"{language_stem}.pdf"
        md_path.write_text(render_markdown(blocks), encoding="utf-8")
        html_path.write_text(
            render_html(blocks, language_result["doc_id"], language), encoding="utf-8"
        )
        pdf_error = print_pdf(html_path, pdf_path)
        if pdf_error:
            error_path = directory / f"{language_stem}_pdf_error.txt"
            error_path.write_text(pdf_error, encoding="utf-8")
            files.append(error_path)
        files.extend([md_path, html_path] + ([pdf_path] if not pdf_error else []))
        reports[language] = {
            "language": language,
            "doc_id": language_result["doc_id"],
            "md": str(md_path),
            "html": str(html_path),
            "pdf": str(pdf_path) if not pdf_error else "",
            "pdf_error": pdf_error,
        }
        if language == messages.DEFAULT_LANGUAGE:
            canonical_result = language_result

    if canonical_result is None:  # pragma: no cover - LANGUAGES 始终包含 zh
        raise RuntimeError("default report language is not configured")
    result = canonical_result
    if session_file.is_file():
        target = directory / f"{robot_id}_OpenArmMini_会话日志{suffix}.jsonl"
        shutil.copyfile(session_file, target)
        files.append(target)
    if calibration_file is not None and calibration_file.is_file():
        target = directory / f"{robot_id}_OpenArmMini_校准参数{suffix}.json"
        shutil.copyfile(calibration_file, target)
        files.append(target)
    gate_path = directory / f"{robot_id}_OpenArmMini_放行判定{suffix}.json"
    gate_path.write_text(json.dumps({**result, "archive_revision": revision,
                                     "reports": reports, "context": context,
                                     "historical_anomalies": anomalies(records)},
                                    ensure_ascii=False, indent=2),
                         encoding="utf-8")
    files.append(gate_path)

    _append_index(archive_root, robot_id, side, result, Path(reports["zh"]["md"]))
    pdf_errors = {language: report["pdf_error"] for language, report in reports.items()
                  if report["pdf_error"]}
    return {
        "verdict": result["verdict"],
        "doc_id": result["doc_id"],
        "revision": revision,
        "directory": str(directory),
        "files": [str(f) for f in files],
        "reports": reports,
        "pdf_errors": pdf_errors,
        "pdf_error": "; ".join(f"{language}: {error}" for language, error in pdf_errors.items()),
    }


def _next_archive_revision(directory: Path, base: str) -> int:
    """同时识别旧版单文件与新版分语言文件，旧修订永不覆盖。"""

    pattern = re.compile(
        rf"^{re.escape(base)}(?:_R(?P<revision>\d+))?(?:_(?:{'|'.join(messages.LANGUAGES)}))?\.md$"
    )
    revisions = []
    for path in directory.glob(f"{base}*.md"):
        match = pattern.fullmatch(path.name)
        if match:
            revisions.append(int(match.group("revision") or 1))
    return max(revisions, default=0) + 1


INDEX_HEADER = (
    "# OpenArm Mini 编号与归档索引\n\n"
    "由工作站归档时自动追加。编号规则：OAM + L/R + YYYYMMDD + 当日两位序号；作废号不复用。\n\n"
    "| 编号 | 臂侧 | 归档时间 | 结论 | 文档号 | 记录 |\n|---|---|---|---|---|---|\n"
)


def _append_index(archive_root: Path, robot_id: str, side: str, result: dict[str, Any], md_path: Path) -> None:
    index = archive_root / "编号与归档索引.md"
    if not index.is_file():
        index.write_text(INDEX_HEADER, encoding="utf-8")
    relative = md_path.relative_to(archive_root).as_posix()
    with index.open("a", encoding="utf-8") as handle:
        handle.write(
            f"| {robot_id} | {'L' if side == 'left' else 'R'} | "
            f"{datetime.now().astimezone().isoformat(timespec='seconds')} | {result['verdict']} | "
            f"{result['doc_id']} | [{md_path.name}]({relative}) |\n"
        )
