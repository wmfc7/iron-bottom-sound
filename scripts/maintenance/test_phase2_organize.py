from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path
import pytest

SCRIPT = Path(__file__).with_name('IBS_phase2_organize.py')


def shell(root, *args, expect=0):
    p=subprocess.run(args, cwd=root, capture_output=True, text=True, encoding='utf8', errors='replace')
    assert p.returncode == expect, (args, p.stdout, p.stderr)
    return p


def make_repo(path, crlf=False):
    path.mkdir()
    shell(path,'git','init','-q')
    shell(path,'git','config','user.email','test@example.com')
    shell(path,'git','config','user.name','Tests')
    files={
        'lan_server.py':'import lan_dice\nimport lan_unseal\n',
        'lan_dice.py':'SIDES=("axis","allies")\n',
        'lan_dice_client.js':'console.log("dice")\n',
        'lan_unseal.py':'class PendingSubmissionStore: pass\n',
        'lan_lobby.html':'<html></html>\n',
        'ibs_cpu_rng.c':'int main(void) { return 0; }\n',
        'ibs_cpu_rng.dll':'not-real-but-preserve\n',
        'build_cpu_rng.bat':'cl ibs_cpu_rng.c\n',
        'frontend/src/App.tsx':'export default function App() {return null;}\n',
        'README.md':'# Iron Bottom Sound\n',
        '.gitignore':'__pycache__/\nfrontend/dist/\n',
        'Diagnose-IBS-Dice.ps1':'param([int]$Port=8765)\n',
        '启动交互骰子联机-系统安全随机数测试.bat':'@echo off\npython lan_server.py\n',
        '局域网双人联机使用说明.md':'old guide\n',
        '使用说明-实验版.md':'old guide\n',
        '卡回合修复说明.txt':'old bug info\n',
        '安装与测试说明.md':'old guide\n',
        '安装说明.txt':'old guide\n',
        '联机准备大厅v3-安装说明.md':'old lobby\n',
        '启动联机骰子CPU-RDSEED.bat':'@echo off\nset IBS_DICE_SOURCE=cpu_rdseed\npython lan_server.py\n',
        '启动局域网双人对战.bat':'@echo off\npython lan_server.py\n',
        '新建联机房间.bat':'@echo off\npython lan_server.py --new-room\n',
        'test_dice_v2.py':"import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent))\nfrom lan_dice import SIDES\ndef test_a():\n    assert (Path(__file__).with_name('lan_server.py')).is_file()\n",
        'test_online_dice.py':"import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent))\nfrom lan_dice import SIDES\ndef test_a():\n    assert Path(__file__).parent.joinpath('lan_server.py').is_file()\n",
        'test_lan_duel.py': '"""Simulation."""\nimport sys\nimport lan_server\ndef test_ok(): assert True\n',
        'test_v6_2_crlf.py':"import sys\nfrom pathlib import Path\nTHIS = Path(__file__).resolve().parent\nsys.path.insert(0,str(THIS / 'IBS_Dice_Gunnery_Privacy_v6'))\ndef test_x(): assert True\n",
        'IBS_Dice_Gunnery_Privacy_v6/patch_gateway_v6.py':'def patch_gateway(s): return s\n',
    }
    for fn,text in files.items():
        target=path / fn
        target.parent.mkdir(parents=True, exist_ok=True)
        if crlf: text=text.replace('\n','\r\n')
        target.write_bytes(text.encode('utf-8'))
    shell(path,'git','add','.')
    shell(path,'git','commit','-qm','baseline')
    return files


def run_clean(path, *args, expect=0):
    return shell(path,sys.executable, str(SCRIPT),'--root',str(path),*args,expect=expect)


@pytest.mark.parametrize('crlf',[False, True])
def test_phase2_preview_apply_and_undo(tmp_path,crlf):
    root=tmp_path/'game'
    baseline=make_repo(root,crlf)
    pre=run_clean(root)
    assert '预览' in pre.stdout
    assert not (root/'docs/lan/README.md').exists()
    assert shell(root,'git','status','--porcelain').stdout == ''
    app=run_clean(root,'--apply')
    assert '备份和回退清单' in app.stdout
    assert (root/'docs/lan/README.md').exists()
    assert (root/'tests/lan/legacy/legacy_test_dice_v2.py').exists()
    assert not (root/'test_dice_v2.py').exists()
    assert 'ROOT = Path(__file__).resolve().parents[3]' in (root/'tests/lan/legacy/legacy_test_dice_v2.py').read_text()
    assert 'os_csprng' in (root/'scripts/lan/history/启动交互骰子联机-系统安全随机数测试.bat').read_text()
    assert (root/'ibs_cpu_rng.dll').read_bytes() == baseline['ibs_cpu_rng.dll'].replace('\n','\r\n' if crlf else '\n').encode('utf-8')
    assert 'lan-dice-audit.jsonl' in (root/'.gitignore').read_text()
    shell(root,sys.executable,'-m','pytest','-q','tests/lan/test_repository_contract.py')
    # To undo, read manifest path from log.
    manifest_line=next(x for x in app.stdout.splitlines() if x.startswith('备份和回退清单'))
    manifest=Path(manifest_line.split('：',1)[1])
    assert manifest.is_file()
    run_clean(root,'--undo',str(manifest))
    assert not (root/'docs/lan/README.md').exists()
    assert (root/'test_dice_v2.py').read_bytes()==baseline['test_dice_v2.py'].replace('\n','\r\n' if crlf else '\n').encode('utf-8')
    for fn in ('README.md','.gitignore','启动联机骰子CPU-RDSEED.bat'):
        assert (root/fn).read_bytes()==baseline[fn].replace('\n','\r\n' if crlf else '\n').encode('utf-8')
    assert shell(root,'git','status','--porcelain').stdout == ''


def test_refuses_dirty_and_collision(tmp_path):
    root=tmp_path/'game'
    make_repo(root)
    (root/'README.md').write_text('uncommitted\n')
    p=run_clean(root,'--apply',expect=1)
    assert '未提交' in p.stderr
    assert (root/'test_dice_v2.py').exists()
    shell(root,'git','checkout','--','README.md')
    (root/'docs/lan/README.md').parent.mkdir(parents=True)
    (root/'docs/lan/README.md').write_text('custom')
    p=run_clean(root,'--apply',expect=1)
    assert '目标已存在且内容不同' in p.stderr
    assert (root/'test_online_dice.py').exists()


def test_undo_refuses_modified_outputs(tmp_path):
    root=tmp_path/'game'
    make_repo(root)
    p=run_clean(root,'--apply')
    manifest=Path(next(x for x in p.stdout.splitlines() if x.startswith('备份和回退清单')).split('：',1)[1])
    (root/'docs/lan/README.md').write_text('user edited')
    rejected=run_clean(root,'--undo',str(manifest),expect=1)
    assert '已经变化' in rejected.stderr
    assert (root/'tests/lan/legacy/legacy_test_dice_v2.py').exists()


def test_second_execution_after_commit_is_idempotent(tmp_path):
    root = tmp_path/'game'
    make_repo(root,crlf=True)
    run_clean(root,'--apply')
    shell(root,'git','add','-A')
    shell(root,'git','commit','-qm','phase 2')
    again=run_clean(root,'--apply')
    assert '没有需要调整的内容' in again.stdout
    assert shell(root,'git','status','--porcelain').stdout == ''
    assert (root/'README.md').read_text().count('局域网双人对战（online-test）') == 1


def test_missing_legacy_files_are_nonfatal(tmp_path):
    root=tmp_path/'game'
    make_repo(root)
    # Simulates partially reorganized roots and retained entries from first-round cleanup.
    shell(root,'git','rm','-q','test_dice_v2.py')
    shell(root,'git','commit','-qm','previously removed legacy test')
    p=run_clean(root)
    assert 'SKIP' in p.stdout
    app=run_clean(root,'--apply')
    assert (root/'docs/lan/README.md').exists()
    assert 'test_dice_v2.py' not in [p.name for p in (root/'tests/lan/legacy').iterdir()]
