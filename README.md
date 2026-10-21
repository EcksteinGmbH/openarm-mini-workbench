# OpenArm Mini 测试工作站

[OpenArm Mini](https://github.com/pkooij/open-arms-mini) 的产线测试工作站：
写电机 ID、只读质检、八轴扫描、驱动官方 LeRobot 校准、一致性核对和测试数据导出。

硬件是 7 DOF + 夹爪的遥操作 **leader 臂**，8 颗 Feetech STS3215-C046（7.4V）
挂在 Waveshare 串行总线驱动板上，软件侧是 LeRobot 的 `openarm_mini` 遥操作器。

运行代码两个文件：[`app/main.py`](app/main.py) 是工作站本体，
[`app/messages.py`](app/messages.py) 是中/英/德三语文案目录。

## 启动

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app/main.py --host 127.0.0.1 --port 8788
```

浏览器打开 `http://127.0.0.1:8788`。

用系统 `python3` 直接启动也能开页面，但一点「扫描」就会报「未安装 scservo_sdk」——
硬件层是**懒加载**的，缺依赖不会拦住服务启动，只会在第一次真的要跟电机说话时暴露。

校准那一步需要另外一个装有 **含 `openarm_mini` 驱动的 LeRobot** 的环境
（`pip install 'lerobot[feetech]'`）。LeRobot 刻意不是本工作站的依赖：
工作站自己只用 `pyserial` + `scservo_sdk` 跟电机说话。

## 全程只读，不上扭矩

Mini 是手持 leader 臂，正常使用时人手驱动、电机只当编码器。**工作站在任何步骤都不会
开启扭矩、不会下发目标位置**：所有质检都是「读起点 → 操作员手动摆动 → 再读」。
给一条手持臂上扭矩既没有对应的使用场景，也会在装配阶段把人和结构件置于风险里。

唯一会写入电机的操作是第 2 步的 ID 与波特率（EEPROM），以及第 4 步由官方
`lerobot-calibrate` 自己写入的校准参数。

## 这台工作站不做什么
- **不重写校准算法。** 第 4 步把官方 `lerobot-calibrate` 当子进程驱动，
  把它的每次确认映射成页面按钮。保存下来的文件与在终端直接跑完全一致，
  LeRobot 升级后也不需要同步校准逻辑。
- **不做行程试扫。** `openarm_mini` 驱动给 joint_1..joint_7 写死整圈量程
  （`0..4095`），不存在 SO-101 那种「行程必须落进停放位 ±2047」的约束。
  照搬那套逻辑会拦下完全正常的关节。理由见
  [docs/lerobot-openarm-mini.md](docs/lerobot-openarm-mini.md)。

## 流程与官方的对应

页面上每一步都标了 `官方流程` 或 `本地质检`，照着走就能知道哪些是 LeRobot 官方要求、
哪些是本工作站加的产线闸门，不必预先记住：

| 步骤 | 归属 | 对应官方 |
|---|---|---|
| 串口自动识别 | 本地（替代） | `lerobot-find-port` |
| 扫描当前电机 → 写 ID 与波特率 | **官方流程** | `lerobot-setup-motors` |
| 断电 5 秒复扫 | 本地质检 | 无 |
| 只读反馈测试 | 本地质检 | 无 |
| 八轴只读扫描 | 本地质检 | 官方仅要求恢复菊花链 |
| 校准预检 | 本地质检 | 无 |
| 开始官方校准 | **官方流程** | `lerobot-calibrate` |
| 一致性核对 | 本地质检 | 无 |
| 导出归档 | 本地质检 | 无 |
| 遥操作配对验证 | **未覆盖** | `lerobot-teleoperate`（需 follower 臂） |

## 五个阶段

页面按阶段组织，顶部进度条显示当前位置。

1. **准备** —— 选左右臂、生成编号、确认供电档位、选串口。
2. **逐颗写 ID 与只读质检** —— 按 **8 → 1** 的顺序（官方 `setup_motors()` 的顺序），
   每颗走「扫描 → 写 ID → 断电 5 秒复扫 → 只读反馈测试」四步，全过才进入下一颗。
   写 ID 时总线上**只能挂当前这一颗电机**。
3. **八轴只读扫描** —— 恢复 1→8 菊花链，读遍 8 颗的 ID、型号、位置、电压、温度、`Phase` 和关键配置。
4. **校准与一致性核对** —— 先只读预检，再启动官方校准。页面按阶段引导
   零位（整臂下垂、夹爪闭合）、夹爪闭合、夹爪张开三次确认；保存后自动核对。
5. **导出归档** —— 下载本次测试的完整 JSON。

## 三语

页面右上角切中文 / English / Deutsch。**错误信息也跟着翻**——出错的时候恰恰最需要看懂，
而错误大多产生在硬件层，所以文案目录放在服务端（[`app/messages.py`](app/messages.py)），
页面每次请求带上 `lang`，服务端按该语言渲染。页面骨架用 `data-i18n` 声明式标注，
自带一份同构的三语表。

关节名、供电档位文案和编号格式提示由服务端按语言给，所以切语言时页面会重取 `/api/config`。

新增任何面向操作员的文案，都要同时写齐三种语言：`tests/test_i18n.py` 会检查缺键、
空值、占位符不一致、英德版残留中文，以及 `app/main.py` 里有没有绕过目录的中文字面量。
最后这一条是补出来的——三语改造第一遍就漏了 HTTP 层的「请先选择串口。」。

## 机械臂编号

```
OAM + 臂侧(L/R) + YYYYMMDD + 当日两位序号      例：OAML2026092801
```

Mini 只有 leader 一种形态、只有 7.4V 一档，所以区分位留给左右臂——
左右臂的夹爪件号（J8 L/R）和驱动里的方向翻转表都不同，是真实的产品差异。

「推荐编号」同时扫描 `test_reports/`、会话日志和 LeRobot 校准缓存来确定当日已用序号。
只看归档会漏掉已校准未归档的臂，导致重复发号。

## 供电档位保护

| 档位 | 电机额定 | 现场电源设置 | 用途 |
|---|---|---|---|
| 台架建站 5V | 7.4V | 5.00V / 4.00A | 逐颗写 ID 与只读检查 |
| 整臂 7.5V | 7.4V | 7.50V / 2.00A | 八轴联调、官方校准与遥操作 |

每次扫描和写 ID 前，工作站读电机实际电压并与所选档位比对，偏差超过 1.0V
或超过额定 7.4V 即拒绝执行。工作站只记录档位、改不了实体电源——
仍需人工核对红正黑负、OCP 关闭和 OUTPUT 状态。

## 测试记录持久化

每次扫描、写 ID、质检、预检、校准和核对（**含失败**）都追加写入
`test_reports/.sessions/<编号>.jsonl`。页面内存不再是唯一副本，
关标签页或服务重启都不丢数据。归档最需要解释的恰恰是失败的那几次。

## 验证

```bash
.venv/bin/python -m compileall -q app scripts/wiki_reindex.py
.venv/bin/python -m unittest discover -s tests
python3 scripts/wiki_reindex.py agent_wiki --check
```

95 项单测，只锁可离线判定的规则：关节表与官方 ID 表一致、写 ID 顺序与驱动一致、
Feetech 符号位解码、编码器接缝展开、供电档位判据、编号规则、校准阶段提示串识别、
失败特征串与处置一一对应、三语完整性。装有 `node` 时还会做一次内嵌 JS 语法检查。

另有一组串口失败路径的测试，用一个不存在的设备路径复现，不需要硬件：
串口打不开时必须抛出三语的 `ConnectionError`、必须在错误里说清该选哪个条目、
并且**必须释放串口锁**——失败不放锁会让之后每一次操作都报「串口正忙」，
只能重启服务才能恢复。用系统 `python3` 跑时这 6 项会自动跳过（缺 `scservo_sdk`）。

电机在位时的真实行为仍在真机上验证，不在这里模拟。

## 验收门

以下改动需在真机上复验后才能用于产线：串口通信、电机寄存器写入、
ID 写入流程、校准子进程的阶段识别与作答。

验收环境：OpenArm Mini 台架，STS3215 + Waveshare 驱动板 + 独立可调电源；
写 ID 时一次只接一颗电机，八电机联调时再接全部。
浏览器人工检查中 / 英 / 德三语流程。

## 串口自动识别

不需要选串口。内核给每个板载 UART 都建一个 `/dev/ttyS*` 节点（本机 32 个），
插没插东西都在；让操作员在 33 条里挑出那一条适配器，是选错串口的主要来源。

工作站按 **USB 身份（vid/pid）和 `/dev/serial/by-id/` 别名** 筛出真适配器：

| 情况 | 行为 |
|---|---|
| 恰好 1 个适配器 | **自动选中**，显示型号与 USB 序列号 |
| 没有适配器 | 提示插好 USB 线，并说明 `/dev/ttyS*` 不是适配器 |
| 2 个以上适配器 | **不猜**，要求手动选择 |

最后一条是有意的：一个工位同时插着左右两条臂的适配器是正常状态，猜错会把 ID
写到另一条臂上。

给出的路径一律是 `/dev/serial/by-id/...` 别名，它由 USB 序列号生成、拔插后不变；
`/dev/ttyACM0` 这类内核名每次重新枚举都会变。

页面每 3 秒自动重新识别，**适配器插上或拔掉不用点任何按钮**；候选没变化时不重建下拉框，
免得打断正在展开它的操作员。勾选「显示全部串口」可以看到全部 33 个节点做返工排查。
适配器存在但当前用户没有读写权限时会提前警告并给出 `usermod -aG dialout` 命令——
不提前说的话，要等到点了操作才在打开串口时失败。

## 单电机识别：与官方同法

第 2 步的「扫描」按官方 `feetech._find_single_motor_p0()` 的方式做：
**每档波特率发一个广播 ping**，最坏 8 个包。实测（适配器在位、电机未上电）**8.0 秒**。

比官方多一道闸：广播会返回总线上**所有**应答，检测到多于一颗就直接报错并列出 ID。
官方只取第一个应答，多接了电机发现不了——而写 ID 时多接一颗，两颗会被改成同一个 ID。
这道闸是在**执行**官方那句「只连接当前这一颗电机」。

勾选「深度扫描」会退回逐个试 ID（8 档 × 252 个，实测约 110 秒），**默认关闭**，
只在某颗电机确实不响应广播时用；这不是官方行为。

页面给所有占串口的按钮都加了「进行中… Ns」状态：置灰、显示已耗时，
避免看起来像卡死，也避免连点撞上「串口正忙」。

## 指定用哪个 LeRobot

第 4 步要启动官方 `lerobot-calibrate`。解析优先级：

1. `--lerobot-calibrate=/path` 参数
2. `OPENARM_MINI_LEROBOT_CALIBRATE` 环境变量
3. **项目内** `.venv-lerobot/` 或 `.venv/`
4. `PATH`
5. 共享 `~/Projects/.venvs` / `~/.venvs`

显式指定的路径无效时直接报错，不静默回退。页面会显示将启动哪个可执行文件、来源是哪一级。

**给本工作站装带单臂 `openarm_mini` 驱动的 LeRobot，要装进项目目录**。
PyPI 上的 `lerobot 0.4.4` 带的是**双臂代**驱动（只有 `port_right` / `port_left`），
官方 README 的单臂命令跑不起来，工作站会在第 4 步拦下它；单臂代目前只在上游 `main`，
所以按提交安装（需 Python ≥ 3.12）：

```bash
python3.12 -m venv .venv-lerobot
.venv-lerobot/bin/python -m pip install \
  'lerobot[feetech] @ git+https://github.com/huggingface/lerobot@eb7a54c6ff4983fc86075442bf4fa61503e7b5d1'
```

**不要装到 `~/Projects/.venvs/`。** 那个共享目录被 SO-ARM101 工作站用
`sorted(glob(...))` 扫描并取第一个匹配，在那里新建 venv 会按字母序悄悄改变**它**
选中的 LeRobot；装在项目内它看不见。详见
[docs/official-comparison.md](docs/official-comparison.md) 的 A3。

本机现状（2026-10-21 核对）：`.venv-lerobot/` 是 `lerobot 0.6.2 @ eb7a54c`（单臂代，
含 `bi_openarm_mini`），工作站默认选中它。最初装的 PyPI 0.4.4（双臂代）挪到了
`.venv-lerobot.py310-pypi/`，留作对照，工作站不会选它。SO-ARM101 那个 venv 也报 0.4.4，
却是 `so-arm101-workbench/reference/lerobot/` 的 editable 快照，**没有** `openarm_mini`。
版本号不能单独标识 LeRobot，引用时连来源/提交一起写。详见
[agent_wiki/openarm-mini-driver-generations.md](agent_wiki/openarm-mini-driver-generations.md)。

## 已知范围限制

- 归档脚本（从会话日志生成 Markdown/PDF 归档目录）尚未实现，第 5 步只导出 JSON。
- 命令行的启动提示和 `--help` 只有中文：那是给启动服务的人看的，语言不随请求变。
- 会话日志里记录的是**当次请求语言**渲染后的文案。归档若要统一语言，
  导出时按 `action` 重新渲染，或固定用中文操作。
- 只覆盖单臂路径。官方 `bi_openarm_mini`（双臂）的校准文件叫 `<编号>_left.json`
  / `<编号>_right.json`，本工作站的编号规则不匹配，核对会报「未找到校准文件」。
- 没有遥操作配对验证（官方流程的最后一步，需要 follower 臂）。
- **交付时必须提醒客户遥操作要带 `--teleop.side=left|right`**：官方硬件 README 的
  `lerobot-teleoperate` 命令里没有它，而驱动的方向翻转表只在 `side` 非空时生效，
  照 README 逐字抄会有 6 个关节方向是反的。详见
  [docs/official-comparison.md](docs/official-comparison.md) 的 B3。

## 资料

- [docs/hardware-reference.md](docs/hardware-reference.md) —— BOM、打印参数、关节 ID 表、装配顺序、官方命令
- [docs/lerobot-openarm-mini.md](docs/lerobot-openarm-mini.md) —— 上游驱动的校准流程、寄存器期望值、失败特征串
- [docs/official-comparison.md](docs/official-comparison.md) —— 与官方逐项核对：一致项、有意的差异、缺失与待改
- [agent_wiki/index.md](agent_wiki/index.md) —— 工程知识（决策、排障、约定），每页带证据来源；写页前读 [agent_wiki/AGENTS.md](agent_wiki/AGENTS.md)
- [feature_wiki/standard-test-workflow.md](feature_wiki/standard-test-workflow.md) —— 操作员视角的五阶段流程、接口与边界情况
- [CLAUDE.md](CLAUDE.md) 的「工程档案」—— 领域约束、验证命令、验收门、架构边界

## 许可与来源

硬件设计来自 [pkooij/open-arms-mini](https://github.com/pkooij/open-arms-mini)（Apache 2.0，
基于 SO-ARM100）。Feetech 适配层的实现思路来自同台架的 SO-ARM101 工作站，
两者电机与控制表相同。
