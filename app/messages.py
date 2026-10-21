"""面向操作员的文案目录（中/英/德）。

只收**操作员会看到**的字符串。代码注释和 docstring 留中文——那是给维护者看的。

为什么放服务端：出错的时候恰恰最需要看懂，而错误信息大多产生在硬件层。
如果只翻页面骨架，德语操作员会在最要紧的时候读到一段中文。
页面每次请求带上 `lang`，服务端按该语言渲染，目录因此只有一份。

`{name}` 占位符在三种语言里必须完全一致，由 tests 锁住。
"""

from __future__ import annotations

import threading

LANGUAGES = ("zh", "en", "de")
DEFAULT_LANGUAGE = "zh"

_state = threading.local()


def set_language(lang: str) -> str:
    """设定当前请求的语言。ThreadingHTTPServer 每个请求一个线程，所以线程本地就够。"""

    resolved = lang if lang in LANGUAGES else DEFAULT_LANGUAGE
    _state.lang = resolved
    return resolved


def get_language() -> str:
    return getattr(_state, "lang", DEFAULT_LANGUAGE)


def m(key: str, **params: object) -> str:
    """渲染一条文案。缺语言回落中文，缺键回落键名本身——现场宁可看见键名，也不要空白。"""

    entry = MESSAGES.get(key)
    if entry is None:
        return key
    text = entry.get(get_language()) or entry[DEFAULT_LANGUAGE]
    if params:
        for name, value in params.items():
            text = text.replace("{" + name + "}", str(value))
    return text


def motor_label(motor_name: str) -> str:
    return m("motor_" + motor_name)


def field_name(field_key: str) -> str:
    return m("field_" + field_key) if field_key else m("field_unknown")


MESSAGES: dict[str, dict[str, str]] = {
    # ---------- 关节名 ----------
    "motor_joint_1": {"zh": "肩部旋转", "en": "Shoulder Pan", "de": "Schulterdrehung"},
    "motor_joint_2": {"zh": "肩部抬升", "en": "Shoulder Lift", "de": "Schulterhub"},
    "motor_joint_3": {"zh": "肩部翻滚", "en": "Shoulder Roll", "de": "Schulterrollung"},
    "motor_joint_4": {"zh": "肘部弯曲", "en": "Elbow Flex", "de": "Ellbogenbeugung"},
    "motor_joint_5": {"zh": "前臂旋转", "en": "Forearm Rotation", "de": "Unterarmdrehung"},
    "motor_joint_6": {"zh": "腕部俯仰", "en": "Wrist Flex", "de": "Handgelenkbeugung"},
    "motor_joint_7": {"zh": "腕部旋转", "en": "Wrist Roll", "de": "Handgelenkdrehung"},
    "motor_gripper": {"zh": "夹爪", "en": "Gripper", "de": "Greifer"},
    # ---------- 寄存器字段名 ----------
    "field_unknown": {"zh": "寄存器", "en": "register", "de": "Register"},
    "field_position": {"zh": "当前位置", "en": "present position", "de": "aktuelle Position"},
    "field_voltage": {"zh": "电压", "en": "voltage", "de": "Spannung"},
    "field_homing_offset": {"zh": "中点偏移", "en": "homing offset", "de": "Mittelpunkt-Offset"},
    "field_phase": {"zh": "Phase 寄存器", "en": "Phase register", "de": "Phase-Register"},
    "field_return_delay": {"zh": "响应延迟", "en": "return delay time", "de": "Antwortverzögerung"},
    "field_min_position": {"zh": "最小位置范围", "en": "min position limit", "de": "untere Positionsgrenze"},
    "field_max_position": {"zh": "最大位置范围", "en": "max position limit", "de": "obere Positionsgrenze"},
    "field_max_torque": {"zh": "最大扭矩", "en": "max torque limit", "de": "max. Drehmoment"},
    "field_p_coefficient": {"zh": "位置 P 系数", "en": "position P coefficient", "de": "Positions-P-Koeffizient"},
    "field_d_coefficient": {"zh": "位置 D 系数", "en": "position D coefficient", "de": "Positions-D-Koeffizient"},
    "field_i_coefficient": {"zh": "位置 I 系数", "en": "position I coefficient", "de": "Positions-I-Koeffizient"},
    "field_protection_current": {"zh": "保护电流", "en": "protection current", "de": "Schutzstrom"},
    "field_operating_mode": {"zh": "工作模式", "en": "operating mode", "de": "Betriebsmodus"},
    "field_overload_torque": {"zh": "过载扭矩", "en": "overload torque", "de": "Überlastdrehmoment"},
    "field_torque_enable": {"zh": "扭矩状态", "en": "torque enable", "de": "Drehmomentfreigabe"},
    "field_acceleration": {"zh": "加速度", "en": "acceleration", "de": "Beschleunigung"},
    "field_max_acceleration": {"zh": "最大加速度", "en": "max acceleration", "de": "max. Beschleunigung"},
    "field_temperature": {"zh": "温度", "en": "temperature", "de": "Temperatur"},
    "field_status": {"zh": "状态", "en": "status", "de": "Status"},
    "field_current": {"zh": "电流", "en": "present current", "de": "Strom"},
    "field_firmware": {"zh": "固件版本", "en": "firmware version", "de": "Firmware-Version"},
    "field_max_temperature_limit": {"zh": "过温保护限值", "en": "max temperature limit", "de": "Übertemperaturgrenze"},
    "field_max_voltage_limit": {"zh": "过压保护限值", "en": "max voltage limit", "de": "Überspannungsgrenze"},
    "field_min_voltage_limit": {"zh": "欠压保护限值", "en": "min voltage limit", "de": "Unterspannungsgrenze"},
    # ---------- SDK 与串口 ----------
    "sdk_missing": {
        "zh": "未安装 scservo_sdk。请先安装依赖：pip install -r requirements.txt",
        "en": "scservo_sdk is not installed. Install the dependencies first: pip install -r requirements.txt",
        "de": "scservo_sdk ist nicht installiert. Zuerst die Abhängigkeiten installieren: pip install -r requirements.txt",
    },
    "port_busy": {
        "zh": "串口正忙：另一项操作仍在使用串口。请等它结束后再试，不要连续点击。",
        "en": "The serial port is busy: another operation still holds it. Wait for it to finish instead of clicking again.",
        "de": "Der serielle Port ist belegt: Ein anderer Vorgang nutzt ihn noch. Bitte abwarten und nicht mehrfach klicken.",
    },
    "port_open_failed": {
        "zh": "无法打开串口：{port}",
        "en": "Could not open the serial port: {port}",
        "de": "Der serielle Port konnte nicht geöffnet werden: {port}",
    },
    # 下拉框里排在最前面的是 32 个内核虚拟串口占位，误选它们就会走到这条，
    # 所以这条必须直接说清该选哪个。
    "port_open_failed_detail": {
        "zh": "无法打开串口 {port}：{error}。请确认选的是 USB 适配器（条目以 /dev/serial/by-id/ 开头），而不是 /dev/ttyS0–ttyS31 这类内核虚拟串口；并确认适配器已插好、当前用户有串口读写权限。",
        "en": "Could not open the serial port {port}: {error}. Make sure you picked the USB adapter (its entry starts with /dev/serial/by-id/) and not a kernel placeholder such as /dev/ttyS0–ttyS31, that the adapter is plugged in, and that the current user may read and write serial ports.",
        "de": "Der serielle Port {port} konnte nicht geöffnet werden: {error}. Sicherstellen, dass der USB-Adapter gewählt ist (Eintrag beginnt mit /dev/serial/by-id/) und nicht ein Kernel-Platzhalter wie /dev/ttyS0–ttyS31, dass der Adapter eingesteckt ist und dass der aktuelle Benutzer serielle Ports lesen und schreiben darf.",
    },
    "set_baud_failed_detail": {
        "zh": "设置波特率 {baudrate} 失败：{error}",
        "en": "Failed to set the baud rate {baudrate}: {error}",
        "de": "Baudrate {baudrate} konnte nicht gesetzt werden: {error}",
    },
    "set_baud_failed": {
        "zh": "设置波特率失败：{baudrate}",
        "en": "Failed to set the baud rate: {baudrate}",
        "de": "Baudrate konnte nicht gesetzt werden: {baudrate}",
    },
    "reconnect_ok": {
        "zh": "{port} 串口重连成功。",
        "en": "Reconnected to {port}.",
        "de": "Verbindung zu {port} wiederhergestellt.",
    },
    # ---------- 串口自动识别 ----------
    "port_detect_none": {
        "zh": "未检测到 USB 串口适配器。请插好 Waveshare 板的 USB 线，然后点「重新识别」。内核给每个板载 UART 都建了 /dev/ttyS* 节点，那些不是适配器。",
        "en": "No USB serial adapter detected. Plug in the Waveshare board's USB cable, then press “Detect again”. The kernel creates a /dev/ttyS* node for every on-board UART; those are not adapters.",
        "de": "Kein USB-Seriell-Adapter erkannt. Das USB-Kabel des Waveshare-Boards einstecken und dann „Erneut erkennen“ drücken. Der Kernel erzeugt für jede Onboard-UART einen /dev/ttyS*-Knoten; das sind keine Adapter.",
    },
    "port_detect_one": {
        "zh": "已自动识别串口：{description}（序列号 {serial}）。",
        "en": "Serial port detected automatically: {description} (serial number {serial}).",
        "de": "Serieller Port automatisch erkannt: {description} (Seriennummer {serial}).",
    },
    "port_detect_many": {
        "zh": "检测到 {count} 个 USB 串口适配器，无法确定哪一个是本工位的。请在下拉框里选择。",
        "en": "{count} USB serial adapters were detected, so the right one cannot be decided automatically. Pick it from the list.",
        "de": "Es wurden {count} USB-Seriell-Adapter erkannt, der richtige lässt sich nicht automatisch bestimmen. Bitte aus der Liste wählen.",
    },
    "port_not_writable": {
        "zh": "{port} 当前用户没有读写权限，打开会失败。把用户加入 dialout 组后重新登录一次：sudo usermod -aG dialout $USER",
        "en": "The current user cannot read or write {port}, so opening it will fail. Add the user to the dialout group and log in again: sudo usermod -aG dialout $USER",
        "de": "Der aktuelle Benutzer kann {port} nicht lesen oder schreiben, das Öffnen wird fehlschlagen. Den Benutzer der Gruppe dialout hinzufügen und erneut anmelden: sudo usermod -aG dialout $USER",
    },
    # ---------- 电机识别 ----------
    "initial_params_invalid": {
        "zh": "给定初始参数无效：baudrate={baudrate}, id={id}, model={model}",
        "en": "The given initial parameters are invalid: baudrate={baudrate}, id={id}, model={model}",
        "de": "Die angegebenen Anfangsparameter sind ungültig: baudrate={baudrate}, id={id}, model={model}",
    },
    "wrong_model_found": {
        "zh": "在 baudrate={baudrate}, id={id} 发现型号 {model}，不是 STS3215（{expected}）。",
        "en": "Found model {model} at baudrate={baudrate}, id={id}, which is not an STS3215 ({expected}).",
        "de": "Bei baudrate={baudrate}, id={id} wurde Modell {model} gefunden, kein STS3215 ({expected}).",
    },
    "multiple_motors_on_bus": {
        "zh": "总线上检测到 {count} 颗电机（ID {ids}）。写 ID 这一步必须只连接一颗——多颗同时在线会一起被改成同一个 ID。请只留下当前这一颗，其余断开后重新扫描。",
        "en": "{count} motors answered on the bus (IDs {ids}). The ID-writing step requires exactly one connected motor — several online at once all end up with the same ID. Leave only the current motor connected and scan again.",
        "de": "{count} Motoren haben auf dem Bus geantwortet (IDs {ids}). Für das Schreiben der ID darf nur ein Motor angeschlossen sein — mehrere gleichzeitig erhalten alle dieselbe ID. Nur den aktuellen Motor angeschlossen lassen und erneut scannen.",
    },
    "no_motor_found_deep_hint": {
        "zh": "广播 ping 在 8 档波特率上都没有电机应答，请检查接线、电源和串口。若这颗电机确实不响应广播，可勾选「深度扫描」逐个试 ID（实测约 110 秒）。",
        "en": "No motor answered the broadcast ping on any of the 8 baud rates. Check the wiring, the power supply and the serial port. If this motor genuinely does not answer a broadcast, tick “deep scan” to probe IDs one by one (measured at about 110 seconds).",
        "de": "Kein Motor hat auf den Broadcast-Ping in einer der 8 Baudraten geantwortet. Verkabelung, Stromversorgung und seriellen Port prüfen. Falls dieser Motor wirklich nicht auf einen Broadcast antwortet, „Tiefenscan“ aktivieren, um die IDs einzeln zu prüfen (gemessen etwa 110 Sekunden).",
    },
    "no_motor_found": {
        "zh": "未找到可通信的 STS3215 电机，请检查接线、电源和串口。",
        "en": "No reachable STS3215 motor was found. Check the wiring, the power supply and the serial port.",
        "de": "Kein erreichbarer STS3215-Motor gefunden. Verkabelung, Stromversorgung und seriellen Port prüfen.",
    },
    "unknown_motor": {
        "zh": "未知电机：{motor}",
        "en": "Unknown motor: {motor}",
        "de": "Unbekannter Motor: {motor}",
    },
    "snapshot_model_mismatch": {
        "zh": "ID {id}：读到型号 {model}，期望 {expected}。",
        "en": "ID {id}: read model {model}, expected {expected}.",
        "de": "ID {id}: Modell {model} gelesen, erwartet {expected}.",
    },
    "model_mismatch_at_id": {
        "zh": "未在 ID {id} 读到 STS3215，读取到 model={model}。请确认该电机已完成 ID 写入且接线正常。",
        "en": "No STS3215 answered at ID {id} (read model={model}). Make sure this motor has its ID written and is wired correctly.",
        "de": "An ID {id} hat kein STS3215 geantwortet (model={model}). Prüfen, ob die ID geschrieben wurde und die Verkabelung stimmt.",
    },
    # ---------- 寄存器读写失败 ----------
    "read_fail": {
        "zh": "读取{field}失败：comm={comm}, error={error}",
        "en": "Failed to read {field}: comm={comm}, error={error}",
        "de": "{field} konnte nicht gelesen werden: comm={comm}, error={error}",
    },
    "disable_torque_failed": {
        "zh": "关闭扭矩失败：comm={comm}, error={error}",
        "en": "Failed to disable torque: comm={comm}, error={error}",
        "de": "Drehmoment konnte nicht deaktiviert werden: comm={comm}, error={error}",
    },
    "write_register_failed": {
        "zh": "写寄存器失败：addr={address}, comm={comm}, error={error}",
        "en": "Failed to write register: addr={address}, comm={comm}, error={error}",
        "de": "Register konnte nicht geschrieben werden: addr={address}, comm={comm}, error={error}",
    },
    "write_id_failed": {
        "zh": "写入 ID 失败：comm={comm}, error={error}",
        "en": "Failed to write the ID: comm={comm}, error={error}",
        "de": "ID konnte nicht geschrieben werden: comm={comm}, error={error}",
    },
    "write_id_failed_detail": {
        "zh": "写入 ID 失败：{error}",
        "en": "Failed to write the ID: {error}",
        "de": "ID konnte nicht geschrieben werden: {error}",
    },
    "unsupported_baudrate": {
        "zh": "不支持的波特率：{baudrate}",
        "en": "Unsupported baud rate: {baudrate}",
        "de": "Nicht unterstützte Baudrate: {baudrate}",
    },
    "write_baud_failed": {
        "zh": "写入波特率失败：comm={comm}, error={error}",
        "en": "Failed to write the baud rate: comm={comm}, error={error}",
        "de": "Baudrate konnte nicht geschrieben werden: comm={comm}, error={error}",
    },
    # ---------- 供电档位 ----------
    "profile_unset": {
        "zh": "未指定供电档位",
        "en": "no supply profile selected",
        "de": "kein Versorgungsprofil gewählt",
    },
    "voltage_over_rated": {
        "zh": "实测电压 {measured}V 超过电机额定 {rated}V，可能损坏电机。请立即关闭 OUTPUT 并核对电源设置与供电档位。",
        "en": "The measured {measured}V exceeds the motor rating of {rated}V and can destroy the motors. Switch OUTPUT off now and check the supply setting against the selected profile.",
        "de": "Die gemessenen {measured}V übersteigen die Motornennspannung von {rated}V und können die Motoren zerstören. OUTPUT sofort ausschalten und Netzteileinstellung mit dem gewählten Profil vergleichen.",
    },
    "voltage_profile_mismatch": {
        "zh": "实测电压 {measured}V 与所选档位期望的 {expected}V 相差 {deviation}V。请确认电源设置和档位是否一致后重试。",
        "en": "The measured {measured}V differs from the {expected}V this profile expects by {deviation}V. Check that the supply setting and the profile agree, then retry.",
        "de": "Die gemessenen {measured}V weichen um {deviation}V von den für dieses Profil erwarteten {expected}V ab. Netzteileinstellung und Profil abgleichen und erneut versuchen.",
    },
    "profile_field_label": {"zh": "7.5V（官方 BOM）", "en": "7.5 V (official BOM)", "de": "7,5 V (offizielle Stückliste)"},
    "profile_field_usage": {
        "zh": "装配完成后的整臂测试、官方校准与读数",
        "en": "full-arm tests after assembly, official calibration and readout",
        "de": "Gesamtarm-Prüfungen nach der Montage, offizielle Kalibrierung und Auslesen",
    },
    # ---------- 扫描与写 ID ----------
    "scan_found": {
        "zh": "识别到电机 ID={id}，波特率 {baudrate}。",
        "en": "Found a motor with ID={id} at {baudrate} baud.",
        "de": "Motor mit ID={id} bei {baudrate} Baud erkannt.",
    },
    "scan_found_known": {
        "zh": "识别到电机 ID={id}，对应 {title}。",
        "en": "Found a motor with ID={id}, which is {title}.",
        "de": "Motor mit ID={id} erkannt, das ist {title}.",
    },
    "baud_not_switched": {
        "zh": "ID 写入成功，但波特率未切到 1000000。请重试写入。",
        "en": "The ID was written but the baud rate did not switch to 1000000. Retry the write.",
        "de": "Die ID wurde geschrieben, aber die Baudrate wechselte nicht auf 1000000. Schreibvorgang wiederholen.",
    },
    "baud_verify_failed": {
        "zh": "ID 写入成功，但波特率校验失败。请重试写入。",
        "en": "The ID was written but the baud rate could not be verified. Retry the write.",
        "de": "Die ID wurde geschrieben, aber die Baudrate konnte nicht verifiziert werden. Schreibvorgang wiederholen.",
    },
    "verify_unreachable": {
        "zh": "写入后无法在目标 ID 上完成校验，请检查接线与供电。",
        "en": "The motor could not be verified on the target ID after the write. Check the wiring and the power supply.",
        "de": "Nach dem Schreiben war der Motor unter der Ziel-ID nicht verifizierbar. Verkabelung und Stromversorgung prüfen.",
    },
    "init_success": {
        "zh": "{title} 已写入 ID={id}，波特率 {baudrate}。本次上电周期校验通过；请断电 5 秒后重新上电复扫，确认已永久保存。",
        "en": "{title} now has ID={id} at {baudrate} baud. Verified for this power cycle; power down for 5 seconds, power up and rescan to confirm it was stored permanently.",
        "de": "{title} hat jetzt ID={id} bei {baudrate} Baud. Für diesen Einschaltzyklus verifiziert; 5 Sekunden ausschalten, wieder einschalten und erneut scannen, um die dauerhafte Speicherung zu bestätigen.",
    },
    # ---------- 只读反馈测试 ----------
    "feedback_no_movement": {
        "zh": "{seconds} 秒内位移不足 {counts} 计数。请确认测试期间确实手动摆动了该关节；若已摆动仍无读数变化，检查三芯线、供电和电机是否被结构卡死。",
        "en": "Less than {counts} counts of movement in {seconds} s. Make sure the joint really was moved by hand during the test; if it was and the reading stayed flat, check the 3-pin cable, the supply and whether the joint is mechanically jammed.",
        "de": "Weniger als {counts} Zählschritte Bewegung in {seconds} s. Sicherstellen, dass das Gelenk während des Tests wirklich von Hand bewegt wurde; falls doch und der Messwert unverändert blieb, 3-poliges Kabel, Versorgung und mechanische Blockierung prüfen.",
    },
    # ---------- 校准预检 ----------
    "precheck_multiturn": {
        "zh": "电机报出的位置 {present} 超过一圈（{max}），属于多圈累计读数，官方校准会因中点偏移超限而中止。关闭 OUTPUT 超过 5 秒后重新上电，再重新预检。",
        "en": "The motor reports position {present}, beyond one turn ({max}). That is a multi-turn accumulated reading and the official calibration will abort on an out-of-range homing offset. Switch OUTPUT off for more than 5 seconds, power up and precheck again.",
        "de": "Der Motor meldet Position {present}, mehr als eine Umdrehung ({max}). Das ist ein mehrfach akkumulierter Wert, und die offizielle Kalibrierung bricht wegen eines unzulässigen Mittelpunkt-Offsets ab. OUTPUT länger als 5 Sekunden ausschalten, wieder einschalten und erneut prüfen.",
    },
    "precheck_offset_overflow": {
        "zh": "该关节停在机械位置 {actual}，校准需要写入的中点偏移为 {offset}，超过电机允许的 ±{limit}。关闭 OUTPUT 超过 5 秒后重新上电，再重新预检。",
        "en": "This joint sits at mechanical position {actual}; calibration would have to write a homing offset of {offset}, beyond the ±{limit} the motor allows. Switch OUTPUT off for more than 5 seconds, power up and precheck again.",
        "de": "Dieses Gelenk steht an der mechanischen Position {actual}; die Kalibrierung müsste einen Mittelpunkt-Offset von {offset} schreiben, mehr als die vom Motor erlaubten ±{limit}. OUTPUT länger als 5 Sekunden ausschalten, wieder einschalten und erneut prüfen.",
    },
    "precheck_note": {
        "zh": "零位姿态要求：整臂自然下垂、夹爪闭合。关节量程由驱动写死为整圈，不需要停放在行程中点。",
        "en": "Zero pose: the whole arm hanging straight down with the gripper closed. Joint ranges are hardcoded to a full turn by the driver, so joints need not be parked at the middle of their travel.",
        "de": "Nullstellung: der gesamte Arm hängt gerade nach unten, Greifer geschlossen. Die Gelenkbereiche sind im Treiber auf eine ganze Umdrehung festgelegt, die Gelenke müssen also nicht in der Wegmitte stehen.",
    },
    # ---------- 编号 ----------
    "serial_hint": {
        "zh": "OAM + L(左臂)/R(右臂) + YYYYMMDD + 两位当日序号，例如 OAML2026092801",
        "en": "OAM + L (left arm) / R (right arm) + YYYYMMDD + two-digit sequence for the day, e.g. OAML2026092801",
        "de": "OAM + L (linker Arm) / R (rechter Arm) + YYYYMMDD + zweistellige Tagesnummer, z. B. OAML2026092801",
    },
    "serial_malformed": {
        "zh": "机械臂编号格式不合规：{robot_id}。应为 {hint}",
        "en": "Malformed arm serial: {robot_id}. Expected {hint}",
        "de": "Ungültige Arm-Seriennummer: {robot_id}. Erwartet {hint}",
    },
    "side_invalid": {
        "zh": "臂侧必须是 left 或 right。",
        "en": "The side must be either left or right.",
        "de": "Die Seite muss left oder right sein.",
    },
    "serial_exhausted": {
        "zh": "{day} 当日 {code} 侧编号已用满 99 个。",
        "en": "All 99 serials for side {code} on {day} are already used.",
        "de": "Alle 99 Seriennummern für Seite {code} am {day} sind bereits belegt.",
    },
    # ---------- 一致性核对 ----------
    "calibration_file_missing": {
        "zh": "未找到校准文件：{path}",
        "en": "Calibration file not found: {path}",
        "de": "Kalibrierdatei nicht gefunden: {path}",
    },
    "calibration_file_invalid": {
        "zh": "校准文件格式无效。",
        "en": "The calibration file is not in a valid format.",
        "de": "Die Kalibrierdatei hat kein gültiges Format.",
    },
    "motor_read_failed": {"zh": "电机只读失败", "en": "read-only access to the motor failed", "de": "Nur-Lese-Zugriff auf den Motor fehlgeschlagen"},
    "calibration_missing_joint": {"zh": "校准文件缺少该轴", "en": "the calibration file has no entry for this joint", "de": "die Kalibrierdatei enthält dieses Gelenk nicht"},
    "driver_range_mismatch": {
        "zh": "校准文件量程 [{file_min}, {file_max}] 不是 openarm_mini 驱动写死的 [{min}, {max}]，这份文件可能由别的机型生成。",
        "en": "The calibration file range [{file_min}, {file_max}] is not the [{min}, {max}] the openarm_mini driver hardcodes; this file may have been produced for a different arm type.",
        "de": "Der Bereich [{file_min}, {file_max}] in der Kalibrierdatei entspricht nicht den vom openarm_mini-Treiber festgelegten [{min}, {max}]; die Datei stammt möglicherweise von einem anderen Armtyp.",
    },
    "fields_inconsistent": {
        "zh": "不一致字段：{fields}",
        "en": "Inconsistent fields: {fields}",
        "de": "Abweichende Felder: {fields}",
    },
    "runtime_fields_pending": {
        "zh": "持久参数一致；运行期字段 {fields} 待 LeRobot 连接时重写，断电后归零属正常。",
        "en": "The persisted parameters agree; the runtime fields {fields} are rewritten when LeRobot connects, so reading zero after a power cycle is normal.",
        "de": "Die dauerhaft gespeicherten Parameter stimmen; die Laufzeitfelder {fields} werden beim Verbinden von LeRobot neu geschrieben, ein Nullwert nach dem Aus- und Einschalten ist normal.",
    },
    # ---------- 校准子进程 ----------
    "calibrate_not_found": {
        "zh": "未找到 lerobot-calibrate 可执行文件，无法启动官方校准。请确认已安装带 openarm_mini 驱动的 LeRobot 环境。",
        "en": "The lerobot-calibrate executable was not found, so the official calibration cannot start. Make sure a LeRobot environment that includes the openarm_mini driver is installed.",
        "de": "Die ausführbare Datei lerobot-calibrate wurde nicht gefunden, die offizielle Kalibrierung kann nicht starten. Sicherstellen, dass eine LeRobot-Umgebung mit dem openarm_mini-Treiber installiert ist.",
    },
    "lerobot_source_project": {
        "zh": "项目内 {name}/",
        "en": "project-local {name}/",
        "de": "projektlokal {name}/",
    },
    "lerobot_source_shared": {
        "zh": "共享目录 {name}/（其他工作站也会扫描这里）",
        "en": "shared directory {name}/ (other workstations scan it too)",
        "de": "gemeinsames Verzeichnis {name}/ (andere Arbeitsplätze durchsuchen es ebenfalls)",
    },
    "lerobot_override_missing": {
        "zh": "指定的 lerobot-calibrate 不存在或不可执行：{path}。检查 --lerobot-calibrate 参数或 {env} 环境变量。",
        "en": "The specified lerobot-calibrate does not exist or is not executable: {path}. Check the --lerobot-calibrate argument or the {env} environment variable.",
        "de": "Das angegebene lerobot-calibrate existiert nicht oder ist nicht ausführbar: {path}. Das Argument --lerobot-calibrate oder die Umgebungsvariable {env} prüfen.",
    },
    "calibrate_no_driver": {
        "zh": "{executable} 所在的 LeRobot 环境没有 openarm_mini 驱动，启动了也只会被 argparse 以「invalid choice」顶回来。请升级到含该驱动的 LeRobot，或把工作站指向装有它的虚拟环境。",
        "en": "The LeRobot environment behind {executable} has no openarm_mini driver; starting it would only come back as an argparse “invalid choice”. Upgrade to a LeRobot that includes the driver, or point the workstation at the virtualenv that has it.",
        "de": "Die LeRobot-Umgebung hinter {executable} enthält keinen openarm_mini-Treiber; ein Start würde nur mit einem argparse-„invalid choice“ zurückkommen. Auf ein LeRobot mit diesem Treiber aktualisieren oder den Arbeitsplatz auf die passende virtuelle Umgebung verweisen.",
    },
    "calibrate_dual_arm_generation": {
        "zh": "{executable} 装的是**已发布的双臂版** openarm_mini 驱动：它的配置只有 port_right / port_left，不接受 --teleop.port，校准时必须两条臂同时接上，校准文件的键名还带 right_ / left_ 前缀。官方硬件 README 写的是单臂形式（--teleop.port），需要 LeRobot ≥ 0.6.1（PyPI 0.4.4 / 0.5.0 是双臂版）。请在该环境里装 lerobot[feetech]==0.6.1，或改用支持单臂驱动的环境。",
        "en": "{executable} has the released dual-arm generation of the openarm_mini driver: its config only offers port_right / port_left, it does not accept --teleop.port, calibration requires both arms connected at once, and the calibration keys carry right_ / left_ prefixes. The official hardware README documents the single-arm form (--teleop.port), which needs LeRobot ≥ 0.6.1 (PyPI 0.4.4 / 0.5.0 are dual-arm). Install lerobot[feetech]==0.6.1 into that environment, or point the workstation at one that has the single-arm driver.",
        "de": "{executable} enthält die veröffentlichte Zweiarm-Generation des openarm_mini-Treibers: Seine Konfiguration bietet nur port_right / port_left, akzeptiert kein --teleop.port, die Kalibrierung setzt beide Arme gleichzeitig voraus, und die Kalibrierschlüssel tragen die Präfixe right_ / left_. Das offizielle Hardware-README beschreibt die Einarm-Form (--teleop.port), die LeRobot ≥ 0.6.1 benötigt (PyPI 0.4.4 / 0.5.0 sind Zweiarm-Versionen). lerobot[feetech]==0.6.1 in diese Umgebung installieren oder den Arbeitsplatz auf eine Umgebung mit dem Einarm-Treiber verweisen.",
    },
    "calibration_already_running": {
        "zh": "已有校准进程在运行，请先完成或中止。",
        "en": "A calibration process is already running. Finish or abort it first.",
        "de": "Ein Kalibriervorgang läuft bereits. Diesen zuerst abschließen oder abbrechen.",
    },
    "calibration_not_running": {
        "zh": "没有正在运行的校准进程。",
        "en": "No calibration process is running.",
        "de": "Es läuft kein Kalibriervorgang.",
    },
    "calibration_aborted": {
        "zh": "校准进程已中止；本次未保存的参数不得使用。",
        "en": "The calibration process was aborted; the unsaved parameters from this run must not be used.",
        "de": "Der Kalibriervorgang wurde abgebrochen; die nicht gespeicherten Parameter dieses Durchlaufs dürfen nicht verwendet werden.",
    },
    # ---------- 请求层 ----------
    "need_port": {
        "zh": "请先选择串口。",
        "en": "Select a serial port first.",
        "de": "Zuerst einen seriellen Port wählen.",
    },
    "unknown_endpoint": {
        "zh": "未知接口：{path}",
        "en": "Unknown endpoint: {path}",
        "de": "Unbekannter Endpunkt: {path}",
    },
    # ---------- 校准阶段提示 ----------
    "prompt_existing_title": {
        "zh": "已存在同编号的校准文件",
        "en": "A calibration file already exists for this serial",
        "de": "Für diese Seriennummer existiert bereits eine Kalibrierdatei",
    },
    "prompt_existing_detail": {
        "zh": "直接回车等于沿用旧文件，官方程序什么都不会测。要重新校准请选覆盖。",
        "en": "A bare ENTER keeps the old file and the official program measures nothing. Choose overwrite to calibrate again.",
        "de": "Ein reines ENTER behält die alte Datei, das offizielle Programm misst dann nichts. Zum erneuten Kalibrieren Überschreiben wählen.",
    },
    "prompt_existing_action": {
        "zh": "重新校准（覆盖旧文件）",
        "en": "Recalibrate (overwrite the old file)",
        "de": "Neu kalibrieren (alte Datei überschreiben)",
    },
    "prompt_zero_title": {"zh": "零位姿态", "en": "Zero pose", "de": "Nullstellung"},
    "prompt_zero_detail": {
        "zh": "把整条臂自然下垂、夹爪闭合，扶稳后再确认。此处写入 homing = 当前位置 − 2047。",
        "en": "Let the whole arm hang straight down with the gripper closed, steady it, then confirm. This writes homing = present position − 2047.",
        "de": "Den gesamten Arm gerade nach unten hängen lassen, Greifer geschlossen, festhalten und dann bestätigen. Hier wird homing = aktuelle Position − 2047 geschrieben.",
    },
    "prompt_zero_action": {
        "zh": "零位已摆好，继续",
        "en": "Zero pose is set, continue",
        "de": "Nullstellung steht, weiter",
    },
    "prompt_gripper_closed_title": {
        "zh": "夹爪完全闭合",
        "en": "Gripper fully closed",
        "de": "Greifer vollständig geschlossen",
    },
    "prompt_gripper_closed_detail": {
        "zh": "把夹爪扣到底，记录闭合位置。这一步决定夹爪 0% 对应的计数。",
        "en": "Squeeze the gripper all the way shut to record the closed position. This step fixes the count that means 0%.",
        "de": "Den Greifer vollständig zudrücken, um die geschlossene Position aufzunehmen. Dieser Schritt legt den Zählwert für 0% fest.",
    },
    "prompt_gripper_closed_action": {
        "zh": "夹爪已闭合，记录",
        "en": "Gripper is closed, record it",
        "de": "Greifer ist geschlossen, aufnehmen",
    },
    "prompt_gripper_open_title": {
        "zh": "夹爪完全张开",
        "en": "Gripper fully open",
        "de": "Greifer vollständig geöffnet",
    },
    "prompt_gripper_open_detail": {
        "zh": "把扳机松到底，记录张开位置。这一步决定夹爪 100% 对应的计数。",
        "en": "Release the trigger all the way to record the open position. This step fixes the count that means 100%.",
        "de": "Den Abzug vollständig loslassen, um die geöffnete Position aufzunehmen. Dieser Schritt legt den Zählwert für 100% fest.",
    },
    "prompt_gripper_open_action": {
        "zh": "夹爪已张开，记录",
        "en": "Gripper is open, record it",
        "de": "Greifer ist geöffnet, aufnehmen",
    },
    # ---------- 失败处置 ----------
    "remedy_offset_overflow": {
        "zh": "中点偏移超出 ±2047：断电 5 秒后重新上电，让多圈累计读数回到单圈内，再重跑预检。",
        "en": "The homing offset exceeds ±2047: power down for 5 seconds and power up so the multi-turn reading returns inside one turn, then run the precheck again.",
        "de": "Der Mittelpunkt-Offset übersteigt ±2047: 5 Sekunden ausschalten und wieder einschalten, damit der mehrfach akkumulierte Wert in eine Umdrehung zurückfällt, dann die Vorprüfung wiederholen.",
    },
    "remedy_port_unavailable": {
        "zh": "串口打不开：确认没有别的程序占用串口（包括本页其他操作），必要时拔插适配器。",
        "en": "The serial port could not be opened: make sure no other program holds it (including other operations on this page), and re-plug the adapter if needed.",
        "de": "Der serielle Port konnte nicht geöffnet werden: sicherstellen, dass kein anderes Programm ihn belegt (auch keine anderen Vorgänge auf dieser Seite), notfalls den Adapter neu einstecken.",
    },
    "remedy_motor_mismatch": {
        "zh": "电机与预期不符：用八轴只读扫描确认 ID 1–8 齐全且都是 STS3215，检查供电和三芯线。",
        "en": "The motors do not match what was expected: use the eight-axis read-only scan to confirm IDs 1–8 are all present and all STS3215, and check the supply and the 3-pin cables.",
        "de": "Die Motoren entsprechen nicht der Erwartung: mit dem Nur-Lese-Scan aller acht Achsen prüfen, ob die IDs 1–8 vollständig und alle STS3215 sind, und Versorgung sowie 3-polige Kabel kontrollieren.",
    },
    "remedy_reused_existing": {
        "zh": "本次沿用了旧校准文件，没有测量任何数据：重来一次，在沿用提示处点「重新校准（覆盖旧文件）」。",
        "en": "This run kept the old calibration file and measured nothing: start over and choose “Recalibrate (overwrite the old file)” at the reuse prompt.",
        "de": "Dieser Durchlauf hat die alte Kalibrierdatei behalten und nichts gemessen: neu beginnen und bei der Abfrage „Neu kalibrieren (alte Datei überschreiben)“ wählen.",
    },
    "remedy_finished_unsaved": {
        "zh": "退出码 0 但没有保存校准：看输出确认停在哪一步，然后重跑整个校准。",
        "en": "Exit code 0 but no calibration was saved: check the output for where it stopped, then run the whole calibration again.",
        "de": "Exit-Code 0, aber keine Kalibrierung gespeichert: in der Ausgabe nachsehen, wo es abgebrochen ist, und die gesamte Kalibrierung erneut ausführen.",
    },
    "remedy_teleop_type_unknown": {
        "zh": "这套 LeRobot 没有 openarm_mini 驱动：它是较新版本才加入的。请升级到含该驱动的 LeRobot（pip install -U 'lerobot[feetech]'），或把工作站指向装有它的那个虚拟环境。",
        "en": "This LeRobot has no openarm_mini driver: it was only added in a newer version. Upgrade to a LeRobot that includes it (pip install -U 'lerobot[feetech]'), or point the workstation at the virtualenv that has it.",
        "de": "Dieses LeRobot hat keinen openarm_mini-Treiber: er wurde erst in einer neueren Version ergänzt. Auf ein LeRobot mit diesem Treiber aktualisieren (pip install -U 'lerobot[feetech]') oder den Arbeitsplatz auf die passende virtuelle Umgebung verweisen.",
    },
    # ---------- 出厂测试：装配后整臂测试 ----------
    "comm_failures": {
        "zh": "通信稳定未通过：{rounds} 轮读取中失败 {failures} 次。检查三芯线、菊花链接头与供电，再测一次。",
        "en": "Communication stability failed: {failures} failed reads in {rounds} rounds. Check the 3-pin cables, the daisy-chain connectors and the supply, then test again.",
        "de": "Kommunikationsstabilität nicht bestanden: {failures} Lesefehler in {rounds} Runden. 3-polige Kabel, Daisy-Chain-Stecker und Versorgung prüfen, dann erneut testen.",
    },
    "identity_failed": {
        "zh": "关节身份未通过：要求只动 {title}，但跨度最大的是 {dominant}（被测跨度 {span}，次大 {runner_up}）。若确实只动了这个关节，说明电机装错位或线接错。",
        "en": "Joint identity failed: only {title} was to move, but the largest travel was on {dominant} (tested travel {span}, runner-up {runner_up}). If only this joint was moved, a motor is mounted in the wrong place or wired wrongly.",
        "de": "Gelenkidentität nicht bestanden: Nur {title} sollte bewegt werden, der größte Weg lag aber bei {dominant} (Prüfweg {span}, zweitgrößter {runner_up}). Wurde wirklich nur dieses Gelenk bewegt, sitzt ein Motor an der falschen Stelle oder ist falsch verkabelt.",
    },
    "readout_needs_single_arm": {
        "zh": "{executable} 不是单臂版 openarm_mini 驱动，无法做官方驱动读数。需要 LeRobot ≥ 0.6.1。",
        "en": "{executable} does not carry the single-arm openarm_mini driver, so the official readout cannot run. LeRobot ≥ 0.6.1 is required.",
        "de": "{executable} enthält nicht den Einarm-Treiber openarm_mini, daher ist das offizielle Auslesen nicht möglich. LeRobot ≥ 0.6.1 ist erforderlich.",
    },
    "readout_failed": {
        "zh": "官方驱动读数失败（{code}）：{detail}",
        "en": "Official driver readout failed ({code}): {detail}",
        "de": "Offizielles Treiber-Auslesen fehlgeschlagen ({code}): {detail}",
    },
    "calibration_stale_confirm": {
        "zh": "这个提示已经答过或已经过去了，请等页面刷新到下一个提示再点。",
        "en": "This prompt has already been answered or has passed; wait for the page to show the next prompt.",
        "de": "Diese Abfrage wurde bereits beantwortet oder ist vorbei; warten, bis die Seite die nächste Abfrage zeigt.",
    },
    "checklist_need_operator": {
        "zh": "请填写操作员姓名。",
        "en": "Please enter the operator name.",
        "de": "Bitte den Namen des Bedieners eintragen.",
    },
    "checklist_missing": {
        "zh": "以下项未确认：{items}",
        "en": "Not confirmed: {items}",
        "de": "Nicht bestätigt: {items}",
    },
    "checklist_S1_power_supply": {
        "zh": "电源 7.50V / ≥2A（官方 BOM），红正黑负、OCP 关闭、OUTPUT 打开",
        "en": "Supply 7.50 V / ≥2 A (official BOM), red positive, black negative, OCP off, OUTPUT on",
        "de": "Netzteil 7,50 V / ≥2 A (offizielle Stückliste), rot plus, schwarz minus, OCP aus, OUTPUT an",
    },
    "checklist_S1_fixture_post": {
        "zh": "整臂已装配完成，固定在竖直立柱上可自然下垂（同官方照片）",
        "en": "The arm is fully assembled and mounted on a vertical post so it hangs freely (as in the official photo)",
        "de": "Der Arm ist vollständig montiert und hängt frei an einer senkrechten Säule (wie auf dem offiziellen Foto)",
    },
    "checklist_S1_daisy_chain": {
        "zh": "Waveshare 板按 1→8 菊花链接好，USB 已连到本机",
        "en": "Waveshare board wired as daisy chain 1→8, USB connected to this computer",
        "de": "Waveshare-Platine als Daisy-Chain 1→8 verkabelt, USB mit diesem Rechner verbunden",
    },
    "checklist_S1_waveshare_jumper": {
        "zh": "Waveshare 驱动板跳线在 B 档",
        "en": "Waveshare driver board jumper set to B",
        "de": "Jumper der Waveshare-Treiberplatine auf B",
    },
    "checklist_S1_parts_side": {
        "zh": "夹爪件（J8 L/R、扳机 L/R、J8 holder L/R）与编号的左右臂一致",
        "en": "Gripper parts (J8 L/R, trigger L/R, J8 holder L/R) match the arm side in the serial",
        "de": "Greiferteile (J8 L/R, Abzug L/R, J8-Halter L/R) passen zur Armseite in der Seriennummer",
    },
    "gate_checklist": {
        "zh": "准备检查表",
        "en": "Preparation checklist",
        "de": "Vorbereitungs-Checkliste",
    },
    "gate_detail_scan": {
        "zh": "{passed}/{total} 通过",
        "en": "{passed}/{total} passed",
        "de": "{passed}/{total} bestanden",
    },
    "gate_detail_comm": {
        "zh": "{rounds} 轮，失败 {failures}",
        "en": "{rounds} rounds, {failures} failures",
        "de": "{rounds} Runden, {failures} Fehler",
    },
    "gate_detail_phase": {
        "zh": "结局：{phase}",
        "en": "outcome: {phase}",
        "de": "Ergebnis: {phase}",
    },
    "gate_detail_need_field_profile": {
        "zh": "须在 7.5V 档下扫描",
        "en": "Must be scanned with the 7.5 V profile",
        "de": "Muss mit dem 7,5-V-Profil gescannt werden",
    },
    "gate_scan": {
        "zh": "八轴电气判定",
        "en": "Eight-axis electrical check",
        "de": "Elektrische Prüfung aller acht Achsen",
    },
    "gate_comm": {
        "zh": "通信稳定",
        "en": "Communication stability",
        "de": "Kommunikationsstabilität",
    },
    "gate_identity": {
        "zh": "{title} 关节身份",
        "en": "{title} joint identity",
        "de": "{title} Gelenkidentität",
    },
    "gate_precheck": {
        "zh": "校准预检",
        "en": "Calibration precheck",
        "de": "Kalibriervorprüfung",
    },
    "gate_saved": {
        "zh": "官方校准已保存",
        "en": "Official calibration saved",
        "de": "Offizielle Kalibrierung gespeichert",
    },
    "gate_verify": {
        "zh": "一致性核对",
        "en": "Consistency check",
        "de": "Konsistenzprüfung",
    },
    "gate_verify_power_cycled": {
        "zh": "断电后再核对",
        "en": "Consistency check after power cycle",
        "de": "Konsistenzprüfung nach Aus/Ein",
    },
    "gate_readout_zero": {
        "zh": "官方读数：零位",
        "en": "Official readout: zero pose",
        "de": "Offizielles Auslesen: Nullstellung",
    },
    "gate_readout_gripper_open": {
        "zh": "官方读数：夹爪张开",
        "en": "Official readout: gripper open",
        "de": "Offizielles Auslesen: Greifer offen",
    },
    "gate_readout_sweep": {
        "zh": "官方读数：{title} 扫动",
        "en": "Official readout: {title} sweep",
        "de": "Offizielles Auslesen: {title} schwenken",
    },
    "crit_S1_checklist": {
        "zh": "准备检查表全部确认，记录操作员",
        "en": "Preparation checklist fully confirmed, operator recorded",
        "de": "Vorbereitungs-Checkliste vollständig bestätigt, Bediener erfasst",
    },
    "crit_S2_present": {
        "zh": "ID 1–8 全部应答，型号 777",
        "en": "IDs 1–8 all answer, model 777",
        "de": "IDs 1–8 antworten alle, Modell 777",
    },
    "crit_S2_firmware_same": {
        "zh": "8 颗固件版本一致（LeRobot 连接时校验）",
        "en": "Same firmware on all 8 (checked by LeRobot on connect)",
        "de": "Gleiche Firmware auf allen 8 (von LeRobot beim Verbinden geprüft)",
    },
    "crit_S2_voltage": {
        "zh": "每颗电压与 7.5V 偏差 ≤ 阈值",
        "en": "Each voltage within the tolerance of 7.5 V",
        "de": "Jede Spannung innerhalb der Toleranz von 7,5 V",
    },
    "crit_S2_temperature": {
        "zh": "静止、未上扭矩时温度 ≤ 阈值",
        "en": "Temperature at rest, torque off ≤ threshold",
        "de": "Temperatur im Ruhezustand ohne Drehmoment ≤ Schwelle",
    },
    "crit_S2_status": {
        "zh": "状态寄存器为 0（无告警位）",
        "en": "Status register is 0 (no alarm bits)",
        "de": "Statusregister ist 0 (keine Alarmbits)",
    },
    "crit_S2_torque_off": {
        "zh": "扭矩关闭",
        "en": "Torque disabled",
        "de": "Drehmoment deaktiviert",
    },
    "crit_S2_voltage_spread": {
        "zh": "8 颗电压极差（待定标）",
        "en": "Voltage spread across the 8 (to be calibrated)",
        "de": "Spannungsstreuung über die 8 (noch zu kalibrieren)",
    },
    "crit_S2_comm": {
        "zh": "连续读取 8 颗位置，0 失败",
        "en": "Continuous reads of all 8 positions, 0 failures",
        "de": "Fortlaufendes Lesen aller 8 Positionen, 0 Fehler",
    },
    "crit_S3_identity": {
        "zh": "只动一个关节时它的跨度最大，且 ≥ 次大 × 阈值",
        "en": "When one joint is moved its travel is largest and ≥ runner-up × threshold",
        "de": "Bei Bewegung eines Gelenks ist sein Weg am größten und ≥ zweitgrößter × Schwelle",
    },
    "crit_S3_span": {
        "zh": "被测关节跨度 ≥ 阈值",
        "en": "Tested joint travel ≥ threshold",
        "de": "Weg des geprüften Gelenks ≥ Schwelle",
    },
    "crit_S4_precheck": {
        "zh": "预检：读数单圈内，预算偏移 |·| ≤ 2047",
        "en": "Precheck: single-turn readings, predicted offset |·| ≤ 2047",
        "de": "Vorprüfung: Werte innerhalb einer Umdrehung, erwarteter Offset |·| ≤ 2047",
    },
    "crit_S4_saved": {
        "zh": "官方校准输出保存标记",
        "en": "Official calibration printed the save marker",
        "de": "Offizielle Kalibrierung hat die Speichermarke ausgegeben",
    },
    "crit_S4_consistent": {
        "zh": "校准文件与 EEPROM 8/8 一致，Phase=12",
        "en": "Calibration file and EEPROM consistent 8/8, Phase=12",
        "de": "Kalibrierdatei und EEPROM 8/8 konsistent, Phase=12",
    },
    "crit_S4_consistent_power_cycled": {
        "zh": "断电 ≥5 s 后再次 8/8 一致",
        "en": "Consistent 8/8 again after ≥5 s power off",
        "de": "Nach ≥5 s stromlos erneut 8/8 konsistent",
    },
    "crit_S4_gripper_range": {
        "zh": "夹爪校准量程（待定标）",
        "en": "Gripper calibration range (to be calibrated)",
        "de": "Greifer-Kalibrierbereich (noch zu kalibrieren)",
    },
    "crit_S5_calibrated": {
        "zh": "官方驱动认定已校准（is_calibrated）",
        "en": "Official driver reports calibrated (is_calibrated)",
        "de": "Offizieller Treiber meldet kalibriert (is_calibrated)",
    },
    "crit_S5_zero_pose": {
        "zh": "零位时 J1–J7 读数 |·| ≤ 阈值",
        "en": "At zero pose J1–J7 readings |·| ≤ threshold",
        "de": "In Nullstellung J1–J7 Werte |·| ≤ Schwelle",
    },
    "crit_S5_gripper_closed": {
        "zh": "夹爪闭合读数 ≥ 阈值（接近 0°）",
        "en": "Gripper closed reading ≥ threshold (near 0°)",
        "de": "Greifer geschlossen ≥ Schwelle (nahe 0°)",
    },
    "crit_S5_gripper_open": {
        "zh": "夹爪张开读数 ≤ 阈值（接近 −65°）",
        "en": "Gripper open reading ≤ threshold (near −65°)",
        "de": "Greifer offen ≤ Schwelle (nahe −65°)",
    },
    "crit_S5_remap": {
        "zh": "扫动 J6/J7 时变化最大的是对调后的键",
        "en": "Sweeping J6/J7 changes the swapped key most",
        "de": "Beim Schwenken von J6/J7 ändert sich der getauschte Schlüssel am stärksten",
    },
    "crit_S5_direction": {
        "zh": "读数方向（待定标，需方向表）",
        "en": "Reading direction (to be calibrated, needs a direction table)",
        "de": "Ableserichtung (noch zu kalibrieren, Richtungstabelle nötig)",
    },
    "crit_S2_protection_limits": {
        "zh": "过压 / 过温保护限值（记录；过压限值应 ≥ 7.5V）",
        "en": "Over-voltage / over-temperature protection limits (recorded; over-voltage limit should be ≥ 7.5 V)",
        "de": "Überspannungs- / Übertemperaturgrenzen (erfasst; Überspannungsgrenze sollte ≥ 7,5 V sein)",
    },
    "crit_R_feedback_moved": {
        "zh": "只读反馈跨度 ≥ 阈值（证明能动、读数连续）",
        "en": "Read-only feedback travel ≥ threshold (moves, readings continuous)",
        "de": "Nur-Lese-Rückmeldeweg ≥ Schwelle (bewegt sich, Werte stetig)",
    },
    "crit_R_feedback_span": {
        "zh": "反馈跨度建议值（待定标）",
        "en": "Suggested feedback travel (to be calibrated)",
        "de": "Empfohlener Rückmeldeweg (noch zu kalibrieren)",
    },
}
