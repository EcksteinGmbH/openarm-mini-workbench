"""三语完整性。

缺一个键不会报错，只会静默回落成中文——德语操作员因此在最要紧的一步读到中文。
所以完整性必须由测试来锁，而不是靠人校对。
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import main  # noqa: E402
import messages  # noqa: E402

PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


class ServerCatalogTest(unittest.TestCase):
    def test_every_key_has_all_three_languages(self) -> None:
        for key, entry in messages.MESSAGES.items():
            with self.subTest(key=key):
                self.assertEqual(set(entry), set(messages.LANGUAGES))

    def test_no_translation_is_empty(self) -> None:
        for key, entry in messages.MESSAGES.items():
            for lang, text in entry.items():
                with self.subTest(key=key, lang=lang):
                    self.assertTrue(text.strip(), f"{key}/{lang} 为空")

    def test_placeholders_match_across_languages(self) -> None:
        # 占位符对不上时，渲染出来的句子会留着一个没被替换的 {id}。
        for key, entry in messages.MESSAGES.items():
            expected = set(PLACEHOLDER.findall(entry["zh"]))
            for lang in messages.LANGUAGES:
                with self.subTest(key=key, lang=lang):
                    self.assertEqual(set(PLACEHOLDER.findall(entry[lang])), expected)

    def test_no_untranslated_copy_between_languages(self) -> None:
        # 英德两版与中文逐字相同，说明那一条根本没翻。纯符号/占位符的条目不算。
        for key, entry in messages.MESSAGES.items():
            if not re.search(r"[一-鿿]", entry["zh"]):
                continue
            for lang in ("en", "de"):
                with self.subTest(key=key, lang=lang):
                    self.assertNotEqual(entry[lang], entry["zh"])
                    self.assertFalse(
                        re.search(r"[一-鿿]", entry[lang]),
                        f"{key}/{lang} 里还留着中文",
                    )


class RenderTest(unittest.TestCase):
    def tearDown(self) -> None:
        messages.set_language(messages.DEFAULT_LANGUAGE)

    def test_language_selection(self) -> None:
        messages.set_language("de")
        self.assertEqual(messages.m("prompt_zero_title"), "Nullstellung")
        messages.set_language("en")
        self.assertEqual(messages.m("prompt_zero_title"), "Zero pose")
        messages.set_language("zh")
        self.assertEqual(messages.m("prompt_zero_title"), "零位姿态")

    def test_unknown_language_falls_back_to_chinese(self) -> None:
        self.assertEqual(messages.set_language("fr"), "zh")
        self.assertEqual(messages.m("prompt_zero_title"), "零位姿态")

    def test_placeholders_are_substituted(self) -> None:
        messages.set_language("de")
        text = messages.m("serial_exhausted", day="20260929", code="L")
        self.assertIn("20260929", text)
        self.assertNotIn("{day}", text)

    def test_unknown_key_returns_the_key(self) -> None:
        self.assertEqual(messages.m("no_such_key"), "no_such_key")

    def test_motor_titles_follow_the_language(self) -> None:
        messages.set_language("de")
        self.assertEqual(main.motor_title("gripper"), "J8 · Greifer")
        messages.set_language("en")
        self.assertEqual(main.motor_title("joint_1"), "J1 · Shoulder Pan")

    def test_every_motor_has_a_name_in_every_language(self) -> None:
        for lang in messages.LANGUAGES:
            messages.set_language(lang)
            for name in main.OPENARM_MINI_MOTORS:
                with self.subTest(lang=lang, motor=name):
                    self.assertNotEqual(messages.motor_label(name), "motor_" + name)

    def test_every_supply_profile_label_is_translated(self) -> None:
        for lang in messages.LANGUAGES:
            messages.set_language(lang)
            for key, profile in main.MINI_HARDWARE_PROFILES.items():
                with self.subTest(lang=lang, profile=key):
                    for field in ("label_key", "usage_key"):
                        self.assertIn(profile[field], messages.MESSAGES)
                        self.assertNotEqual(messages.m(profile[field]), profile[field])

    def test_every_register_field_name_is_translated(self) -> None:
        # 字段键来自 read_1byte / read_2byte 的调用点，漏一个就会渲染成 field_xxx。
        source = Path(main.__file__).read_text(encoding="utf-8")
        used = set(re.findall(r'ADDR_[A-Z_]+,\s*"([a-z_]+)"', source))
        self.assertTrue(used, "没有找到任何字段键，正则可能过期了")
        for lang in messages.LANGUAGES:
            messages.set_language(lang)
            for field in sorted(used):
                with self.subTest(lang=lang, field=field):
                    self.assertIn("field_" + field, messages.MESSAGES)
                    self.assertNotEqual(messages.field_name(field), "field_" + field)


class PageCatalogTest(unittest.TestCase):
    """页面自带的 I18N 表。按源码格式解析，格式改了这里会先报错。"""

    @classmethod
    def setUpClass(cls) -> None:
        block = re.search(r"const I18N = \{(.*?)\n\};", main.INDEX_HTML, re.S)
        assert block is not None, "页面里找不到 I18N 表"
        body = block.group(1)
        cls.tables: dict[str, set[str]] = {}
        for lang in messages.LANGUAGES:
            section = re.search(r"\n  " + lang + r": \{(.*?)\n  \},", body, re.S)
            assert section is not None, f"页面 I18N 里找不到 {lang}"
            # 值里也有 `xxx:` 形状的文本，所以先把字符串字面量抹平再抓键名。
            stripped = re.sub(r'"(?:[^"\\]|\\.)*"', '""', section.group(1))
            cls.tables[lang] = set(re.findall(r"([a-z_]+):", stripped))

    def test_all_three_tables_carry_the_same_keys(self) -> None:
        reference = self.tables["zh"]
        self.assertTrue(reference, "中文表解析为空")
        for lang in ("en", "de"):
            with self.subTest(lang=lang):
                self.assertEqual(
                    self.tables[lang],
                    reference,
                    f"{lang} 与中文相比多/少了: "
                    f"{self.tables[lang] ^ reference}",
                )

    def test_every_data_i18n_attribute_has_a_key(self) -> None:
        attrs = set(re.findall(r'data-i18n(?:-html)?="([a-z_]+)"', main.INDEX_HTML))
        self.assertTrue(attrs, "页面里没有 data-i18n 标注")
        for key in sorted(attrs):
            with self.subTest(key=key):
                self.assertIn(key, self.tables["zh"])

    def test_every_key_used_in_script_exists(self) -> None:
        used = set(re.findall(r"\btr\('([a-z_]+)'\)", main.INDEX_HTML))
        used |= set(re.findall(r"\btf\('([a-z_]+)'", main.INDEX_HTML))
        self.assertTrue(used, "脚本里没有取任何文案键")
        for key in sorted(used):
            with self.subTest(key=key):
                self.assertIn(key, self.tables["zh"])


class PageSyntaxTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "未安装 node，跳过 JS 语法检查")
    def test_embedded_script_parses(self) -> None:
        script = re.search(r"<script>(.*?)</script>", main.INDEX_HTML, re.S)
        assert script is not None
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
            handle.write(script.group(1))
            path = handle.name
        try:
            result = subprocess.run(
                [str(shutil.which("node")), "--check", path], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            Path(path).unlink()


if __name__ == "__main__":
    unittest.main()


class NoHardcodedOperatorTextTest(unittest.TestCase):
    """main.py 里不允许再有绕过文案目录的中文操作员文案。

    这条测试是补出来的：三语改造第一遍漏掉了 HTTP 层的「请先选择串口。」，
    页面切到德语后那句仍然是中文。靠人逐行看不住，靠 AST 能。
    """

    # 启动服务的人看的是终端，不是页面，语言不随请求变。
    CLI_ALLOWLIST = {
        "OpenArm Mini 测试工作站",
        "监听地址，默认 127.0.0.1",
        "监听端口，默认 8788",
        "已停止。",
    }

    def test_no_chinese_literal_outside_the_catalog(self) -> None:
        import ast

        source = Path(main.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)

        skip: set[int] = set()
        for node in ast.walk(tree):
            # docstring 是给维护者的，留中文
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                body = getattr(node, "body", [])
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                    if isinstance(body[0].value.value, str):
                        skip.add(id(body[0].value))
            # 内嵌页面自带三语表
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "INDEX_HTML":
                        skip.add(id(node.value))

        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in skip or not re.search(r"[一-鿿]", node.value):
                continue
            text = node.value.strip()
            if text in self.CLI_ALLOWLIST or any(
                text.startswith(allowed) for allowed in self.CLI_ALLOWLIST
            ):
                continue
            offenders.append((node.lineno, text[:70]))

        self.assertEqual(
            offenders,
            [],
            "这些中文文案没有走 messages.py，切到英/德时不会翻译：\n"
            + "\n".join(f"  app/main.py:{line} {text}" for line, text in offenders),
        )
