"""用 LeRobot 官方 openarm_mini 驱动读一段 leader 臂的动作值（S6）。

在 **LeRobot 的虚拟环境**里运行，由工作站以子进程调用；工作站本身不 import LeRobot。

官方第 7 步 `lerobot-teleoperate` 必须带 follower（`TeleoperateConfig.robot` 必填），
没有 follower 跑不了。这里只做 leader 半边：与遥操作时完全相同的
`connect(calibrate=False)` → `get_action()`，所以校准文件、side 方向翻转、
J6/J7 对调、夹爪换算全部走官方代码。

`configure()` 先关扭矩，再写官方运行期配置（与客户遥操作时一致）；全程不上扭矩。

输出一行 JSON 到 stdout；失败时退出码非 0，stderr 给原因。
"""

from __future__ import annotations

import argparse
import json
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description="openarm_mini official readout")
    parser.add_argument("--port", required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--side", required=True, choices=("left", "right"))
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--interval", type=float, default=0.05)
    args = parser.parse_args()

    from lerobot.teleoperators.openarm_mini import OpenArmMini, OpenArmMiniConfig

    config = OpenArmMiniConfig(port=args.port, id=args.id, side=args.side)
    teleop = OpenArmMini(config)
    calibration_file = str(teleop.calibration_fpath)
    has_file = teleop.calibration_fpath.is_file()
    if not has_file:
        print(f"calibration file not found: {calibration_file}", file=sys.stderr)
        return 3

    teleop.connect(calibrate=False)
    try:
        is_calibrated = bool(teleop.is_calibrated)
        samples: list[dict[str, float]] = []
        deadline = time.monotonic() + max(0.5, args.seconds)
        while time.monotonic() < deadline:
            samples.append({k: float(v) for k, v in teleop.get_action().items()})
            time.sleep(args.interval)
    finally:
        teleop.disconnect()

    keys = sorted(samples[0]) if samples else []
    result = {
        "ok": True,
        "calibration_file": calibration_file,
        "is_calibrated": is_calibrated,
        "side": args.side,
        "samples": len(samples),
        "first": samples[0] if samples else {},
        "last": samples[-1] if samples else {},
        "mean": {k: sum(s[k] for s in samples) / len(samples) for k in keys},
        "min": {k: min(s[k] for s in samples) for k in keys},
        "max": {k: max(s[k] for s in samples) for k in keys},
        "span": {k: max(s[k] for s in samples) - min(s[k] for s in samples) for k in keys},
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        # 操作员只需要最后那句原因（例如 LeRobot 的 "Could not connect on port"），不要整段 traceback。
        print(f"{type(exc).__name__}: {' '.join(str(exc).split())}", file=sys.stderr)
        sys.exit(1)
