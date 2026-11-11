#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Iron Bottom Sound online-test, phase-2 cleanup.

Default: read-only preview. --apply: guarded, Git-aware changes. --undo MANIFEST: restore.
No game data, engine, active LAN modules, or CPU RNG DLL are modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

MOVES = {
    "Diagnose-IBS-Dice.ps1": "scripts/diagnostics/Diagnose-IBS-Dice.ps1",
    "启动交互骰子联机-系统安全随机数测试.bat": "scripts/lan/history/启动交互骰子联机-系统安全随机数测试.bat",
    "局域网双人联机使用说明.md": "docs/lan/history/局域网双人联机使用说明.md",
    "使用说明-实验版.md": "docs/lan/history/使用说明-实验版.md",
    "卡回合修复说明.txt": "docs/lan/history/卡回合修复说明.txt",
    "安装与测试说明.md": "docs/lan/history/安装与测试说明.md",
    "安装说明.txt": "docs/lan/history/安装说明.txt",
    "联机准备大厅v3-安装说明.md": "docs/lan/history/联机准备大厅v3-安装说明.md",
    "test_dice_v2.py": "tests/lan/legacy/legacy_test_dice_v2.py",
    "test_online_dice.py": "tests/lan/legacy/legacy_test_online_dice.py",
    "test_lan_duel.py": "tests/lan/legacy/legacy_test_lan_duel.py",
    "test_v6_2_crlf.py": "tests/lan/legacy/legacy_test_v6_2_crlf.py",
}

WRAPPERS = {
    "启动联机骰子CPU-RDSEED.bat": "cpu_rdseed",
    "启动局域网双人对战.bat": "inherit",
    "新建联机房间.bat": "inherit_new_room",
}

IGNORE = """# IBS LAN: private runtime data and rebuildable local outputs
/backend/lan-dice-audit.jsonl
/ibs_cpu_rng.obj
/ibs_cpu_rng.exp
/ibs_cpu_rng.lib
/ibs-dice-diagnostic-*/
/iron-bottom-sound-cleanup-report/
*.bak
"""

README_APPEND = """

## 局域网双人对战（online-test）

联机网关、人工骰子、CPU RDSEED、撤回封存及恢复注意事项请参阅
[局域网双人模式使用说明](docs/lan/README.md)。单机启动器与双人网关不是同一个服务。
"""

LAN_PS1 = r'''# PowerShell 5.1+, central launcher for the LAN duel gateway.
# This script never deletes a room, database, audit file, or checkpoint.
[CmdletBinding()]
param(
    [ValidateSet('cpu_rdseed', 'cpu_rdrand', 'os_csprng', 'inherit')]
    [string]$Mode = 'cpu_rdseed',
    [switch]$NewRoom,
    [string]$HostAddress = '0.0.0.0',
    [ValidateRange(1, 65535)] [int]$Port = 8765,
    [string]$Scenario = 'IBS-S-03'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not (Test-Path -LiteralPath (Join-Path $root 'lan_server.py') -PathType Leaf)) {
    throw 'Cannot find lan_server.py; wrong installation location.'
}
if ($Mode -ne 'inherit') {
    $env:IBS_DICE_SOURCE = $Mode
}
if ($Mode -eq 'cpu_rdseed' -and -not (Test-Path -LiteralPath (Join-Path $root 'ibs_cpu_rng.dll') -PathType Leaf)) {
    throw 'RDSEED DLL is missing. Build ibs_cpu_rng.dll first; no silent RNG fallback.'
}
$argsList = @('lan_server.py', '--host', $HostAddress, '--port', [string]$Port)
if ($NewRoom) {
    Write-Warning 'NewRoom rotates room tickets. Make sure both players are ready for a new room.'
    $argsList += @('--new-room', '--scenario', $Scenario)
}
Push-Location $root
try {
    & python @argsList
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw ('lan_server.py failed, exit code ' + $code) }
} finally {
    Pop-Location
}
'''

LAN_DOC = """# 局域网双人模式（online-test）

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
powershell -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\lan\\start-lan.ps1 -Mode cpu_rdseed
```

或者继续双击根目录的 `启动联机骰子CPU-RDSEED.bat`。默认监听 `0.0.0.0:8765`；游戏内邀请链接含身份令牌，只给对应玩家，勿上传到公开仓库。

只有主动开始新对局时才运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\lan\\start-lan.ps1 -Mode cpu_rdseed -NewRoom -Scenario IBS-S-03
```

**警告：** `-NewRoom` 会轮换邀请凭证，不能用来解决临时的骰子卡顿。调试 OS 系统随机源时需显式 `-Mode os_csprng`，不能把其记录称为 RDSEED。

## 安全与诊断

- 正常停止服务器后才归档文件；SQLite 主库、WAL、SHM 要作为同一时刻的状态处理。
- 骰点审计 `backend/lan-dice-audit.jsonl` 是本机记录，不要推送到 GitHub。若已被 Git 跟踪，先备份并执行 `git rm --cached -- backend/lan-dice-audit.jsonl`，确认 Git 变更后提交；历史提交中的内容不会因此消失。
- 检查阻塞：`powershell -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\diagnostics\\Diagnose-IBS-Dice.ps1`，请从项目根目录执行。
- 恢复卡住的阶段请优先查看主机日志和状态接口，不要清除房间 JSON、审计或数据库。

[测试与回归](TESTING.md) · [工程维护](MAINTENANCE.md)
"""

TESTING_DOC = """# 局域网测试说明

`pyproject.toml` 的 `testpaths = [\"tests\"]`，所以从项目根目录运行 `python -m pytest` 会收集 `tests/` 下符合 `test_*.py` 命名的测试。

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
"""

MAINT_DOC = """# 联机工程维护与归档

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
"""

STRUCTURE_TEST = r'''"""Non-invasive repository-layout checks; no game data or DLL is loaded."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[2]


def test_lan_runtime_entrypoints_remain_in_place():
    required = [
        'lan_server.py', 'lan_dice.py', 'lan_dice_client.js',
        'lan_unseal.py', 'lan_lobby.html', 'ibs_cpu_rng.c',
        'build_cpu_rng.bat', 'frontend/src/App.tsx',
    ]
    assert all((ROOT / rel).is_file() for rel in required)


def test_lan_python_sources_compile_without_importing():
    for name in ('lan_server.py', 'lan_dice.py', 'lan_unseal.py'):
        ast.parse((ROOT / name).read_text(encoding='utf-8'), filename=name)


def test_new_docs_and_launcher_exist():
    assert (ROOT / 'docs/lan/README.md').is_file()
    assert (ROOT / 'scripts/lan/start-lan.ps1').is_file()
'''

CREATES = {
    "scripts/lan/start-lan.ps1": LAN_PS1,
    "docs/lan/README.md": LAN_DOC,
    "docs/lan/TESTING.md": TESTING_DOC,
    "docs/lan/MAINTENANCE.md": MAINT_DOC,
    "tests/lan/test_repository_contract.py": STRUCTURE_TEST,
}


def encode_utf8(text: str, like: bytes | None = None) -> bytes:
    ending = '\r\n' if like and b'\r\n' in like else '\n'
    return text.replace('\r\n', '\n').replace('\n', ending).encode('utf-8')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    ret = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and ret.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {ret.stderr.strip()}")
    return ret


def validate_repo(root: Path) -> None:
    required = ('lan_server.py', 'lan_dice.py', 'lan_unseal.py', 'lan_dice_client.js', 'frontend/src/App.tsx', 'README.md', '.gitignore')
    if not (root / '.git').exists():
        raise RuntimeError('仓库根目录缺少 .git；只能在 Git 工作区运行')
    top = Path(git(root, 'rev-parse', '--show-toplevel').stdout.strip()).resolve()
    if top != root.resolve():
        raise RuntimeError(f'请在 Git 仓库根目录操作：{top}')
    if not all((root / x).is_file() for x in required):
        raise RuntimeError('缺少联机必要文件；不是预期的 online-test 游戏根目录')


def assert_clean_tracked(root: Path) -> None:
    if git(root, 'diff', '--quiet', check=False).returncode:
        raise RuntimeError('工作区有未提交的已跟踪修改，请先保存或提交')
    if git(root, 'diff', '--cached', '--quiet', check=False).returncode:
        raise RuntimeError('Git 暂存区已有修改，请先保存或提交')


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f'{label}: 预期 1 处锚点，实际 {source.count(old)} 处。未执行归档')
    return source.replace(old, new, 1)


def patch_legacy_text(src: str, data: bytes) -> bytes:
    text = data.decode('utf-8-sig').replace('\r\n', '\n')
    if src == 'test_dice_v2.py':
        text = replace_once(text, 'sys.path.insert(0, str(Path(__file__).parent))',
            "ROOT = Path(__file__).resolve().parents[3]\nsys.path.insert(0, str(ROOT))", src)
        text = replace_once(text, "Path(__file__).with_name('lan_server.py')", "ROOT / 'lan_server.py'", src)
    elif src == 'test_online_dice.py':
        text = replace_once(text, 'sys.path.insert(0, str(Path(__file__).parent))',
            "ROOT = Path(__file__).resolve().parents[3]\nsys.path.insert(0, str(ROOT))", src)
        text = replace_once(text, "Path(__file__).parent.joinpath('lan_server.py')", "ROOT / 'lan_server.py'", src)
    elif src == 'test_v6_2_crlf.py':
        text = replace_once(text, 'THIS = Path(__file__).resolve().parent',
            'ROOT = Path(__file__).resolve().parents[3]', src)
        text = replace_once(text, "THIS / 'IBS_Dice_Gunnery_Privacy_v6'",
            "ROOT / 'IBS_Dice_Gunnery_Privacy_v6'", src)
    elif src == 'test_lan_duel.py':
        text = replace_once(text, 'import sys\n',
            "import sys\nfrom pathlib import Path\nROOT = Path(__file__).resolve().parents[3]\nsys.path.insert(0, str(ROOT))\n", src)
    compile(text, src, 'exec')
    return encode_utf8(text, data)


def legacy_batch() -> str:
    return '''@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\\start-lan.ps1" -Mode os_csprng
if errorlevel 1 pause
'''


def launcher_batch(mode: str) -> str:
    room = ' -NewRoom -Scenario IBS-S-03' if mode == 'inherit_new_room' else ''
    selected = 'inherit' if mode == 'inherit_new_room' else mode
    return (f'@echo off\nchcp 65001 >nul\n'
            f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\\lan\\start-lan.ps1" -Mode {selected}{room}\n'
            'if errorlevel 1 pause\n')


def update_ignore(data: bytes) -> bytes:
    text = data.decode('utf-8-sig')
    newlines = [line for line in IGNORE.splitlines() if line and line not in text.splitlines()]
    if not newlines:
        return data
    return encode_utf8(text.rstrip('\r\n') + '\n\n' + '\n'.join(newlines) + '\n', data)


def update_readme(data: bytes) -> bytes:
    text = data.decode('utf-8-sig')
    if '[局域网双人模式使用说明](docs/lan/README.md)' in text:
        return data
    return encode_utf8(text.rstrip('\r\n') + README_APPEND, data)


def payload(root: Path):
    """Build change plan from local project; all transformations in memory."""
    moves, writes = [], {}
    for src, dst in MOVES.items():
        old, new = root / src, root / dst
        if old.is_file() and new.exists():
            raise RuntimeError(f'目标已存在，拒绝覆盖：{dst}')
        if not old.exists():
            if new.is_file():
                continue  # previously moved
            print(f'[SKIP] 文件不存在：{src}')
            continue
        if not old.is_file():
            raise RuntimeError(f'预期文件但不是文件：{src}')
        if not git(root, 'ls-files', '--error-unmatch', '--', src, check=False).returncode == 0:
            raise RuntimeError(f'不是 Git 跟踪文件，拒绝移动：{src}')
        moves.append((src, dst))
        if src.startswith('test_'):
            writes[dst] = patch_legacy_text(src, old.read_bytes())
        if src.startswith('启动交互骰子联机'):
            writes[dst] = encode_utf8(legacy_batch(), old.read_bytes())
    for rel, value in CREATES.items():
        if (root / rel).exists():
            if (root / rel).read_bytes() != value.encode('utf-8'):
                raise RuntimeError(f'目标已存在且内容不同，拒绝覆盖：{rel}')
            continue
        writes[rel] = value.encode('utf-8')
    for src, mode in WRAPPERS.items():
        path = root / src
        if path.is_file():
            content = encode_utf8(launcher_batch(mode), path.read_bytes())
            if content != path.read_bytes():
                writes[src] = content
    for rel, fun in [('.gitignore', update_ignore), ('README.md', update_readme)]:
        data = (root / rel).read_bytes()
        new_data = fun(data)
        if new_data != data:
            writes[rel] = new_data
    return moves, writes


def preview(root: Path) -> None:
    moves, writes = payload(root)
    print('第二轮整理：预览（没有修改任何文件）')
    print(f'Git 分支：{git(root, "branch", "--show-current").stdout.strip() or "(detached)"}')
    for src, dst in moves:
        print(f'  MOVE  {src}  ->  {dst}')
    for rel in sorted(writes):
        print(f'  WRITE {rel}  ({len(writes[rel])} bytes)')
    print(f'共 {len(moves)} 个移动、{len(writes)} 个文件写入。')
    print('不会读取/改写游戏数据库、运行态房间、骰点审计、RDSEED DLL、现行联机源码或前端构建目录。')
    if git(root, 'ls-files', '--error-unmatch', '--', 'backend/lan-dice-audit.jsonl', check=False).returncode == 0:
        print('警告：骰点审计仍由 Git 跟踪；后续请另行取消跟踪并检查 Git 历史。')


def backup_to(root: Path, paths: set[str], moves: list[tuple[str, str]]) -> tuple[Path, dict]:
    basedir = root.parent / f'{root.name}-phase2-backups'
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    folder = basedir / stamp
    folder.mkdir(parents=True, exist_ok=False)
    original = {}
    for rel in sorted(paths | {s for s, _ in moves}):
        src = root / rel
        if src.is_file():
            data = src.read_bytes()
            target = folder / 'original' / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            original[rel] = sha(data)
    return folder, original


def apply(root: Path) -> None:
    assert_clean_tracked(root)
    moves, writes = payload(root)
    if not moves and not writes:
        print('没有需要调整的内容。')
        return
    # Preflight: no change outside validated list; no ignored/nontracked file movement.
    for src, _ in moves:
        if git(root, 'ls-files', '--others', '--exclude-standard', '--', src).stdout.strip():
            raise RuntimeError(f'候选文件包含未跟踪内容，拒绝移动：{src}')
    for rel in writes:
        dest = root / rel
        if dest.exists() and rel not in MOVES.values() and rel not in WRAPPERS and rel not in ('.gitignore','README.md'):
            # Existing content already checked in payload().
            pass
    backup, originals = backup_to(root, set(writes), moves)
    log = {
        'repo': str(root.resolve()), 'moves': [], 'writes': [],
        'original_sha256': originals, 'post_sha256': {}, 'backup': str(backup),
    }
    manifest = backup / 'manifest.json'
    manifest.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        for src, dst in moves:
            (root / dst).parent.mkdir(parents=True, exist_ok=True)
            git(root, 'mv', '--', src, dst)
            log['moves'].append({'from': src, 'to': dst})
            print(f'MOVED  {src}  ->  {dst}')
            manifest.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding='utf-8')
        for rel, data in writes.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            log['writes'].append(rel)
            log['post_sha256'][rel] = sha(data)
            print(f'WROTE  {rel}')
            manifest.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        print(f'安装中断，备份清单位于 {manifest}；可使用 --undo 复原。', file=sys.stderr)
        raise
    print(f'\n备份和回退清单（在仓库外）：{manifest}')
    print('请先执行 python -m pytest tests/lan/test_repository_contract.py，再构建前端并验收双人对局。')
    print('新增文件可能尚未纳入 Git：检查 git status --short，确认后 git add -A。')


def undo(root: Path, manifest: Path) -> None:
    log = json.loads(manifest.read_text(encoding='utf-8'))
    if Path(log['repo']).resolve() != root.resolve():
        raise RuntimeError('回退清单不属于该仓库')
    backup = Path(log['backup'])
    # Refuse to lose edits made after apply; do not risk clobbering users' new work.
    for rel, expected in log['post_sha256'].items():
        path = root / rel
        if not path.is_file() or sha(path.read_bytes()) != expected:
            raise RuntimeError(f'回退前文件已经变化，拒绝覆盖：{rel}')
    for item in log['moves']:
        if not (root / item['to']).is_file() or (root / item['from']).exists():
            raise RuntimeError(f'回退移动状态不符合清单：{item}')
    for item in reversed(log['moves']):
        src, dst = item['from'], item['to']
        (root / src).parent.mkdir(parents=True, exist_ok=True)
        git(root, 'mv', '--', dst, src)
        print(f'RESTORED MOVE {dst} -> {src}')
    for rel in reversed(log['writes']):
        path = root / rel
        original = backup / 'original' / rel
        # Moved legacy test original sits under original source path, not its new destination.
        original_move = next((backup / 'original' / m['from'] for m in log['moves'] if m['to'] == rel), None)
        if original.is_file():
            path.write_bytes(original.read_bytes())
        elif original_move is not None and original_move.is_file():
            (root / next(m['from'] for m in log['moves'] if m['to'] == rel)).write_bytes(original_move.read_bytes())
        elif path.exists():
            path.unlink()
        print(f'RESTORED WRITE {rel}')
    # Any moved original that wasn't patched by script is already back via git mv.
    print('回退完毕。用 git status --short 检查暂存区；若未提交、且无其他改动，可按需恢复未暂存状态。')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--apply', action='store_true')
    group.add_argument('--undo', type=Path, metavar='MANIFEST_JSON')
    args = parser.parse_args()
    root = args.root.resolve()
    validate_repo(root)
    if args.undo:
        undo(root, args.undo.resolve())
    elif args.apply:
        apply(root)
    else:
        preview(root)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
