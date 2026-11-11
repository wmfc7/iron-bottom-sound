# 局域网双人模式（online-test）

本页说明当前根目录的联机入口；历史升级步骤已归档至 `docs/lan/history/` 或 `maintenance/archive/`，**不要在现行项目上重复运行旧安装器**。

## 结构与模式

- `lan_server.py`：唯一的局域网网关，维护双人身份与单进程裁决状态。
- `lan_dice.py`、`lan_dice_client.js`：CPU RDSEED / 互动骰子；`ibs_cpu_rng.dll` 必须放在根目录。
- `lan_unseal.py`：仅在一方已封存、另一方未封存时允许撤回。
- `lan_lobby.html`：准备大厅。`frontend/dist/` 是浏览器用的构建产物，**运行时不可删除**。
- `backend/`：数据库、凭证、骰点审计和撤回快照等本地状态，不属于缓存。

## 首次安装 / 修改前端后

在根目录执行：

```powershell
python -m pip install -e .
cd frontend
pnpm.cmd install
pnpm.cmd run build
cd ..
```

## 启动

在根目录启动局域网服务器（首选）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lan\start-lan.ps1 -Mode cpu_rdseed
```

或者继续双击根目录的 `启动联机骰子CPU-RDSEED.bat`。默认监听 `0.0.0.0:8765`；游戏内邀请链接含身份令牌，只给对应玩家，勿上传到公开仓库。

只有主动开始新对局时才运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lan\start-lan.ps1 -Mode cpu_rdseed -NewRoom -Scenario IBS-S-03
```

**警告：** `-NewRoom` 会轮换邀请凭证，不能用来解决临时的骰子卡顿。调试 OS 系统随机源时需显式 `-Mode os_csprng`，不能把其记录称为 RDSEED。

## 安全与诊断

- 正常停止服务器后才归档文件；SQLite 主库、WAL、SHM 要作为同一时刻的状态处理。
- 骰点审计 `backend/lan-dice-audit.jsonl` 是本机记录，不要推送到 GitHub。若已被 Git 跟踪，先备份并执行 `git rm --cached -- backend/lan-dice-audit.jsonl`，确认 Git 变更后提交；历史提交中的内容不会因此消失。
- 检查阻塞：`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\diagnostics\Diagnose-IBS-Dice.ps1`，请从项目根目录执行。
- 恢复卡住的阶段请优先查看主机日志和状态接口，不要清除房间 JSON、审计或数据库。

[测试与回归](TESTING.md) · [工程维护](MAINTENANCE.md)
