from __future__ import annotations
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE=Path(__file__).parent
V6=HERE.parent/'IBS_Dice_Gunnery_Privacy_v6'
installer_spec=importlib.util.spec_from_file_location('installer_v63',HERE/'Install-Dice-Privacy-UI-v6_3.py')
installer=importlib.util.module_from_spec(installer_spec)
installer_spec.loader.exec_module(installer)


def fixture_files():
    return (V6/'lan_dice.py').read_text(encoding='utf8'), (V6/'lan_dice_client.js').read_text(encoding='utf8')


def module():
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'lan_dice.py'
        py,_=fixture_files()
        path.write_text(installer.patch_backend(py),encoding='utf8')
        spec=importlib.util.spec_from_file_location('dice_v63_test',path)
        m=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        yield m


def test_patch_idempotence():
    py,js=fixture_files()
    p=installer.patch_backend(py)
    j=installer.patch_client(js)
    assert installer.patch_backend(p)==p
    assert installer.patch_client(j)==j
    assert "'_actor_roles': context.get('_actor_roles', {})" in p
    assert "'_rule_private_side': context.get('_rule_private_side')" in p
    assert 'position:fixed;right:18px;top:16px' not in j
    assert 'position:absolute;right:14px;top:14px' in j
    assert j.index('id="ibs-dice-shell" role="dialog"') < j.index('id="ibs-dice-restore" type="button"')
    # Both controls are inside the floating modal, not the page coordinate space.
    assert '#ibs-dice-banner {position:relative;' in j
    assert '#ibs-dice-shell {position:relative;' in j
    result=subprocess.run(['node','--check','-'],input=j,text=True,capture_output=True)
    assert result.returncode==0, result.stderr


def test_same_context_separately_redacted_for_both_sides():
    m=next(module())
    class Ship:
        def __init__(self,name,side,ident):
            self.name,self.side,self.id=name,side,ident
    attacker=Ship('青叶号','axis','JPN-AOBA-1')
    target=Ship('旧金山号','allies','USA-SF-1')
    class Rules:
        def hit_count(self, fp, dice): return 5
        def gunnery_result(self,v): return {'kind':'no_effect'}
    frame=SimpleNamespace(f_code=SimpleNamespace(co_filename='/fake-v63-engine.py'),f_lineno=1)
    import linecache
    linecache.cache['/fake-v63-engine.py']=(0,None,['     result_roll, x = self._roll_d66(state)\n'],'/fake-v63-engine.py')
    ctx=m._context_from_frame('_resolve_gunnery',{'self':SimpleNamespace(rules=Rules()),'attacker':attacker,'target':target},frame,'D66',None)
    assert ctx['owner']=='axis'
    assert set(ctx['_actor_roles']) >= {'attacker','target'}
    for side, visible, hidden in (('axis','青叶号','旧金山号'),('allies','旧金山号','青叶号')):
        detail, rules, invisible=m._viewer_projection(ctx,side)
        assert visible in detail
        assert hidden not in detail
        assert '***' in detail
        assert 'JPN-AOBA-1' not in json.dumps([detail,rules],ensure_ascii=False)
        assert 'USA-SF-1' not in json.dumps([detail,rules],ensure_ascii=False)


def test_rule_secret_not_leaked():
    m=next(module())
    p={'reason':'炮击命中判定','detail':'青叶攻击旧金山 机密',
       '_actor_roles':{'attacker':{'name':'青叶','side':'axis'},'target':{'name':'旧金山','side':'allies'}},
       '_rule_private_side':'axis',
       'rule':{'title':'GF=43', 'note':'机密配置123','rows':[{'key':'35','value':'命中4'}], 'modifier':7}}
    detail,rule,private=m._viewer_projection(p,'allies')
    assert '旧金山' in detail and '青叶' not in detail
    assert '***' in detail and private
    assert '43' not in str(rule) and '123' not in str(rule)
    detail,rule,private=m._viewer_projection(p,'axis')
    assert '青叶' in detail and '旧金山' not in detail and not private
    assert 'GF=43' in rule['title']


def test_no_metadata_fails_closed():
    m=next(module())
    detail,rule,private=m._viewer_projection({'reason':'炮击命中判定', 'detail':'秘密舰名 123',
                            'rule':{'title':'GF=123','rows':[{'key':'35','value':'12发'}]}},'axis')
    assert '秘密舰名' not in detail and '123' not in detail
    assert private and not rule['rows'] and '123' not in str(rule)


def test_request_roll_transfers_privacy_metadata():
    m=next(module())
    class FakeSource:
        mode='cpu_rdseed'
        def dice(self,n):return [3]*n
    class State:
        turn=1;phase='gunnery';game_id='FAKE';rng_counter=0
    state=State()
    b=m.DiceBridge(Path(tempfile.gettempdir())/'ibs-v63-test-audit.jsonl',source=FakeSource(),animation_seconds=0.01,hold_seconds=0,max_ack_wait_seconds=0.05)
    ctx={'owner':'axis','reason':'炮击毁伤判定','detail':'青叶攻击旧金山',
        'rule':{'title':'炮击结果表','rows':[{'key':'33','value':'无效果'}]},
        '_actor_roles':{'attacker':{'name':'青叶','side':'axis'},'target':{'name':'旧金山','side':'allies'}},
        '_rule_private_side':None,'_actors':[]}
    response=[]
    with patch.object(m,'_identify_roll',return_value=ctx):
        thread=threading.Thread(target=lambda:response.append(b.request_roll('D66',state)))
        thread.start()
        for _ in range(150):
            if b.current:break
            time.sleep(.01)
        assert b.current is not None
        assert b.current['_actor_roles']==ctx['_actor_roles']
        axis=b.public('axis'); allies=b.public('allies')
        assert '青叶' in axis['detail'] and '旧金山' not in axis['detail']
        assert '旧金山' in allies['detail'] and '青叶' not in allies['detail']
        b.roll('axis',b.current['id'])
        thread.join(timeout=3)
        assert not thread.is_alive()
        assert response==[(33,[3,3])]


def test_unsupported_version_fails_closed():
    import pytest
    with pytest.raises(RuntimeError):
        installer.patch_backend('def request_roll(): pass')
    with pytest.raises(RuntimeError):
        installer.patch_client('console.log("unrelated")')


def test_lf_crlf_normalization():
    py,js=fixture_files()
    assert installer.patch_backend(py.replace('\n','\r\n').replace('\r\n','\n'))
    assert installer.patch_client(js.replace('\n','\r\n').replace('\r\n','\n'))
