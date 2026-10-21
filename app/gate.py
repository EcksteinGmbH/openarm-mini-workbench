"""放行门与归档报告。

只从会话日志判定：页面状态、内存、人工转述都不算证据。规则：
- 每个必做项取**最近一次**记录；最近一次失败 → FAIL，没有记录 → MISSING。
- 校准之后的项（核对、断电核对、官方读数）必须晚于最近一次「已保存」的校准，
  否则那是对上一份校准文件的证据，不算。
- 结论：全部 PASS → PASS；任一 FAIL → FAIL；其余 → HOLD。
- 历史失败不删，进「异常与重测记录」。

SO-ARM101 的教训：判定只在前端算、归档脚本按默认值写「通过」，结果三台 Leader 的
质检节是「本次未采集」而结论仍是通过。这里缺项一律 HOLD。
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
from datetime import datetime
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


def build_report(
    robot_id: str,
    side: str,
    records: list[dict[str, Any]],
    motors: dict[str, dict[str, Any]],
    context: dict[str, Any],
    revision: int,
) -> tuple[list[Block], dict[str, Any]]:
    """报告固定用中文（与兄弟工站归档一致）。调用方负责把语言设成 zh。"""

    result = evaluate(records, motors)
    ordered = sorted(motors, key=lambda n: motors[n]["id"])
    code = "L" if side == "left" else "R"
    doc_id = f"OAM-{code}-BENCH-RESULT-{robot_id}-R{revision:02d}"
    s1_record = _latest(records, "checklist", lambda r: _request(r).get("stage") == "S1")
    operator = _result(s1_record).get("operator", "") if s1_record else ""
    blocks: list[Block] = [
        ("h1", f"OpenArm Mini 基础测试记录 · {robot_id}"),
        ("table", (["项", "内容"], [
            ["文档号", doc_id],
            ["编号 / 臂侧", f"{robot_id} / {'左臂 L' if side == 'left' else '右臂 R'}"],
            ["生成时间", datetime.now().astimezone().isoformat(timespec="seconds")],
            ["结论", result["verdict"]],
            ["操作员", operator or "-"],
            ["工作站版本", context.get("workstation_version", "-")],
            ["判据版本", crit.CRITERIA_VERSION],
            ["LeRobot", f"{context.get('lerobot', {}).get('version', '-')}（{context.get('lerobot', {}).get('source', '-')}）"],
            ["硬件依据", "pkooij/open-arms-mini README/BOM；lerobot teleoperators/openarm_mini"],
            ["供电", "7.5V（官方 BOM），整臂装配完成后测试"],
        ])),
        ("p", "本记录由工作站会话日志自动生成，实测数值未经人工转录。测试对象为装配完成的整臂，"
              "电机 ID 在装配完成后由本测试站逐颗写入。每个必做项取最近一次记录；"
              "校准之后的项只采信晚于最近一次已保存校准的记录。结论 PASS 需全部必做项通过，"
              "缺项为 HOLD，任一最近记录失败为 FAIL。全程未开启扭矩、未下发目标位置。"),
        ("h2", "1 放行判定"),
        ("table", (["阶段", "项目", "结果", "记录时间", "说明"],
                   [[i["stage"], i["label"], i["status"], i["at"] or "-", i["detail"] or ""]
                    for i in result["items"]])),
        ("h2", "2 S1 准备"),
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
            "是" if rescan and not _error(rescan) else "-",
            _fmt(cf.get("span")),
            _fmt(cf.get("voltage_v")),
            _fmt(baseline.get("firmware")),
            "通过" if cf.get("ok") else ("失败" if confirm else "无记录"),
        ])
    blocks += [
        ("h2", "3 S2 装配后逐颗写 ID"),
        ("p", "整臂装配完成后，驱动板每次只接一颗电机：广播确认总线上只有它 → 写该关节的 ID 与 1 Mbps"
              " → 断电 ≥5 秒复扫 → 只动这个关节确认读数随之变化。电机已装在关节上，ID 与位置一一对应。"),
        ("table", (["关节", "原 ID", "写入 ID", "断电复扫", "确认跨度", "电压 V", "固件", "确认"], rows)),
    ]

    # S3
    scan = _latest(records, "scan-all", lambda r: bool(_result(r).get("judged")))
    blocks.append(("h2", "4 S3 整臂电气与通信"))
    if scan:
        sr = _result(scan)
        blocks.append(("table", (
            ["关节", "ID", "位置", "电压 V", "温度 °C", "状态", "扭矩", "固件", "过压限值 V", "过温限值 °C",
             "Phase", "Max_Acc", "判定"],
            [[r.get("motor_title", r.get("motor_name")), _fmt(r.get("motor_id")),
              _fmt(r.get("present_position")), _fmt(r.get("voltage_v")), _fmt(r.get("temperature_c")),
              _fmt(r.get("status_raw")), _fmt(r.get("torque_enable")), _fmt(r.get("firmware")),
              _fmt(r.get("max_voltage_limit_v")), _fmt(r.get("max_temperature_limit_c")),
              _fmt(r.get("phase")), _fmt(r.get("max_acceleration")),
              "通过" if r.get("judged_ok") else "失败"] for r in sr.get("results", [])],
        )))
        blocks.append(("p", f"供电档位 {sr.get('hardware_profile') or '-'}；固件 {_fmt(sr.get('firmware_versions'))}；"
                            f"电压极差 {_fmt(sr.get('voltage_spread_v'))} V（记录项）。记录时间 {scan.get('recorded_at')}。"))
    else:
        blocks.append(("p", "无记录。"))
    comm = _latest(records, "comm-stability")
    if comm:
        cr = _result(comm)
        blocks.append(("p", f"通信稳定：{_fmt(cr.get('duration_sec'))} s，{_fmt(cr.get('rounds'))} 轮 / "
                            f"{_fmt(cr.get('reads'))} 次读，失败 {_fmt(cr.get('failures'))}。"))

    # S4
    rows = []
    for name in ordered:
        record = _latest(records, "joint-identity", lambda r, n=name: _request(r).get("motor") == n)
        rr = _result(record) if record else {}
        rows.append([motor_title(motors, name), _fmt(rr.get("target_span")),
                     motor_title(motors, rr["dominant"]) if rr.get("dominant") in motors else "-",
                     _fmt(rr.get("runner_up_span")),
                     "通过" if rr.get("ok") else ("失败" if record else "无记录")])
    blocks += [
        ("h2", "5 S4 关节身份与活动性"),
        ("table", (["被测关节", "跨度（计数）", "跨度最大的电机", "次大跨度", "判定"], rows)),
        ("p", f"判据：跨度最大的电机就是被测关节，且 ≥ 次大 × {crit.IDENTITY_DOMINANCE_RATIO:g}；"
              f"被测跨度 ≥ {crit.IDENTITY_MIN_SPAN_COUNTS} 计数。"),
    ]

    # S5
    blocks.append(("h2", "6 S5 官方校准与一致性核对"))
    saved = _latest(records, "calibration/finished", lambda r: _result(r).get("phase") == "saved")
    calibration = context.get("calibration") or (_result(saved).get("calibration") if saved else None)
    if isinstance(calibration, dict):
        blocks.append(("table", (
            ["关节", "id", "drive_mode", "homing_offset", "range_min", "range_max"],
            [[motor_title(motors, n) if n in motors else n, _fmt(v.get("id")), _fmt(v.get("drive_mode")),
              _fmt(v.get("homing_offset")), _fmt(v.get("range_min")), _fmt(v.get("range_max"))]
             for n, v in calibration.items() if isinstance(v, dict)],
        )))
    else:
        blocks.append(("p", "没有已保存的校准文件。"))
    if saved:
        blocks.append(("p", f"校准保存时间 {saved.get('recorded_at')}；命令 "
                            f"`{' '.join(_result(saved).get('command', []))}`。"))

    # S6
    blocks.append(("h2", "7 S6 官方驱动读数验证"))
    rows = []
    for record in records:
        if record.get("action") != "official-readout" or _error(record):
            continue
        rr = _result(record)
        values = "; ".join(f"{c['id']}={_fmt(c.get('value'))}" for c in rr.get("checks", []))
        rows.append([record.get("recorded_at", ""), rr.get("mode", ""), rr.get("motor_title", ""),
                     values, "通过" if rr.get("ok") else "失败"])
    blocks.append(("table", (["时间", "模式", "关节", "读数", "判定"], rows)) if rows else ("p", "无记录。"))
    last_readout = _latest(records, "official-readout", lambda r: bool(_result(r).get("delivery_command")))
    if last_readout:
        blocks += [("p", "交付给客户的遥操作命令（官方 README 的命令缺 --robot.* 与 --teleop.side，照抄跑不起来）："),
                   ("code", _result(last_readout)["delivery_command"])]

    blocks += [("h2", "8 S8 / S9"), ("p", "S8 与 follower 遥操作配对、S9 增强复测：未执行，不得解释为通过。")]

    # 判据表
    blocks += [
        ("h2", "9 判据表"),
        ("table", (["编号", "内容", "阈值", "依据", "参与判定"],
                   [[c["id"], messages.m(crit.criterion_key(c["id"])),
                     f"{_fmt(c['limit'])} {c.get('unit', '')}".strip(),
                     {"official": "官方", "spec": "规格", "derived": "推导", "tbc": "待定标"}[c["basis"]],
                     "是" if c["judged"] else "否（记录）"] for c in crit.CRITERIA])),
    ]
    rows = [[a["at"], a["action"], a["detail"][:300]] for a in anomalies(records)]
    blocks += [("h2", "10 异常与重测记录"),
               ("table", (["时间", "操作", "说明"], rows)) if rows else ("p", "无。")]
    blocks += [
        ("h2", "11 未验证项与边界"),
        ("p", "未覆盖：与 follower 的遥操作配对（S8）、增强复测（S9）、负载、耐久、重复精度、夹持力。"
              "待定标项（判据表中“否（记录）”）只记录不判定。"),
        ("h2", "12 签核"),
        ("table", (["角色", "姓名", "签字", "日期"],
                   [["测试员", operator or "", "", ""], ["复核", "", "", ""]])),
    ]
    return blocks, {**result, "doc_id": doc_id, "operator": operator}


def _checklist_table(record: dict[str, Any] | None, stage: str) -> Block:
    if record is None:
        return ("p", "无记录。")
    items = _result(record).get("items", {})
    rows = [[messages.m(f"checklist_{stage}_{k}"), "✔" if v else "✘"] for k, v in items.items()]
    return ("table", (["检查项", "结果"], rows + [["记录时间", record.get("recorded_at", "")]]))


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


def render_html(blocks: list[Block], title: str) -> str:
    parts = []
    for kind, content in blocks:
        if kind in ("h1", "h2"):
            parts.append(f"<{kind}>{html.escape(str(content))}</{kind}>")
        elif kind == "p":
            text = html.escape(str(content))
            text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
            parts.append(f"<p>{text}</p>")
        elif kind == "code":
            parts.append(f"<pre>{html.escape(str(content))}</pre>")
        elif kind == "table":
            head, rows = content
            body = "".join(
                "<tr>" + "".join(f"<td class='{_status_class(v)}'>{html.escape(str(v))}</td>" for v in row) + "</tr>"
                for row in rows
            )
            parts.append("<table><thead><tr>" + "".join(f"<th>{html.escape(str(h))}</th>" for h in head)
                         + f"</tr></thead><tbody>{body}</tbody></table>")
    style = (
        "body{font:13px/1.55 'Noto Sans CJK SC','Microsoft YaHei',sans-serif;margin:24px;color:#1d2733}"
        "h1{font-size:20px}h2{font-size:15px;margin-top:22px;border-bottom:1px solid #d6dee8}"
        "table{border-collapse:collapse;width:100%;margin:8px 0}"
        "th,td{border:1px solid #d6dee8;padding:4px 6px;text-align:left;vertical-align:top}"
        "th{background:#f1f5fa}pre{background:#f1f5fa;padding:8px;white-space:pre-wrap}"
        ".PASS{color:#1a7f4b;font-weight:600}.FAIL{color:#b3261e;font-weight:600}.MISSING{color:#a15c00}"
        "@page{size:A4;margin:14mm}"
    )
    return (f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
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
    base = f"{robot_id}_OpenArmMini_基础测试记录"
    revision = 1
    while (directory / (f"{base}.md" if revision == 1 else f"{base}_R{revision:02d}.md")).exists():
        revision += 1
    stem = base if revision == 1 else f"{base}_R{revision:02d}"
    suffix = "" if revision == 1 else f"_R{revision:02d}"

    blocks, result = build_report(robot_id, side, records, motors, context, revision)
    md_path = directory / f"{stem}.md"
    html_path = directory / f"{stem}.html"
    md_path.write_text(render_markdown(blocks), encoding="utf-8")
    html_path.write_text(render_html(blocks, result["doc_id"]), encoding="utf-8")
    pdf_path = directory / f"{stem}.pdf"
    pdf_error = print_pdf(html_path, pdf_path)
    if pdf_error:
        (directory / f"{stem}_pdf_error.txt").write_text(pdf_error, encoding="utf-8")

    files = [md_path, html_path] + ([pdf_path] if not pdf_error else [])
    if session_file.is_file():
        target = directory / f"{robot_id}_OpenArmMini_会话日志{suffix}.jsonl"
        shutil.copyfile(session_file, target)
        files.append(target)
    if calibration_file is not None and calibration_file.is_file():
        target = directory / f"{robot_id}_OpenArmMini_校准参数{suffix}.json"
        shutil.copyfile(calibration_file, target)
        files.append(target)
    gate_path = directory / f"{robot_id}_OpenArmMini_放行判定{suffix}.json"
    gate_path.write_text(json.dumps({**result, "context": context}, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    files.append(gate_path)

    _append_index(archive_root, robot_id, side, result, md_path)
    return {
        "verdict": result["verdict"],
        "doc_id": result["doc_id"],
        "revision": revision,
        "directory": str(directory),
        "files": [str(f) for f in files],
        "pdf_error": pdf_error,
    }


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
