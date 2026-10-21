---
title: "openarm_mini 驱动有单臂/双臂两代：PyPI 0.4.4/0.5.0 是双臂版，0.6.1 起是单臂版"
category: environment
tags: [openarm-mini, lerobot, venv, version, draccus]
sources:
  - "app/main.py: probe_openarm_mini_driver() / PROBE_SINGLE_ARM / PROBE_DUAL_ARM"
  - "tests/test_workstation.py: DriverGenerationTest"
  - "git 7494016 提交说明（draccus 报 `The fields port are not valid for OpenArmMiniConfig`）"
  - "2026-10-21 本机探测：dataclasses.fields(OpenArmMiniConfig) 与 dist-info/direct_url.json"
  - "2026-10-21 PyPI wheel 0.4.4 / 0.5.0 / 0.6.1 的 config_openarm_mini.py 字段比对；0.6.1 与 eb7a54c 的 openarm_mini.py、feetech/、motors_bus.py diff"
confidence: high
---

# openarm_mini 驱动有单臂/双臂两代：PyPI 0.4.4/0.5.0 是双臂版，0.6.1 起是单臂版

PyPI `lerobot` 0.4.4 与 0.5.0 带的是双臂代 `openarm_mini`（`port_right/port_left`），0.6.1（2026-08-03）起是官方 README 命令所需的单臂代；工作站按配置字段判别并拦下双臂代，本机 `.venv-lerobot` 现为 0.6.2 @ `eb7a54c`（单臂）。

同一个模块名 `lerobot.teleoperators.openarm_mini` 背后有两代**不兼容**的驱动：

| 代 | 出处 | `OpenArmMiniConfig` 字段 | 行为 |
|---|---|---|---|
| 双臂 | PyPI `lerobot` 0.4.4、0.5.0 | `port_right`, `port_left`, `use_degrees` | 同时开两条总线，校准 6 次确认，键名带 `right_`/`left_` |
| 单臂 | PyPI `lerobot` ≥0.6.1 与 `main`（另有 `bi_openarm_mini`） | `port`, `side`, `use_degrees` | 官方硬件 README 的命令按这一代写 |

官方 README 的 `--teleop.port=...` 在双臂版上会被 draccus 拒绝：
`The fields port are not valid for OpenArmMiniConfig`。

## 工作站怎么处理

`probe_openarm_mini_driver()` 导入 `OpenArmMiniConfig` 按**字段**判定
`single_arm` / `dual_arm` / 缺失；双臂版直接拦下 S4 校准与 S5 读数并说明原因。
不读源码文本——editable 安装、补丁、插件覆盖都会骗过文本匹配。

## 本机现状（2026-10-21 核对）

| venv | 版本 | 来源 | 代 |
|---|---|---|---|
| `.venv-lerobot/`（工作站默认选中） | 0.6.2，Python 3.12 | `git+https://github.com/huggingface/lerobot@eb7a54c6ff49` | 单臂，含 `bi_openarm_mini` |
| `.venv-lerobot.py310-pypi/` | 0.4.4，Python 3.10 | PyPI wheel | 双臂（被拦） |
| `~/Projects/.venvs/so-arm101-lerobot-0.4.4` | 0.4.4 | editable，SO-ARM101 的 `reference/lerobot` 快照 | 没有 `openarm_mini` |

**版本号不能单独标识 LeRobot**：本机两个「0.4.4」完全不同。引用时连来源/提交一起写。
选中哪个可执行文件的规则见 [[lerobot-executable-resolution]]。

提交 7494016 写的「PyPI 没有任何发布含单臂驱动」在当时就不成立：0.6.1 已发布单臂代。
0.6.1 与 eb7a54c 的 `openarm_mini.py` 只差变量改名和一处 `calibration is None` 保护，`feetech/`、`motors_bus.py`、`teleoperator.py` 完全相同，
可作为可复现的钉定版本（Python ≥3.12）。lerobot main 在 eb7a54c 之后改了沿用提示串与偏移超限行为，升级越过 0.6.1 前须先改特征串。
