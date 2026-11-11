铁底湾 IV · 骰子请求拥塞解除补丁 v5（实验版）

原因（来自实际 py-spy 线程信息 + 两个浏览器的 /lan/dice/state）
* 游戏裁决正在等待第6次骰子，owner=allies、status=waiting。
* Chrome(同盟国) may_roll=true，Edge may_roll=false，权限映射正确。
* 原 LAN 网关在整个战斗裁决过程中持有 _guard，后台游戏查询可能长时间等待，从而占满浏览器连接。

本补丁改变了什么
1. 添加 /lan/dice/standalone 独立骰子页面，不加载原版 React 游戏界面。
   两方均可进入，只有服务器指定阵营才能投骰，继续使用原有的动画和规则表。
2. 裁决进行时，普通 GET /api/... 和 GET /lan/status 快速返回 HTTP 503 + Retry-After: 1，
   不再排队等待游戏对局锁。裁决完成后这些接口恢复原来的路由。
3. 不修改 CPU RDSEED、掷骰权限、骰点数值、审计日志、引擎或玩家存档。

注意：这个补丁需重启服务器才生效！
正在等待的第6次骰点是进程内状态。如果立刻重启会丢失它。
建议先用下文的浏览器恢复方法，完成当前裁决；或完整备份后在新测试局安装。

不重启恢复当前骰点（Chrome 是 may_roll:true 的同盟国浏览器）：
1. 关闭 Chrome 和 Edge 旧游戏标签页，保留 Chrome 的 /lan/dice/state 标签页。
2. 按 F12 > Console，粘贴下面 JS（仅向本机 /lan/dice/roll 投递一次，结果由服务器 RDSEED 产生）：
(async()=>{const r=await fetch('/lan/dice/state',{cache:'no-store'});const s=await r.json();if(s.seq!==6||s.status!=='waiting'||!s.may_roll){console.log('No action: state changed',s.seq,s.status,s.may_roll);return;}const q=await fetch('/lan/dice/roll',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:s.id})});console.log(q.status,await q.text());})()
3. 成功时会看到 HTTP 200 和 accepted:true，切勿再次执行。
   这次为恢复操作，不展示原版骰子动画，但保留服务器的实际骰点审计。
4. 在其他浏览器同样检查 /lan/dice/state：后续若轮到其他阵营，必须由相应有权限的浏览器操作。

安装方式（当前裁决完成并已备份、停止服务器后）：
在游戏项目根目录运行：
  python .\IBS_Dice_Unblock_v5\Install-Dice-Unblock-v5.py
  python -m py_compile lan_dice.py lan_server.py
  $env:IBS_DICE_SOURCE = 'cpu_rdseed'
  python lan_server.py
此时双方浏览器访问：
  http://192.168.1.3:8765/lan/dice/standalone
不再打开正常游戏页面来处理掷骰；一旦裁决结束，再返回游戏页面继续下令。

注意 v5 是针对先前 v4 的修复，安装器要求检查到 v4 的核心标记，不会覆盖不熟悉的版本。
若报告缺少 v4 标记，请勿硬改；提供当前 lan_dice.py 用于适配。
自动化测试：本地两项 v5 + v4 原测试四项通过。尚未在 Windows 双浏览器长期运行验收。
