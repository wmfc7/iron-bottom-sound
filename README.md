# Iron Bottom Sound IV（铁底湾）

**基于浏览器界面的海战兵棋与裁决工程**，包含 Python 战斗规则引擎、React 前端、单机模式、基于 EasyTier 私有虚拟网络的双人联机模式，以及 Windows x64 的 Host / Guest 打包工具。

> **适用版本：** 本 README 根据当前工程压缩包 `iron-bottom-sound.7z` 中的实际文件编写（项目元数据版本 `0.1.0`）。以本文件所列的**整理后目录**和当前启动脚本为准；`docs/lan/` 下部分旧文档仍保留了历史路径或 `.url` 入口说明，请勿直接照搬旧版步骤。
>
> **主要运行平台：** Windows 10 / 11 x64、Windows PowerShell 5.1。其他平台上的 Python 引擎不等同于已支持完整的 Windows 启动器、EasyTier 和发行包流程。

## 目录

- [1. 功能概览](#1-功能概览)
- [2. 工程目录](#2-工程目录)
- [3. 环境要求](#3-环境要求)
- [4. 单机游戏](#4-单机游戏)
- [5. EasyTier 双人联机](#5-easytier-双人联机)
- [6. 一键构建 Host / Guest](#6-一键构建-host--guest)
- [7. 数据、存档及配置](#7-数据存档及配置)
- [8. 故障排查](#8-故障排查)
- [9. 开发与测试](#9-开发与测试)
- [10. 安全和发布注意事项](#10-安全和发布注意事项)

## 1. 功能概览

| 模块 | 主要内容 |
| --- | --- |
| 战斗引擎 | Python 规则、舰艇与编队、行动指令、炮击/鱼雷、战术阶段、战斗报告、游戏状态与存档 |
| 单机游戏 | FastAPI / Uvicorn 后端，React + Vite 本地前端，在浏览器中操作 |
| 双人联机 | 房主集中裁决；通过 EasyTier IPv4 对外提供准备大厅、阵营席位和同步接口 |
| 联机骰子 | `cpu_rdseed`、`cpu_rdrand` 或 `os_csprng` 可选随机数来源；前两者使用 Windows x64 原生 DLL |
| Windows 发行包 | PyInstaller 打包 Host，独立生成轻量 Guest 自动发现启动器 |
| 游戏素材 | 规则 PDF、想定、舰艇数据、地图与图片等资源 |
| 辅助研究 | `rl/` 中的 AI 策略训练/评估脚本，以及独立的 `rtt-module/` 资源与模块 |

**两个重要原则：**

1. **单机和联机不要同时运行。** 单机使用 `127.0.0.1:8000`、`127.0.0.1:5173`；联机 Host 默认使用所选 EasyTier 虚拟 IPv4 的 `8765/TCP`。启动脚本会检查模式冲突。
2. **源码目录与发行目录不同。** 项目根目录保存代码；构建完成的 Host / Guest ZIP 位于 `dist/`。不要把生成的 `build/`、`dist/` 和前端依赖目录误认作“整理失效”。

## 2. 工程目录

以下是本压缩包内的**实际布局**（只展示关键路径）：

```text
iron-bottom-sound/
├── README.md                         # 本说明文件（放在根目录）
├── start-game.bat                    # 单机启动入口
├── EasyTier双人联机.bat              # 源码版联机入口（Host / Guest 菜单）
├── Run-IBS-Setup.cmd                 # Windows 一键构建入口
├── Start_Guest.bat                   # 源码版 Guest 自动发现入口
├── pyproject.toml                    # Python 项目和依赖声明
├── .env.example                      # 可选环境变量示例
├── backend/
│   ├── src/iron_bottom_sound/        # FastAPI、规则引擎、对局与存档逻辑
│   ├── scripts/                      # 报告及辅助处理脚本
│   └── reports/                      # 本机报告（运行数据）
├── frontend/
│   ├── src/                          # React / TypeScript 前端
│   ├── vite.config.ts                # Vite 配置及 API 代理
│   └── solo-browser-presence.mjs     # 单机浏览器页面在线状态监控
├── lan/
│   ├── lan_server.py                 # 联机网关与大厅服务
│   ├── lan_dice.py                   # 联机骰子处理
│   ├── lan_dice_client.js            # 浏览器端联机骰子逻辑
│   ├── lan_lobby.html                # 联机大厅
│   ├── lan_seat.html                 # 阵营席位选择页
│   └── lan_unseal.py                 # 联机阶段撤回相关逻辑
├── CPU-RNG/
│   ├── ibs_cpu_rng.c                 # CPU 随机数模块源码
│   └── ibs_cpu_rng.dll               # 预编译 Windows x64 DLL
├── guest/auto_find_lobby.ps1         # Guest 自动发现联机房主
├── scripts/
│   ├── start-game.ps1                # 启动单机服务
│   ├── stop-game.ps1                 # 停止本工程的单机服务
│   ├── Watch-SoloBrowser.ps1         # 监控单机浏览器，触发自动停服
│   ├── game-runtime.ps1              # 进程归属与安全停止逻辑
│   ├── lan/start-easytier.ps1        # EasyTier 联机启动逻辑
│   ├── build/Build-Host.ps1          # Host 打包
│   ├── build/Build-Guest.ps1         # Guest 打包
│   ├── host/                          # Host 发行版启动文件
│   └── diagnostics/                  # 诊断脚本
├── set-up/
│   ├── Install-Build-IBS.ps1         # 一键构建主程序
│   ├── Check-Node.ps1                # Node 环境检查
│   ├── Cleanup-IBS-TemporaryApps.ps1 # 临时安装组件清理
│   └── Restore-IBS-Organized-Layout.ps1 # 整理旧版根目录重复文件
├── resources/
│   ├── originals/                    # 原始规则、想定、图像、舰艇记录
│   └── derived/                      # 结构化与衍生资源
├── docs/lan/                          # 联机专题文档（含历史说明）
├── rl/                                # AI 研究、训练与验证
├── rtt-module/                        # 相关独立模块和资产
└── skills/                            # 规则参考技能资料
```

**请勿将** `lan/` 中的脚本或 `CPU-RNG/` 中的 DLL 再复制回项目根目录。当前构建器和启动脚本已按整理后的路径定位这些文件。

## 3. 环境要求

### 3.1 开发、源码运行与构建

| 组件 | 要求 / 说明 |
| --- | --- |
| Windows | Windows 10/11，**x64** |
| PowerShell | Windows PowerShell **5.1 或更高版本** |
| Python | **3.11+，64 位**；已知源码可使用 Python 3.12 |
| Node.js | 一键构建器要求 **22+，64 位** |
| pnpm | 构建流程使用 **pnpm 10**；一键构建器会在项目临时目录中准备，不需要预先全局安装 |
| 浏览器 | Chrome、Edge 或其他现代浏览器 |
| EasyTier | **仅双人联机需要**；双方必须连接到同一可信私有网络 |
| Visual Studio C++ 构建工具 | 常规构建**不需要**；只有重新编译 `ibs_cpu_rng.dll` 时才需要 MSVC x64 工具链 |

一键构建器会优先使用已有的兼容 Python / Node.js。找不到兼容 Node 时，可下载经校验的便携版到项目临时位置；找不到 Python 时，可能使用 `winget` 临时安装。成功后按选项清理自身新增的构建工具，不会主动替换已有的 Python、Node 或 EasyTier。

### 3.2 检查本机环境

在项目根目录打开 PowerShell：

```powershell
python --version
node --version
npm --version
```

如果 Python、Node 安装在自定义位置（如 `D:\Python`、`D:\nodejs`），当前三个根目录启动器会优先尝试这些路径；其他位置应将其加入 `PATH`，或在构建器中明确指定解释器路径。

## 4. 单机游戏

### 4.1 第一次从源码运行：安装依赖

在项目根目录执行：

```powershell
python -m pip install -e .
cd frontend
npx --yes pnpm@10 install
cd ..
```

上述命令需要联网下载依赖。`npx` 随 Node.js/npm 提供；如果已有 `pnpm.cmd` 10.x，也可以在 `frontend/` 中直接运行 `pnpm.cmd install`。

> **注意：** `Run-IBS-Setup.cmd` 的构建环境使用临时 `.build-venv`，在成功构建后通常会删除它。因此**即使 Host/Guest 已经构建成功，若想运行源码单机，仍需保证启动脚本使用的 Python 环境安装了 `pyproject.toml` 中的依赖**。

### 4.2 启动

双击项目根目录的：

```text
start-game.bat
```

它会启动：

- 后端：`http://127.0.0.1:8000`（FastAPI / Uvicorn）；
- 前端：`http://127.0.0.1:5173`（Vite）；
- 默认浏览器中的游戏页面：`http://127.0.0.1:5173`。

你也可以在 PowerShell 中直接运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-game.ps1
```

### 4.3 关闭浏览器后自动停服

当前工程包含单机浏览器生命周期监控：

1. 正常启动后，前端向 `tmp/runtime/solo-presence.json` 更新页面在线状态。
2. **关闭最后一个单机游戏标签页**后，监控脚本调用 `scripts/stop-game.ps1`，尝试安全停止所属后端和前端进程。
3. 正常页面关闭后通常需约 **6–10 秒**；浏览器异常退出时使用约 **150 秒**无心跳兜底；如果启动后一直没有浏览器连接，监控约 **75 秒**后也会尝试停服。

这些是脚本设定的行为与预期时间，并非所有 Windows 浏览器环境都已验证。切换标签页不等于关闭；如果仍有其他游戏标签页，服务应继续运行。**请先保存游戏再关闭页面**，自动停服不负责替你保存未提交的操作。

如果没有自动停止，或要立即转为联机模式，手动执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop-game.ps1
```

确认两个单机端口已释放：

```powershell
Get-NetTCPConnection -LocalPort 5173,8000 -State Listen -ErrorAction SilentlyContinue
```

**没有输出**表示这两个端口当前没有处于监听状态的进程。若有输出，检查 `tmp/runtime/` 内的日志；不要在未核实进程归属前强制结束占用这些端口的其他程序。

**开发/无浏览器模式：** 使用 `scripts/start-game.ps1 -NoBrowser` 时，脚本刻意不启用浏览器自动停服，应使用 `scripts/stop-game.ps1` 结束服务。

## 5. EasyTier 双人联机

### 5.1 网络要求

- 房主与访客都需要连接到**同一个可信 EasyTier 虚拟网络**，并获得可互访的虚拟 IPv4。
- Host 服务默认监听 **EasyTier 虚拟 IPv4:8765**，不是公网或通用 `0.0.0.0` 地址。
- Windows 防火墙如有拦截，只应允许在需要的 EasyTier 地址/网络上访问 TCP `8765`，**不要进行公网端口映射**。
- 房主运行联机模式前，先确保单机的 `8000` 和 `5173` 端口已经关闭。

### 5.2 从源码启动联机

源码版 Host 需要有 Python 运行依赖和生产前端文件 `frontend/dist/index.html`。如果还未构建，推荐先运行一次 [一键构建](#6-一键构建-host--guest)；也可以在安装前端依赖后手动生成：

```powershell
cd frontend
npx --yes pnpm@10 install --frozen-lockfile
npx --yes pnpm@10 run build
cd ..
```

双击根目录：

```text
EasyTier双人联机.bat
```

菜单如下：

| 选项 | 含义 |
| --- | --- |
| `1` | **Host：恢复原房间**（断线重连优先使用） |
| `2` | **Host：新建房间**（轮换邀请凭证；旧邀请链接可能失效） |
| `3` | **Guest：通过房主私下提供的完整邀请 URL 加入** |
| `4` | **Host：指定私有 TOML 并启动 EasyTier Core** |
| `5` | 退出菜单 |

房主创建或恢复房间后，当前 `lan/lan_server.py` 会在服务就绪时**尝试自动打开本机浏览器中的阵营席位选择页面**，然后进入联机大厅。当前版本**不会为了加入房间再生成包含私有令牌的 `.url` 快捷方式**。其他玩家可使用 Guest 自动发现，或通过房主私下发送的完整邀请链接加入。

如果房主正在运行，不要因为玩家短暂掉线就选择 **2 新建房间**：这可能导致原邀请失效。创建新房间并不等于删除历史存档。

### 5.3 使用打包好的 Host / Guest

打包文件在：

```text
dist/IBS-Host-Windows-x64.zip
dist/IBS-Guest-Windows-x64.zip
```

**Host（房主）：**

1. 在房主电脑解压 `IBS-Host-Windows-x64.zip` 到可写目录。
2. 先连接 EasyTier。
3. 双击发行目录中的 `Start_Host.bat`。
4. 按提示恢复现有房间或创建新房间，并保持 Host 控制台运行。

**Guest（访客）：**

1. 在访客电脑解压 `IBS-Guest-Windows-x64.zip`。
2. 连接与房主相同的 EasyTier 网络。
3. 双击发行目录中的 `Start_Guest.bat`，自动搜索房主并在浏览器中打开联机页面。

Guest 发行包不包含游戏后端和数据库，通常不需要安装 Python 或 Node.js；它需要 Windows PowerShell、EasyTier 和浏览器。打包 Host 将 Python 网关及所需资源放入发行目录，也不要求玩家另外安装 Python/Node。

### 5.4 联机排查命令

在**访客电脑**的 PowerShell 中，用房主实际的 EasyTier IPv4 替换示例值：

```powershell
Test-NetConnection 10.0.0.10 -Port 8765
```

这里的 `10.0.0.10` **仅是占位示例，不是项目固定地址**。只有 `TcpTestSucceeded : True` 才代表对应 TCP 端口可连接；仍需继续检查页面、阵营权限与游戏同步。

若检测不到虚拟网卡，可运行：

```powershell
Get-NetAdapter -IncludeHidden | Format-Table Name, InterfaceDescription, Status
Get-NetIPAddress -AddressFamily IPv4 | Format-Table InterfaceAlias, IPAddress, AddressState
```

详细网络与发行说明参见 [`docs/lan/EASYTIER.md`](docs/lan/EASYTIER.md) 和 [`docs/lan/DISTRIBUTION.md`](docs/lan/DISTRIBUTION.md)，但其中提到的旧根目录路径或 `.url` 文件应以当前代码为准。

## 6. 一键构建 Host / Guest

### 6.1 推荐方式

**在已经解压的源码根目录双击：**

```text
Run-IBS-Setup.cmd
```

这个入口会调用：

```text
set-up/Install-Build-IBS.ps1
```

构建器大致按以下步骤工作：

1. 检查兼容的 Python 3.11+ / Node.js 22+（x64）。
2. 准备本项目临时使用的 pnpm 10 和 Python 虚拟环境。
3. 检查 `scripts/build/Build-Host.ps1`，编译前端并使用 PyInstaller 创建 Host。
4. 创建 Guest 自动发现启动包。
5. 验证两份 ZIP 及必要资源是否存在。
6. 成功时清理临时构建环境、已识别的嵌套 `__pycache__`、本次构建日志；根目录启动器还会调用整理脚本检查旧版重复文件。

输出：

```text
dist/
├── IBS-Host-Windows-x64.zip
├── IBS-Guest-Windows-x64.zip
├── Iron-Bottom-Sound-Host/      # Host 打包暂存目录
└── Iron-Bottom-Sound-Guest/     # Guest 打包暂存目录
```

> **测试说明：** 本次上传的源码中**没有根目录 `tests/`**。构建器发现指定的联机测试文件不存在时会**跳过自动化测试并发出警告**，但仍可打包。**ZIP 生成成功只证明构建和文件验证成功，不等于在另一台电脑上通过了完整联机验收。**

### 6.2 PowerShell 高级参数

从工程根目录运行（示例）：

```powershell
# 使用已有 Python / Node；不允许构建器临时安装新的系统应用
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\set-up\Install-Build-IBS.ps1 `
  -ProjectRoot (Get-Location).Path `
  -PythonPath 'D:\Python\python.exe' `
  -NodePath 'D:\nodejs\node.exe' `
  -NoAppInstall
```

其他可用参数包括 `-DiceMode cpu_rdseed|cpu_rdrand|os_csprng`、`-SkipTests` 和 `-KeepInstalledApps`。默认骰子模式为 `cpu_rdseed`。`-NoAppInstall` 表示禁止新增需要安装的应用，**并不意味着 pip/pnpm 构建依赖完全离线**。

如果需要仅打包 Guest，可单独运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build\Build-Guest.ps1
```

直接运行 `Build-Host.ps1` 则需要事先准备 `pnpm.cmd` 和 Python 环境；如果测试目录不存在，需要添加 `-SkipTests`。对于日常使用，优先选择一键入口以减少环境差异。

### 6.3 清理边界

构建器成功后可清理的临时项包括 `.build-venv/`、`.ibs-build-tools/`、`.pytest_cache/`、`.pytest-tmp/`、源码中的 `__pycache__/` 和本次成功构建日志。

**不应视为垃圾删除**：

- `frontend/dist/`：源码版联机服务需要的生产前端；
- `CPU-RNG/ibs_cpu_rng.dll`：CPU 骰子所需；
- `lan/` 下的联机核心源码及页面；
- `backend/*.sqlite3*`、`backend/lan-duel-room.json`、`backend/lan-saves/`、审计、检查点、报告；
- 需要交付的 `dist/IBS-Host-Windows-x64.zip` 与 `dist/IBS-Guest-Windows-x64.zip`。

缓存目录可能在下次运行 Python 后重新出现，这是 Python 的正常行为。构建失败时请**保留日志**以供排查。

## 7. 数据、存档及配置

| 路径 | 用途 | 处理建议 |
| --- | --- | --- |
| `backend/iron-bottom-sound.sqlite3` | 本机对局数据库 | **保留、备份；不得随发行包公开** |
| `backend/lan-duel-room.json` | 本机房间及相关状态 | 不要随意删除、分享 |
| `backend/lan-saves/` | Host 端联机存档 | 保留；读档前建议备份 |
| `backend/lan-dice-audit.jsonl` | 联机骰点审计 | 私有记录，不上传公共仓库 |
| `backend/lan-unseal-checkpoint.json` | 联机阶段撤回检查点 | 不要当缓存删除 |
| `backend/reports/` | 战斗报告 | 根据需要备份 |
| `tmp/runtime/` | 单机 PID、监控会话、运行日志 | 可用于问题诊断；不要在服务运行时清理 |
| `.env.example` | 可选环境变量示例 | **不包含真实密钥**；不要提交实际 `.env` |

本仓库源码压缩包已经包含 `backend/iron-bottom-sound.sqlite3`。如果你要对外发布或公开仓库，请在**复制出的干净发行副本**中检查并排除本机数据库、私有存档、审计与身份凭据，避免误泄露；不要为了发布而直接删除自己正在使用的原始存档。

### 可选环境变量

`pyproject.toml` 和 `.env.example` 提供如下配置线索：

```dotenv
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
IBS_DB_PATH=backend/iron-bottom-sound.sqlite3
```

其中模型相关变量仅在使用相应 AI 提供商功能时才可能需要；**普通单机和 EasyTier 双人联机不应要求提供第三方 API 密钥**。请根据实际代码和启动环境设置变量；不要假设复制 `.env.example` 为 `.env` 就一定会被所有脚本自动读取。

### 游戏资料

原始资料集中于：

- `resources/originals/rules/`：规则与辅助表 PDF；
- `resources/originals/scenarios/`：想定资料；
- `resources/originals/records/`：舰艇记录手册；
- `resources/originals/assets/images/`：地图与舰艇图像；
- `resources/derived/structured/`：引擎使用的结构化数据。

## 8. 故障排查

| 现象 | 排查方法 |
| --- | --- |
| 双击单机后网页打不开 | 检查 `python -m pip install -e .` 和 `frontend/node_modules/`；查看 `tmp/runtime/backend-error.log`、`frontend-error.log` |
| 浏览器已关闭，但 8000 / 5173 仍监听 | 等待监控清理；检查 `tmp/runtime/solo-auto-stop.log`、`solo-presence.json`；必要时手动运行 `scripts/stop-game.ps1` |
| 联机报 `Standalone server on TCP 8000 detected` | 先停止单机，再重新运行 `EasyTier双人联机.bat` |
| 联机提示 `frontend/dist/index.html missing` | 先构建前端或运行 `Run-IBS-Setup.cmd` |
| 没有找到 EasyTier IPv4 | 确认 EasyTier GUI / Core 已连接、虚拟网卡已 Up、IP 已分配 |
| Guest 发现不到 Host | 两机须处于同一虚拟网络；检查 Host 8765 监听和防火墙，使用 `Test-NetConnection` |
| `CPU-RNG/ibs_cpu_rng.dll` 缺失 | 恢复压缩包中预编译 DLL；不要把它移回根目录；确需不同随机源可显式选择 `os_csprng` |
| pip 升级时出现元数据 `TypeError` | 当前 `Build-Host.ps1` 在升级 pip 前检查**空的** `iron_bottom_sound.egg-info`，并给 pip 自升级添加 `--no-warn-conflicts`；确认使用的是这份新脚本及当前构建结果 |
| 提示缺少联机自动化测试 | 此压缩包没有根目录 `tests/`，构建器会跳过对应测试。需要另行在 Windows 双机环境验收 |
| 出现 `__pycache__` | 属于 Python 运行缓存；成功构建会尝试清理，但后续运行可重新生成 |

**端口检查：**

```powershell
Get-NetTCPConnection -LocalPort 5173,8000,8765 -State Listen -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

**单机服务手动关闭：**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop-game.ps1
```

**更深入的骰子诊断：**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\diagnostics\Diagnose-IBS-Dice.ps1
```

请勿仅因为端口被占用，就对所有 `python.exe` 或 `node.exe` 执行强制结束：可能误伤其他项目。当前停服脚本带有进程身份核对机制。

## 9. 开发与测试

### 9.1 技术栈

- **Python**：FastAPI、Uvicorn、Pydantic、HTTPX、Pillow、PyYAML；核心业务代码在 `backend/src/iron_bottom_sound/`。
- **前端**：React 19、TypeScript 5、Vite 7；主入口位于 `frontend/src/App.tsx`。
- **联机**：`lan/lan_server.py` 网关、HTML/JavaScript 大厅、`guest/auto_find_lobby.ps1`、EasyTier 私有网络。
- **打包**：PyInstaller（Windows Host `--onedir`）、PowerShell 构建脚本和 ZIP。

### 9.2 日常开发命令

```powershell
# 安装 Python 开发依赖（需要执行现有测试时）
python -m pip install -e ".[dev]"

# 前端编译检查与生产构建
cd frontend
npx --yes pnpm@10 install --frozen-lockfile
npx --yes pnpm@10 run build
cd ..

# Python 模块语法检查（不会启动服务器）
python -m py_compile .\lan\lan_server.py .\lan\lan_dice.py .\lan\lan_unseal.py
```

本上传包**未包含根目录 `tests/`**，因此不要把 `python -m pytest` 没有收集到业务测试、或构建脚本跳过测试，解读为联机行为已得到自动化验证。`rtt-module/tests/` 与主项目的 Python 业务测试并非同一套测试入口。

### 9.3 推荐回归验证

完成源码修改后，至少检查：单机启动与退出、单机端口自动释放、Host 恢复/创建房间、Guest 发现与进入、阵营占用与权限、双方操作同步、阶段封存/撤回、骰子记录、保存与读取，以及 Host/Guest ZIP 在独立 Windows 机器上的启动。

更多专题资料：

- [EasyTier 组网与源码入口](docs/lan/EASYTIER.md)
- [Windows Host / Guest 打包](docs/lan/DISTRIBUTION.md)
- [联机测试说明](docs/lan/TESTING.md)
- [联机维护说明](docs/lan/MAINTENANCE.md)
- [联机大厅存读档说明](docs/lan/EASYTIER_SHARED_LOBBY_SAVE.md)
- [AI / RL 研究](rl/README.md)
- [RL 设计文档](rl/DESIGN.md)

## 10. 安全和发布注意事项

1. **只在可信 EasyTier 网络中开放联机服务。** 不要把 `8765` 映射到公网；不应在物理网卡上扩大不必要的监听范围。
2. **保护邀请凭证与房间数据。** URL 中 `#` 后的票据及任何房间凭证都属于私有信息，不要粘贴到公开聊天、日志、GitHub Issue 或截图中。
3. **保护 EasyTier 配置。** 私有 TOML、网络口令及设备私钥不要提交仓库，也不要把同一台设备的身份密钥复制给其他玩家。
4. **区分构建产物与用户数据。** 发布 ZIP 时排除个人数据库、存档、报告、审计和凭证。备份时也要保留 SQLite 对应的 WAL/SHM（若存在），并在服务停止后的稳定状态处理。
5. **CPU RNG 模式必须如实标识。** `cpu_rdseed` 需要 CPU/原生 DLL 支持；不应将 `os_csprng` 的骰点记录冒称为 RDSEED。
6. **核实素材分发许可。** 上传的源码根目录未见统一 `LICENSE` 文件；不能据此推定规则 PDF、图片、舰艇记录及其他资料允许任意公开再分发。

---

**快速入口汇总**

| 需要做什么 | 应该使用什么 |
| --- | --- |
| 玩单机 | `start-game.bat` |
| 结束单机 | 关闭所有游戏标签页；必要时运行 `scripts/stop-game.ps1` |
| 从源码开 EasyTier 双人房间 | `EasyTier双人联机.bat` |
| 从源码查找房主 | `Start_Guest.bat` 或联机菜单选项 `3` |
| 一次生成 Windows Host + Guest | `Run-IBS-Setup.cmd` |
| 发行版房主启动 | 解压 Host ZIP 后运行 `Start_Host.bat` |
| 发行版访客启动 | 解压 Guest ZIP 后运行 `Start_Guest.bat` |
| 查看完整联机专题文档 | `docs/lan/` |

**文档维护约定：** 调整目录结构、启动器、联机接口或构建输出时，应同步更新本 README，避免重新使用历史补丁造成根目录文件重复或脚本路径回退。
