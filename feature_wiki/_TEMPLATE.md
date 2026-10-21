---
title: "<module> — <feature short name>"
category: feature
module: <module-name>                        # testbench / calibration / ...
audience: [operator]                         # operator / engineer / admin / system (可多选)
status: shipped                              # shipped / beta / deprecated
since: <YYYY-MM-DD>                          # 上线 or 上次大改日期
sources:
  - ".tasks/<module>/<task>/CLAUDE.md"
  - "<关键实现路径>"
related_features: []                         # ["other-slug"] 同 module / 上下游
---

# <module> — <feature short name>

## What it is

<一到两句话。从使用者视角描述这个功能做什么、解决什么问题。不写技术实现。>

## Who uses it

| 角色 | 能做什么 | 权限/前提 |
|------|----------|----------|
| <operator> | <能做的事> | <角色 / 工位 / 设备权限> |

## How to use

1. 进入 `<界面位置 / 命令入口>`
2. <操作步骤>(截图占位: `screenshots/<slug>-step1.png`)
3. <验证使用者看到的结果是什么>

> **提示** / **限制** / **常见误用**: <如果有>

## Screens / Routes / Endpoints

| 类型 | 位置 | 说明 |
|------|------|------|
| <页面/命令/接口> | <路径> | <说明> |

## Edge cases

- <边界情况与系统行为>

## Configuration

- <相关配置项及其效果;无则写 none>

## Related features

- [[<other-slug>]]

## Provenance

- 任务: <task path>
- 关键代码: <paths>
