## 工程档案

### 领域约束

| 领域 | 路径模式 | 约束文档 |
|------|---------|---------|
| workbench | `app/**`, `scripts/openarm_mini_readout.py`, `requirements.txt`, `tests/**`, `VERSION` | `README.md`, `docs/WORKSTATION_CHANGELOG.md` |
| official-reference | `docs/**` | `docs/official-comparison.md`(规则以官方硬件仓库 README/BOM 与 lerobot 源码为准) |
| knowledge | `agent_wiki/**`, `feature_wiki/**`, `scripts/wiki_reindex.py` | `agent_wiki/AGENTS.md` |

### 验证命令

- 自检: `.venv/bin/python -m compileall -q app scripts/wiki_reindex.py && python3 scripts/wiki_reindex.py agent_wiki --check`
- 测试: `.venv/bin/python -m unittest discover -s tests`(139 项;须用 `.venv`,系统 `python3` 没有 pyserial)
- 健康检查: `.venv/bin/python app/main.py --help`
- LSP smoke: 无

### 验收门

- 范围: `app/main.py` 的串口通信、电机寄存器读写、ID/波特率写入流程、校准子进程的阶段识别与作答;`scripts/openarm_mini_readout.py`;`app/criteria.py` 判据阈值;`requirements.txt` 与 LeRobot 版本变更
- 验收环境: 装配完成的 OpenArm Mini 整臂(8× STS3215-C046 + Waveshare 驱动板)挂在竖直立柱上,可调电源 7.50V / ≥2A;返修工具写 ID 时总线上只接一颗电机;浏览器人工检查中/英/德三语流程

### 发布流程

- 无集中发布;按 `README.md` 建 `.venv` 与项目内 `.venv-lerobot/`,在目标工位启动 `.venv/bin/python app/main.py --host 127.0.0.1 --port 8788`
- 硬规则: 未经上述真机验收,不把影响串口/寄存器写入/校准作答的版本用于产线
- 台账: 无

### 架构边界

- 运行时代码:`app/main.py`(Feetech 适配、各阶段测试、HTTP API、内嵌页面)、`app/criteria.py`(判据表与纯判定函数,不碰串口与文案)、`app/gate.py`(放行门与归档,只读会话日志);面向操作员的文案只放 `app/messages.py`,三语同步
- 判定一律在服务端完成并写入会话日志;页面阶段条按 `/api/release-gate` 画,不在浏览器里算通过与否
- 判据阈值只改 `app/criteria.py`,同时升 `CRITERIA_VERSION` 并记 `docs/WORKSTATION_CHANGELOG.md`;影响流程/报告/硬件的改动按变更记录的分级升 `VERSION`
- 测试站只测装配完成的整臂,电源一律 7.5V(官方 BOM);装配前写 ID 属装配环节,这里只有不进放行门的返修工具
- 全程只读、不上扭矩;写入只有官方 `lerobot-calibrate` 的校准参数、官方驱动 `connect()` 的运行期配置,以及返修工具的 ID/波特率
- LeRobot 不是工作站依赖:只作为子进程启动(`lerobot-calibrate`、`scripts/openarm_mini_readout.py`),不得从 `app/` 导入
- 持久化/迁移策略: 无数据库;每条臂一个 `test_reports/.sessions/<编号>.jsonl` 追加日志(不提交);归档 `test_reports/Leader/<编号>/` 与 `test_reports/编号与归档索引.md`(提交);校准文件在 LeRobot 校准根下,设备配置在电机 EEPROM;旧格式日志记录由放行门忽略,无迁移机制

### 命名约定

- 任务名: 短英文 kebab-case
- Python 函数与变量 `snake_case`,常量 `UPPER_SNAKE_CASE`
- 电机键名固定为 `joint_1`…`joint_7`, `gripper`(与 LeRobot `openarm_mini` 一致),ID 1–8 ↔ J1–J8
- 机械臂编号: `OAM` + `L`/`R` + `YYYYMMDD` + 当日两位序号,例 `OAML2026092801`

### UX 约定

- 页面每一步标明「官方流程」或「本地质检」
- 所有面向操作员的新文案同步写中/英/德,`tests/test_i18n.py` 会拦缺键与中文字面量
- 写 ID 前维持「总线上只接一颗电机」的前提;广播 ping 收到多于一个应答时直接报错
