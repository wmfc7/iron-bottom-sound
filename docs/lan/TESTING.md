# 局域网测试说明

`pyproject.toml` 的 `testpaths = ["tests"]`，所以从项目根目录运行 `python -m pytest` 会收集 `tests/` 下符合 `test_*.py` 命名的测试。

本次将原先根目录的四个测试脚本保留为 `tests/lan/legacy/legacy_test_*.py`，**故意不让它们进入默认测试集**。这些测试模拟的是早期 v1/v2/v6 安装器和投骰交接；其中部分断言（如炮击毁伤由被攻击方投骰）已被后来规则取代，不得视作当前联机玩法的验收标准。

```powershell
# 当前项目常规测试
python -m pytest

# 当前联机目录契约检查
python -m pytest tests/lan/test_repository_contract.py

# 仅在核对了历史期望后，手动运行旧测试（可能按设计失败）
python -m pytest tests/lan/legacy/legacy_test_v6_2_crlf.py
```

修改联机功能时应新增针对当前规则的集成测试，包括：双方身份锁定、单方撤回、同时封存冲突、CPU RDSEED 失败不降级、命中/毁伤投骰方、炮击战果确认、两端结果同步、数据库和审计的恢复。不能只以静态契约测试通过作为联机验收。

如果你要将旧测试升级为正式测试，先重写过时的断言，放入 `tests/lan/test_*.py` 并在本机完成端到端验证。
