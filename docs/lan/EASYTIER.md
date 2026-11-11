# EasyTier 异地双人联机与原版单机入口（online-test）

本版本**不修改规则引擎、封存交接、撤回计划、RDSEED 骰子与炮击战果**，只调整入口和联机访问地址。游戏裁决仍仅在**房主**的 `lan_server.py` 中运行，另一方只需要浏览器和 EasyTier 虚拟网络。

## 1. 整理后的入口

- `start-game.bat`：**原版单机**，依赖恢复的 `scripts/start-game.ps1` / `scripts/game-runtime.ps1` / `scripts/stop-game.ps1`。监听 `127.0.0.1:8000` 和 `127.0.0.1:5173`，启动后浏览器打开 `http://127.0.0.1:5173`。
- `EasyTier双人联机.bat`：**异地双人联机**，菜单包括：1）恢复现有房间；2）新建房间（会更换邀请凭证）；3）加入房间；4）启动 EasyTier Core 后开房。
- `scripts/lan/start-easytier.ps1`：主入口的实际 PowerShell 实现，可指定虚拟网卡别名、虚拟 IPv4、端口、骰子来源。
- `lan_server.py`、`lan_dice.py`、`lan_dice_client.js`、`lan_lobby.html`、`lan_unseal.py` 等现行核心文件**不移动**。
- 原根目录 `启动局域网双人对战.bat`、`启动联机骰子CPU-RDSEED.bat`、`新建联机房间.bat`、旧版安全随机数测试入口将先备份到 Git 仓库**外部**再从根目录移除；保留的 `scripts/lan/start-lan.ps1` 属于历史/兼容命令，不是新的推荐入口。

## 2. EasyTier 组网：双方都要安装并连接

你提供的 TOML 启用了 `dhcp = true`，**没有静态 IPv4**。因此本补丁不猜测或硬编码 `10.126.126.x`，启动时实际读取 Windows 中处于 Up 状态的 EasyTier 网卡 IPv4。使用共享节点时，房主和访客必须加入同一 EasyTier 虚拟网络；仅共享节点在线、双方未互通时仍无法联机。EasyTier 在穿透失败时可以通过共享节点转发数据（前提是双方配置允许中继）。

### 推荐：两台电脑都提前打开 EasyTier GUI

1. 分别将 EasyTier GUI 配置为相同的虚拟网络，确认双方在线且出现虚拟 IP。不同电脑需要各自的设备身份，**不要复制同一个 `secure_mode.local_private_key` 给对手**。
2. 只在房主的游戏目录双击 `EasyTier双人联机.bat`，选择 **1**（恢复现有房间），或者明确要换房间才选 **2**。脚本只在检测到单一、已启用的 EasyTier IPv4 地址时启动网关，并将 TCP `8765` **仅绑定这个虚拟地址**。
3. 房主终端会显示轴心国和同盟国各自的邀请 URL：`http://房主EasyTier_IP:8765/join#专用令牌`。每条邀请链接只发给对应玩家；**不要发到公开群聊、GitHub 或截图**。
4. 两人在各自浏览器打开对应完整邀请链接（包含 `#` 后面的令牌），将进入原有联机大厅。访客不需要安装游戏后端，只需要 EasyTier 与浏览器。
5. 访客若也有此项目，可双击同一入口选择 **3**，输入房主私发的完整邀请链接。脚本会进行 TCP 测试并打开浏览器。

### 网卡名称不是 EasyTier 时

打开 PowerShell（无需先重新安装网卡）：

```powershell
Get-NetAdapter -IncludeHidden | Format-Table Name, InterfaceDescription, Status
Get-NetIPAddress -AddressFamily IPv4 | Format-Table InterfaceAlias, IPAddress, AddressState
```

如果网卡实际名称不是 EasyTier，但你确定它是 EasyTier 网卡，可手工指定：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lan\start-easytier.ps1 -Mode Host -AdapterName '你的实际虚拟网卡名称' -VpnIPv4 '你的虚拟IPv4'
```

脚本必须核实指定 IPv4 **确实属于该 Up 状态的网卡**，否则拒绝启动。不要把物理路由器分配的 `192.168.1.x` 冒充 EasyTier 地址。

### 可选：用私有 TOML 启动 EasyTier Core

如果没有使用 GUI，可以使用 GUI 导出至你自己电脑的 TOML，推荐放在项目目录**之外**（例如用户文档目录）。EasyTier 官方支持 `easytier-core -c 文件.toml`。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lan\start-easytier.ps1 `
  -Mode Host -StartCore -EasyTierConfig 'C:\Users\你的用户名\Documents\EasyTier\host-private.toml' `
  -CoreExe 'C:\EasyTier\easytier-core.exe'
```

要求 Windows TUN 网卡驱动可用，必要时以管理员权限运行；如你的 EasyTier GUI 已在运行则不要再开第二份 Core。脚本不复制、读取正文或打印 TOML 的私钥/网络口令；也不会把它加入 ZIP 包或 Git 仓库。如果 Core 启动失败，请先在 EasyTier 软件内解决驱动/配置问题。

## 3. Windows 防火墙与诊断

**不要把公网或物理局域网端口映射到 8765。**房主脚本已经将网关监听到 EasyTier 虚拟 IP。如果网络连通但网页打不开，可先在访客电脑运行：

```powershell
Test-NetConnection <房主虚拟IPv4> -Port 8765
```

房主确认本机 VPN IPv4 后，可以**以管理员 PowerShell**建立仅作用于 VPN IPv4 的入站规则（把示例 IPv4 换成房主实际地址）：

```powershell
New-NetFirewallRule -DisplayName 'IBS EasyTier 8765' -Direction Inbound `
  -Action Allow -Protocol TCP -LocalAddress <房主虚拟IPv4> -LocalPort 8765 -Profile Any
```

这只是建议命令，启动器**不会自动修改防火墙**。虚拟 IP 若因 DHCP 变化，请更新该规则的 LocalAddress。需要删除规则时：

```powershell
Remove-NetFirewallRule -DisplayName 'IBS EasyTier 8765'
```

如存在连接故障，依次检查：两台机器是否都加入**同一虚拟网络**、EasyTier 节点表里是否存在彼此、双方虚拟 IP 是否可互访、房主脚本显示的监听 IP 是否正确、端口 `8765` 是否在房主 Windows 防火墙放行。`easytier-cli peer` 和 `easytier-cli node` 可用于观察组网状态（如已安装命令行程序）。

## 4. 单机模式恢复

双击**原来的** `start-game.bat`；此补丁会将 `scripts/start-game.ps1`、`scripts/game-runtime.ps1` 和 `scripts/stop-game.ps1` 恢复到原项目所用位置，并设置单机服务只监听本机回环地址。

如果是首次安装依赖：

```powershell
python -m pip install -e .
cd frontend
pnpm.cmd install
cd ..
```

单机启动后浏览器应访问 `http://127.0.0.1:5173`。停止单机：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop-game.ps1
```

**不要同时运行单机后端与联机网关**：联机网关会拒绝在 `8000` / `5173` 端口已经监听时启动。单机启动也会提示先关闭 `8765` 的联机网关。这个限制阻止原版单机 API 绕过联机阵营隔离。

## 5. 数据和隐私安全

- 不会删除 `backend/iron-bottom-sound.sqlite3`（含 WAL/SHM）、`backend/lan-duel-room.json`、`backend/lan-dice-audit.jsonl`、`backend/lan-unseal-checkpoint.json`。
- 旧房间默认恢复；选择 **2 新建房间** 才会轮换双方的邀请凭证。不要因临时网络掉线而新建房间。
- 提供给助手的 EasyTier TOML 包含网络口令和设备身份私钥。**不要将原 TOML 提交到 GitHub，也不要将同一个设备私钥复制给对方**；如曾公开或泄露，请轮换网络口令与相应设备密钥。
- 双方拥有不同的阵营邀请令牌。必须信任加入同一 EasyTier 网络的其他设备；本脚本没有改变现有 Web 网关的身份认证模型。
- 不要把项目的本地数据库、运行审计或 EasyTier 配置发布到公共仓库。

## 6. 安装/回滚

先停止两种游戏服务器，备份存档，并从干净的 `online-test` 工作树安装。**推荐将工具包解压到游戏仓库之外**（如下载目录），避免再次让根目录变得杂乱；运行安装器时显式指定 `--root`：

```powershell
python "C:\Users\你的用户名\Downloads\IBS_EasyTier_Entry_v1\install_easytier_entry.py" --root . --check
python "C:\Users\你的用户名\Downloads\IBS_EasyTier_Entry_v1\install_easytier_entry.py" --root . --install
```

原有入口以及会被覆盖的脚本保存在工程目录**旁边**的 `iron-bottom-sound-easytier-rollback/`。若要撤回：

```powershell
python "C:\Users\你的用户名\Downloads\IBS_EasyTier_Entry_v1\install_easytier_entry.py" --root . --undo '上次安装输出的完整manifest.json路径'
```

脚本校验安装后文件哈希，若其后有新的手工编辑，会停止回滚而非覆盖。

## 7. 源码与官方说明

- EasyTier 官方：[快速组网](https://www.easytier.cn/guide/network/quick-networking.html)、[配置文件](https://www.easytier.cn/en/guide/network/config-file.html)
- 当前代码：[iron-bottom-sound online-test](https://github.com/wmfc7/iron-bottom-sound/tree/online-test)
