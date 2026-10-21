---
title: "启动哪个 lerobot-calibrate：显式优先、项目内优先，不按字母序"
category: decision
tags: [openarm-mini, lerobot, venv, so-arm101, safety]
sources:
  - "app/main.py: resolve_lerobot_calibrate() / set_lerobot_calibrate_override()"
  - "tests/test_workstation.py: LerobotResolutionTest"
  - "docs/official-comparison.md A3"
  - "git e501f7d 提交说明"
confidence: high
---

# 启动哪个 lerobot-calibrate：显式优先、项目内优先，不按字母序

S5 官方校准启动的 `lerobot-calibrate`（S6 官方读数用同一环境的 Python）按「参数 > 环境变量 > 项目内 venv > PATH > 共享目录」解析，显式路径无效直接报错，不再按共享目录字母序取第一个。

解析优先级：

1. `--lerobot-calibrate=/path`
2. 环境变量 `OPENARM_MINI_LEROBOT_CALIBRATE`
3. 项目内 `.venv-lerobot/` 或 `.venv/`
4. `PATH`
5. 共享 `~/Projects/.venvs` / `~/.venvs`（兼容保留，页面标「共享目录」）

显式路径无效时**直接报错，不回退**。页面显示选中的可执行文件和来源层级。

## 为什么

原先与 SO-ARM101 工作站共用 `sorted(glob("~/Projects/.venvs/*/bin/lerobot-calibrate"))[0]`：
在共享目录新建一个 venv，就会按字母序**同时**改变两个工作站选中的 LeRobot。
靠字母序保证安全属性不可接受。

## 操作规则

- 给本工作站装 LeRobot **装进项目内 `.venv-lerobot/`**，不要装到 `~/Projects/.venvs/`
  （SO-ARM101 工作站仍按旧逻辑扫那里，它的同类隐患未改，属另一个仓库）。
- 装的必须是单臂代驱动，见 [[openarm-mini-driver-generations]]。
