"""打不开串口时的行为。

这组测试是现场撞出来的：装好 scservo_sdk 之后，误选一个内核虚拟串口
（下拉框最前面就是 32 个 /dev/ttyS*）得到的是一句英文
"Could not configure port: (5, 'Input/output error')"——
SDK 的 openPort() 内部直接 serial.Serial(...)，失败时抛 pyserial 异常，
不返回 False，所以按返回值判断的那条分支根本轮不到。

不需要硬件：拿一个不存在的设备路径就能复现同一条失败路径。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import main  # noqa: E402
import messages  # noqa: E402

try:
    import scservo_sdk  # noqa: F401

    SDK_AVAILABLE = True
except Exception:  # noqa: BLE001
    SDK_AVAILABLE = False

MISSING_PORT = "/dev/openarm-mini-no-such-port"


@unittest.skipUnless(SDK_AVAILABLE, "未安装 scservo_sdk，跳过串口失败路径测试")
class OpenFailureTest(unittest.TestCase):
    def tearDown(self) -> None:
        messages.set_language(messages.DEFAULT_LANGUAGE)

    def test_missing_port_raises_connection_error(self) -> None:
        client = main.FeetechSdkClient(MISSING_PORT)
        with self.assertRaises(ConnectionError):
            client.open()

    def test_lock_is_released_after_a_failed_open(self) -> None:
        # 失败时不放锁会把整台工作站卡死：之后每一次操作都报「串口正忙」，
        # 而且只能重启服务才能恢复。
        client = main.FeetechSdkClient(MISSING_PORT)
        with self.assertRaises(ConnectionError):
            client.open()
        self.assertTrue(
            main.SERIAL_PORT_LOCK.acquire(timeout=1.0),
            "打开失败后串口锁没有释放",
        )
        main.SERIAL_PORT_LOCK.release()

    def test_close_after_a_failed_open_is_harmless(self) -> None:
        # 领域函数都在 finally 里 close()，所以这条路径每次失败都会走到。
        client = main.FeetechSdkClient(MISSING_PORT)
        with self.assertRaises(ConnectionError):
            client.open()
        client.close()
        self.assertTrue(main.SERIAL_PORT_LOCK.acquire(timeout=1.0))
        main.SERIAL_PORT_LOCK.release()

    def test_message_is_translated_and_names_the_port(self) -> None:
        for lang, needle in (
            ("zh", "无法打开串口"),
            ("en", "Could not open the serial port"),
            ("de", "konnte nicht geöffnet werden"),
        ):
            with self.subTest(lang=lang):
                messages.set_language(lang)
                client = main.FeetechSdkClient(MISSING_PORT)
                with self.assertRaises(ConnectionError) as caught:
                    client.open()
                text = str(caught.exception)
                self.assertIn(needle, text)
                self.assertIn(MISSING_PORT, text)

    def test_message_tells_the_operator_which_entry_to_pick(self) -> None:
        # 这条错误最常见的原因就是选错了条目，所以文案必须直接给出该选哪个。
        messages.set_language("zh")
        client = main.FeetechSdkClient(MISSING_PORT)
        with self.assertRaises(ConnectionError) as caught:
            client.open()
        self.assertIn("/dev/serial/by-id/", str(caught.exception))

    def test_domain_call_surfaces_the_translated_message(self) -> None:
        messages.set_language("de")
        with self.assertRaises(ConnectionError) as caught:
            main.scan_current_motor(MISSING_PORT, hardware_profile="mini_bench_5v")
        self.assertIn("konnte nicht geöffnet werden", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
