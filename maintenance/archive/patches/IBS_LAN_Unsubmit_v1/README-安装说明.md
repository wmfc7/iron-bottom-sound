# 铁底湾 IV：单方封存撤回 v1

适用：`wmfc7/iron-bottom-sound` 的 `online` 分支，以及在其基础上安装了 LAN 双人联机、v5/v6 掷骰补丁且保留相同路由结构的本地源码。

## 新行为

- 只有本方已封存、另一方尚未封存、阶段仍可下令时，主按钮右边显示 **取消封存**。
- 点击按钮通过 `POST /lan/retract-orders` 请求服务器；服务器验证当前登录方，不信任客户端声称的阵营，并在同一把 `_guard` 锁内重新检查双方状态。
- 成功后恢复本方封存前的引擎状态（包含真实编队脱离等提交副作用），保留审计事件，且把本方原始 OrderBatch 返回给本方浏览器编辑。可以直接修改再封存。
- 对方先一步封存、阶段已推进、尚未封存、或缺少本阶段回滚快照时，服务端返回 HTTP 409，不执行撤回。客户端状态可能短暂滞后，但不能绕过服务器检查。
- 仅新增功能；不影响骰子权属、CPU RDSEED、规则表、联机大厅或原有战斗判定。

## 安装（Windows）

1. **先等所有裁决结束，关闭联机服务器**。备份 `backend/iron-bottom-sound.sqlite3`、`backend/lan-duel-room.json`、骰子审计日志及源码。安装过程中不要让另一程序改写游戏数据库。
2. 将 ZIP 内整个 `IBS_LAN_Unsubmit_v1` 文件夹放到仓库根目录：
   `C:\Users\19195\Desktop\iron-bottom-sound\IBS_LAN_Unsubmit_v1`。
3. 打开 PowerShell：

   ```powershell
   cd "C:\Users\19195\Desktop\iron-bottom-sound"
   python .\IBS_LAN_Unsubmit_v1\Install-Unsubmit-v1.py
   python -m py_compile lan_unseal.py lan_server.py
   cd frontend
   pnpm.cmd run build
   cd ..
   $env:IBS_DICE_SOURCE = "cpu_rdseed"
   python lan_server.py
   ```
4. 两位玩家各自按 `Ctrl+F5` 刷新浏览器。

## 测试

- 玩家 A 点击「校验、封存并交接」后，A 应看到右边出现「取消封存」，B 不显示。
- A 点击「取消封存」，返回先前的编辑草稿，修改后可以重新提交。
- A 和 B 都封存后，按钮对双方消失；即使使用浏览器控制台直接 POST，服务器也会返回 409。
- 双方均未封存时，按钮不可见。推进到下一阶段后同样不可见。
- 使用真实编队模式可测试一艘合法脱队舰：撤回后其编队状态应恢复。

## 版本、安全与边界

- **只对安装本补丁后新提交的单方计划创建可撤回快照。** 安装前已经封存、另一方尚未提交的旧计划缺少安全回滚快照，不能保证撤回；需在下一阶段验证。
- 回滚快照存放在主机 `backend/lan-unseal-checkpoint.json`。该文件包含私有战场和本方原始命令，已自动加入 `.gitignore`，不要上传或分享。它不通过网页公开。
- 游戏仓库采用追加式事件审计。撤回不会清理历史提交或脱队事件，而是追加 `orders_retracted`；历史事件可能继续出现在审计记录中。**完整事件重放与改动后的掷骰系统尚未做端到端验证**，请保留存档备份，先在新测试房间使用。
- 如果源文件与预期结构不一致，安装器会在写入前报错；不要强行删掉检查。安装器会备份修改过的源文件到 `ibs-unsubmit-v1-backup-*`。
- 这份补丁已通过独立模拟测试和 Windows CRLF 安装模拟，尚未在用户机器上的完整源码、React 构建或双人实机对局中验收。
