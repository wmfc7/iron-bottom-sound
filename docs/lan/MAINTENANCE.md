# 联机工程维护与归档

## 不可作为垃圾删除

`lan_server.py`、`lan_dice.py`、`lan_dice_client.js`、`lan_unseal.py`、`lan_lobby.html`、`ibs_cpu_rng.dll`、`frontend/dist/`（服务在运行时）、`backend/*.sqlite3*`、`backend/lan-duel-room.json`、`backend/lan-unseal-checkpoint.json`、`backend/lan-dice-audit.jsonl`。

## 阶段二维护规范

- 旧补丁目录在 `maintenance/archive/` 留存；不要把补丁目录里的源码当做现行版本。
- 联机正式回归测试集中放 `tests/lan/`；旧测试保留于 `tests/lan/legacy/`，先核验版本再运行。
- 联机说明在 `docs/lan/`，历史安装步骤在 `docs/lan/history/`。
- 根目录 `.bat` 仍保留兼容入口，它们委托给 `scripts/lan/start-lan.ps1`；诊断脚本在 `scripts/diagnostics/`。
- 编译输出 `.obj/.lib/.exp` 可以本机重新生成，不要删除正在使用的 `ibs_cpu_rng.dll`。
- `frontend/node_modules` 由 `pnpm.cmd install` 重建；`frontend/dist` 由 `pnpm.cmd run build` 重建，但服务依赖它，**不能运行时删除**。本轮不会自动删除任何缓存或产物。

## 已跟踪产物与审计文件

新增 `.gitignore` 对 **已由 Git 跟踪** 的文件没有取消跟踪的作用。如果你确认不再将本机审计与本机的 DLL 链接临时产物提交 Git，可先建立私有备份，然后执行：

```powershell
git rm --cached -- backend/lan-dice-audit.jsonl
git rm --cached -- ibs_cpu_rng.obj ibs_cpu_rng.lib ibs_cpu_rng.exp
```

`--cached` 仅从 Git 索引移除，不删除工作区文件。执行 `git status --short` 确认，检查是否涉及历史秘密；既有 Git 提交**不会**自动被清除。规则检索数据库 `resources/derived/rag/iron_bottom_sound_rules.sqlite3` 暂不改变跟踪状态，应单独核对许可与重建方式。

## 验收

```powershell
python -m py_compile lan_server.py lan_dice.py lan_unseal.py
python -m pytest tests/lan/test_repository_contract.py
cd frontend
pnpm.cmd run build
cd ..
git status --short
```

然后用双方浏览器验证：加入大厅、封存/撤回、不同阵营投骰权限、完整判定信息、收起/展开、炮击结束原版战果、后续阶段继续。通过后才提交第二轮整理。
