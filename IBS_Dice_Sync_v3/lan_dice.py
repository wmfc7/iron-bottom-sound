"""LAN dice bridge v3 for wmfc7/iron-bottom-sound online.

Only activated inside the LAN /advance context; rules engine remains authoritative.
CPU RDSEED requires separately compiled Windows native DLL. No silent RNG fallback.
Experimental: not yet replay-compatible / crash-transactional.
"""
from __future__ import annotations

import asyncio
import contextvars
import ctypes
import inspect
import json
import os
import platform
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

ACTIVE_DICE = contextvars.ContextVar('ibs_active_dice', default=None)
SIDES = ('axis', 'allies')
D66 = [10 * a + b for a in range(1, 7) for b in range(1, 7)]


def _side(obj: Any) -> str | None:
    val = getattr(obj, 'side', None)
    val = getattr(val, 'value', val)
    return val if isinstance(val, str) and val in SIDES else None


def _ship_label(obj: Any) -> str:
    return str(getattr(obj, 'name', '未知舰艇'))[:96] if obj is not None else '未知舰艇'


def _as_text(value: Any) -> str:
    mapping = {'miss': '无效果', 'Miss': '未命中', 'Sunk': '沉没', 'special': '特殊损伤',
               'primary_bow': '舰艏主炮', 'primary_stern': '舰艉主炮', 'primary_mid': '舰中主炮',
               'secondary': '副炮', 'radar': '雷达', 'fire_control': '火控', 'no_effect': '无效果',
               'special_damage': '特殊损伤'}
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return '、'.join(_as_text(x) for x in value)
    if isinstance(value, dict):
        alias = {'hull': '船体', 'speed_loss': '航速损失', 'primary': '主炮组',
                 'secondary': '副炮组', 'fire': '火灾', 'extinguish': '灭火',
                 'armour_check': '装甲检定', 'kind': '类型', 'rudder_hit': '舵机受损',
                 'narrative': '说明', 'applies_to': '适用舰', 'sunk': '沉没'}
        return '；'.join(f'{alias.get(str(k), str(k))}：{_as_text(v)}' for k, v in value.items())[:220]
    return str(value)


def _rule(rows: list[dict], title: str, note: str = '', kind: str = 'direct', modifier: int = 0, band: str = '') -> dict:
    return {'title': title, 'note': note, 'rows': rows[:48], 'kind': kind, 'modifier': modifier, 'band': band}


def _identify_roll(notation: str, state: Any) -> dict:
    """Engine-version-specific, conservative dispatch using exact caller names & lines.

    Only the matching engine caller is inspected. The previous broad search through
    arbitrary locals could assign ownership to the wrong ship during nested results.
    """
    stack = inspect.currentframe()
    try:
        while stack:
            name = stack.f_code.co_name
            loc = stack.f_locals
            if name == 'prepare' and stack.f_code.co_filename.replace('\\', '/').endswith('/savo.py'):
                data = loc.get('data', {})
                choices = data.get('reinforcement_table', {}) if isinstance(data, dict) else {}
                return {'owner': 'allies', 'reason': '萨沃岛增援判定',
                        'detail': '萨沃岛海战：同盟国增援舰队入场检定',
                        'rule': _rule([{'key': str(k), 'value': _as_text(v)} for k, v in sorted(choices.items(), key=lambda item: int(item[0]))],
                                      '萨沃岛增援表 · IBS-S-10-R20', '实际编队到场还取决于已到场组与想定特例')}
            if name.startswith('_') and name in (
                '_resolve_gunnery', '_resolve_torpedoes', '_resolve_fire',
                '_extra_fire_determination', '_resolve_special_damage',
                '_resolve_malfunction', '_resolve_reinforcements',
                '_resolve_optional_gunnery', '_apply_collision_damage',
                '_resolve_ship_collision', '_resolve_wreck_collision',
                '_move_squalls', '_destroy_gun_mounts',
            ):
                try:
                    return _context_from_frame(name, loc, stack, notation, state)
                except Exception as exc:
                    # A UI table projection must never corrupt the rules engine.
                    print('[LAN DICE] rule context rendering failed:', repr(exc), flush=True)
                    candidate = loc.get('ship') or loc.get('attacker') or loc.get('target')
                    return {'owner': _side(candidate) or 'axis',
                            'reason': '规则检定', 'detail': f'{_ship_label(candidate)} 的规则检定',
                            'rule': _rule([], '规则表不可用', '只影响表格显示，不影响引擎骰点与裁决')}
            stack = stack.f_back
    finally:
        del stack
    return {'owner': 'axis', 'reason': '通用规则检定', 'detail': '未识别到具体舰艇，暂由轴心国代投',
            'rule': _rule([], '通用规则检定', '请以游戏最终战报为准')}


def _context_from_frame(name: str, loc: dict, frame: Any, notation: str, state: Any) -> dict:
    # This is only a classifier. It must never mutate the engine or consume RNG.
    engine = loc.get('self')
    rules = getattr(engine, 'rules', None)
    attacker = loc.get('attacker')
    target = loc.get('target')
    ship = loc.get('ship')
    source_line = ''
    try:
        import linecache
        source_line = linecache.getline(frame.f_code.co_filename, frame.f_lineno)
    except Exception:
        pass
    owner_obj = ship or attacker or target
    reason, detail = '规则检定', '一般规则检定'
    table = _rule([], '本次规则', '对应规则表暂无法安全定位；实际结果仍由原版引擎裁决')
    modifier = 0
    if name == '_resolve_gunnery':
        # The two D66 sites are distinguished by exact source variable names.
        if 'result_roll' in source_line:
            owner_obj = target  # damage suffered by defender
            reason = '炮击毁伤判定'
            detail = f'{_ship_label(target)} 舰的炮击结果判定（攻击舰：{_ship_label(attacker)}）'
            if rules:
                table = _rule([{'key': str(v), 'value': _as_text(rules.gunnery_result(v))} for v in D66],
                              '炮击结果表 · IBS-T-GHRT', '每次命中分别掷一次 D66')
        else:
            owner_obj = attacker
            reason = '炮击命中判定'
            detail = f'{_ship_label(attacker)} 舰炮击 {_ship_label(target)} 舰 · 命中数判定'
            modifier = int(loc.get('modifier', 0))
            fp = loc.get('firepower')
            if rules is not None and isinstance(fp, (int, float)):
                rows = [{'key': str(v), 'value': f'{rules.hit_count(int(fp), v)} 发'} for v in D66]
                table = _rule(rows, f'炮击命中表 · GF={int(fp)} · IBS-T-GHT',
                              f'D66 修正：{modifier:+d} 步；按六进制序号移动（可能有想定特例）',
                              'd66_step', modifier)
    elif name == '_resolve_torpedoes':
        if 'raw_damage_roll' in source_line:
            owner_obj = target  # target rolls its damage
            reason = '鱼雷毁伤判定'
            detail = f'{_ship_label(target)} 舰的鱼雷效果判定（发射舰：{_ship_label(attacker)}）'
            definition = loc.get('definition')
            modifier = int(definition.get('damage_modifier', 0)) if isinstance(definition, dict) else 0
            band = str(getattr(target, 'displacement_band', ''))
            if rules is not None and band:
                rows = [{'key': str(v), 'value': _as_text(rules.torpedo_effect(v, band))} for v in range(2, 13)]
                table = _rule(rows, f'鱼雷效果表 · 排水量级 {band} · IBS-T-THDT',
                              f'原始2D6 {modifier:+d}；修正后8必定起火', 'clamp2d6', modifier, band)
        else:
            owner_obj = attacker
            reason = '鱼雷命中判定'
            detail = f'{_ship_label(attacker)} 舰鱼雷对 {_ship_label(target)} 舰的接触命中检定'
            try:
                modifier = int(engine._torpedo_modifier(state, attacker, loc.get('contact_target') or target, int(loc.get('distance', 1))))
            except (TypeError, ValueError, AttributeError, KeyError):
                modifier = 0
            table = _rule([{'key': str(v), 'value': f'舷侧 {0 if v < 11 else (1 if v < 13 else 2)}发 / 艏艉 {0 if v < 13 else 1}发'} for v in range(-3, 31)],
                          '鱼雷命中阈值 · IBS-R-08.2',
                          f'修正后2D6判定（命中修正 {modifier:+d}）；最终命中数受齐射枚数限制',
                          'add', modifier)
    elif name in ('_resolve_fire', '_extra_fire_determination'):
        owner_obj = ship if name == '_resolve_fire' else target
        reason = '火灾检定'
        detail = f'{_ship_label(owner_obj)} 舰的火灾持续及损伤判定'
        if rules is not None:
            modifier = int(rules.fire_table.get('modifiers', {}).get('ship_did_not_fire', 0)) if not getattr(owner_obj, 'fired', True) else 0
            ignored = rules.fire_table.get('modifiers', {}).get('ignore_results_if_ship_did_not_fire', [])
            rows = [{'key': str(v), 'value': ('无效果（未开火时忽略）' if modifier and v in ignored else
                      _as_text(rules.table_2d6(rules.fire_results, v)))} for v in range(2, 13)]
            table = _rule(rows, '火灾表 · IBS-T-FIRE',
                          f'本舰本回合未射击时 +{modifier}；特殊忽略结果仍以引擎裁决为准',
                          'cap12', modifier)
    elif name == '_resolve_special_damage':
        owner_obj = target
        reason = '特殊损伤判定'
        detail = f'{_ship_label(target)} 舰的特殊损伤判定'
        if rules is not None:
            band = str(getattr(target, 'displacement_band', ''))
            rows = [{'key': str(v), 'value': _as_text(rules.special_damage_result(v, band))} for v in D66]
            table = _rule(rows, f'特殊损伤表 · 排水量级 {band}', '装甲和特例由引擎继续核验')
    elif name == '_resolve_malfunction':
        owner_obj = attacker
        reason = '炮组故障判定'
        detail = f'{_ship_label(attacker)} 舰的66故障判定'
        if rules is not None:
            table = _rule([{'key': str(v), 'value': _as_text(rules.table_2d6(rules.malfunction_results, v))} for v in range(2, 13)],
                          '故障表 · IBS-R-09.5')
    elif name == '_resolve_reinforcements':
        reason, detail = '增援检定', '当前想定的增援舰队是否能够进场'
        options = sorted(getattr(state, 'reinforcement_succeeds_on', []) or [])
        rows = [{'key': str(v), 'value': '成功' if v in options else '失败'} for v in range(1, 7)]
        table = _rule(rows, '当前想定增援判定', f'成功骰点：{options}，以想定特殊规则为准')
        # There may be several reserve formations; do not invent an owning side.
        owner_obj = None
    elif name == '_resolve_optional_gunnery':
        owner_obj = ship
        reason, detail = '照明弹判定', f'{_ship_label(ship)} 舰的照明弹检定'
        table = _rule([{'key': str(v), 'value': '成功' if v >= 4 else '失败'} for v in range(1, 7)],
                      '照明弹检定 · IBS-R-09.3')
    elif name == '_apply_collision_damage':
        owner_obj = ship
        reason, detail = '碰撞损伤判定', f'{_ship_label(ship)} 舰的碰撞损伤判定'
        modifier = int(loc.get('modifier', 0))
        band = str(getattr(ship, 'displacement_band', ''))
        if rules is not None and band:
            table = _rule([{'key': str(v), 'value': _as_text(rules.torpedo_effect(v, band))} for v in range(2, 13)],
                          f'碰撞毁伤表 · {band}', f'骰点修正：{modifier:+d}', 'clamp2d6', modifier, band)
    elif name in ('_resolve_ship_collision', '_resolve_wreck_collision'):
        owner_obj = loc.get('left') if name == '_resolve_ship_collision' else ship
        reason, detail = '碰撞发生判定', f'{_ship_label(owner_obj)} 舰的碰撞检定'
        table = _rule([{'key': str(v), 'value': '碰撞' if v >= 5 else '未碰撞'} for v in range(1, 7)],
                      '碰撞判定 · IBS-R-06.4')
    elif name == '_move_squalls':
        owner_obj = None
        reason, detail = '天气检定', '风暴雨飑移动距离'
        table = _rule([{'key': str(v), 'value': ('0格' if v == 1 else ('2格' if v == 6 else '1格'))} for v in range(1, 7)],
                      '天气移动检定 · IBS-R-09.6')
    elif name == '_destroy_gun_mounts':
        owner_obj = ship
        reason, detail = '随机受损炮组', f'{_ship_label(ship)} 舰的随机炮组毁伤判定'
        table = _rule([{'key': str(v), 'value': '按当前可用炮组顺序选取'} for v in range(1, 7)],
                      '炮组选择', '具体炮组由引擎按可用炮组数量映射')
    owner = _side(owner_obj) or 'axis'
    return {'owner': owner, 'reason': reason, 'detail': detail, 'rule': table}


def _effective(raw: int, notation: str, rule: dict) -> int:
    kind = rule.get('kind')
    modifier = int(rule.get('modifier', 0))
    if notation == 'D66' and kind == 'd66_step':
        return D66[max(0, min(35, D66.index(raw) + modifier))]
    if kind == 'add':
        return raw + modifier
    if kind == 'cap12':
        return min(12, raw + modifier)
    if kind == 'clamp2d6':
        return max(2, min(12, raw + modifier))
    return raw


class RandomSource:
    """Explicit source selection: cpu_rdseed (default), cpu_rdrand, os_csprng.

    RDSEED/RDRAND are CPU instructions, not proof of ideal 'complete randomness'.
    Hardware nonavailability or errors never cause silent software fallback.
    """
    def __init__(self, mode: str | None = None, dll_path: str | None = None):
        self.mode = (mode or os.environ.get('IBS_DICE_SOURCE', 'cpu_rdseed')).lower()
        self.lock = threading.Lock()
        self.native = None
        self.method = {'cpu_rdseed': 1, 'cpu_rdrand': 2}.get(self.mode)
        if self.mode == 'os_csprng':
            return
        if self.method is None:
            raise RuntimeError('IBS_DICE_SOURCE 必须是 cpu_rdseed / cpu_rdrand / os_csprng')
        if os.name != 'nt' or platform.machine().lower() not in ('amd64', 'x86_64'):
            raise RuntimeError('CPU指令模式目前只支持64位 Windows x86-64 主机。')
        if ctypes.sizeof(ctypes.c_void_p) != 8:
            raise RuntimeError('需要安装 64 位 Python 才能加载 CPU 随机数 DLL。')
        path = dll_path or os.environ.get('IBS_DICE_CPU_DLL', str(Path(__file__).with_name('ibs_cpu_rng.dll')))
        if not Path(path).is_file():
            raise RuntimeError(f'找不到 {path}；请先在 x64 Native Tools 命令提示符运行 build_cpu_rng.bat')
        self.native = ctypes.CDLL(str(Path(path).resolve()))
        self.native.ibs_cpu_rng_supported.argtypes = [ctypes.c_int]
        self.native.ibs_cpu_rng_supported.restype = ctypes.c_int
        self.native.ibs_cpu_rng_byte.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_ubyte)]
        self.native.ibs_cpu_rng_byte.restype = ctypes.c_int
        if self.native.ibs_cpu_rng_supported(self.method) != 1:
            raise RuntimeError(f'本机CPU不支持 {self.mode}；不会降级为软件随机数。')

    def dice(self, count: int) -> list[int]:
        if count not in (1, 2):
            raise ValueError('仅支持1D6、2D6或D66')
        if self.mode == 'os_csprng':
            return [secrets.randbelow(6) + 1 for _ in range(count)]
        dice = []
        with self.lock:
            for _ in range(count):
                # Rejection sampling avoids modulo bias; native retries are bounded.
                for _attempt in range(512):
                    b = ctypes.c_ubyte()
                    if self.native.ibs_cpu_rng_byte(self.method, ctypes.byref(b)) != 1:
                        raise RuntimeError('CPU硬件随机数指令未能在限定重试次数内产生数据；本次投掷失败')
                    if b.value < 252:
                        dice.append((b.value % 6) + 1)
                        break
                else:
                    raise RuntimeError('CPU随机字节长期不满足无偏采样条件；拒绝本次投掷')
        return dice


class DiceBridge:
    def __init__(self, audit_file: Path, source: RandomSource | None = None,
                 animation_seconds: float = 2.4, hold_seconds: float = 2.2,
                 max_ack_wait_seconds: float | None = None):
        self.source = source or RandomSource()
        self.animation_seconds = animation_seconds
        self.hold_seconds = hold_seconds
        # Wait for both authenticated browsers to acknowledge the displayed result,
        # but never block the rules engine indefinitely if a player disconnects.
        override = os.environ.get('IBS_DICE_ACK_TIMEOUT')
        self.max_ack_wait_seconds = (float(override) if override else
                                     (max_ack_wait_seconds if max_ack_wait_seconds is not None
                                      else max(hold_seconds, 3 * hold_seconds)))
        if self.max_ack_wait_seconds < hold_seconds:
            raise ValueError('掷骰结果确认超时不能短于最小展示时间')
        self.audit_file = Path(audit_file)
        self.cv = threading.Condition()
        self.current: dict | None = None
        self.busy = False
        self.seq = 0
        self.session_game_id: str | None = None
        self._installed = False
        self._advance_task = None
        self.error = ''

    def install(self, engine_cls: type) -> None:
        if self._installed:
            return
        for method, notation in (('_roll_d6', '1D6'), ('_roll_2d6', '2D6'), ('_roll_d66', 'D66')):
            original = getattr(engine_cls, method)
            if getattr(original, '_ibs_lan_dice', False):
                raise RuntimeError('重复安装了掷骰拦截器')
            def patched(engine, state, original=original, notation=notation):
                bridge = ACTIVE_DICE.get()
                if bridge is None:
                    return original(engine, state)
                return bridge.request_roll(notation, state)
            patched._ibs_lan_dice = True
            setattr(engine_cls, method, patched)
        self._installed = True

    def _persist(self, row: dict) -> None:
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_file.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
            handle.flush()
            os.fsync(handle.fileno())

    def request_roll(self, notation: str, state: Any):
        context = _identify_roll(notation, state)
        with self.cv:
            if self.current is not None:
                raise RuntimeError('上一笔骰点尚未清理，禁止覆盖请求')
            self.seq += 1
            p = {'id': secrets.token_urlsafe(18), 'seq': self.seq,
                 'notation': notation, 'turn': getattr(state, 'turn', None),
                 'phase': str(getattr(getattr(state, 'phase', None), 'value', getattr(state, 'phase', ''))),
                 'game_id': getattr(state, 'game_id', self.session_game_id),
                 'owner': context['owner'], 'reason': context['reason'],
                 'detail': context['detail'], 'rule': context['rule'],
                 'status': 'waiting', 'dice': None, 'at': None,
                 'animation_start_ms': None, 'acknowledged': set(),
                 'source': self.source.mode}
            self.current = p
            self.cv.notify_all()
            while p['status'] == 'waiting':
                self.cv.wait()
            # No chance to roll twice. Both browsers see the same timed animation.
            until = p['at'] + self.animation_seconds
            while time.monotonic() < until:
                self.cv.wait(timeout=max(.01, until - time.monotonic()))
            p['status'] = 'revealed'
            self.cv.notify_all()
            revealed_at = time.monotonic()
            min_until = revealed_at + self.hold_seconds
            max_until = revealed_at + self.max_ack_wait_seconds
            # Both screens have to acknowledge this roll before changing its ID.
            # The deadline prevents permanent stalls if a browser is offline.
            while True:
                now = time.monotonic()
                if now >= max_until or (now >= min_until and len(p['acknowledged']) == 2):
                    break
                wait_until = min(max_until, min_until) if now < min_until else max_until
                self.cv.wait(timeout=max(.01, wait_until - now))
            dice = list(p['dice'])
            raw = (10 * dice[0] + dice[1]) if notation == 'D66' else sum(dice)
            state.rng_counter += 1
            self._persist({'id': p['id'], 'seq': p['seq'], 'game_id': p['game_id'],
                           'turn': p['turn'], 'phase': p['phase'], 'owner': p['owner'],
                           'notation': notation, 'reason': p['reason'], 'source': p['source'],
                           'dice': dice, 'raw': raw, 'unix_time': time.time()})
            if self.current is p:
                self.current = None
            self.cv.notify_all()
            return (raw, dice[0]) if notation == '1D6' else (raw, dice)

    def roll(self, side: str, roll_id: str) -> None:
        with self.cv:
            p = self.current
            if not p or p['status'] != 'waiting' or p['id'] != roll_id:
                raise HTTPException(409, '骰子请求已过期，请刷新')
            if side != p['owner']:
                raise HTTPException(403, '只有当前指定阵营可以投掷')
            try:
                dice = self.source.dice(1 if p['notation'] == '1D6' else 2)
            except Exception as exc:
                print('[LAN DICE] CPU RNG FAILED:', str(exc), flush=True)
                raise HTTPException(503, 'CPU硬件随机数不可用，未产生骰点，请检查主机') from exc
            p['dice'] = dice
            p['at'] = time.monotonic()
            p['animation_start_ms'] = int(time.time() * 1000)
            p['status'] = 'rolling'
            self.cv.notify_all()

    def acknowledge(self, side: str, roll_id: str) -> None:
        """Idempotent, authenticated acknowledgement of a *revealed* result."""
        with self.cv:
            p = self.current
            if not p or p['id'] != roll_id:
                raise HTTPException(409, '该骰点已经结束，请以服务器最新判定为准')
            if p['status'] != 'revealed':
                raise HTTPException(409, '骰点尚未揭晓，不能提前确认')
            if side not in SIDES:
                raise HTTPException(403, '无效的玩家阵营')
            p['acknowledged'].add(side)
            self.cv.notify_all()

    def public(self, side: str) -> dict:
        with self.cv:
            p = self.current
            if not p:
                return {'status': 'calculating' if self.busy else 'idle',
                        'source': self.source.mode, 'error': self.error}
            keys = ('id', 'seq', 'notation', 'owner', 'reason', 'detail', 'rule',
                    'turn', 'phase', 'status', 'source', 'animation_start_ms')
            info = {k: p[k] for k in keys}
            info['may_roll'] = side == p['owner'] and p['status'] == 'waiting'
            info['server_time_ms'] = int(time.time() * 1000)
            info['error'] = self.error
            # Optional fog-of-war protection. Shared detailed rule context can leak hidden ship metadata.
            if side != p['owner'] and os.environ.get('IBS_DICE_REDACT_OPPONENT') == '1':
                info['detail'] = '对方正在进行舰船规则检定（舰名隐藏）'
                info['rule'] = {'title': p['rule']['title'].split(' · ')[0],
                                'note': '为防止泄露战争迷雾，详细表格由掷骰方查看',
                                'rows': [], 'kind': 'direct', 'modifier': 0}
            if p['status'] == 'revealed':
                info['dice'] = list(p['dice'])
                raw = p['dice'][0] * 10 + p['dice'][1] if p['notation'] == 'D66' else sum(p['dice'])
                info['raw'] = raw
                effective = _effective(raw, p['notation'], p['rule'])
                info['adjusted'] = effective
                for row in info['rule']['rows']:
                    if str(row['key']) == str(effective):
                        info['outcome'] = row['value']
                        break
                else:
                    info['outcome'] = None
            return info

    async def advance(self, call_engine: Callable, path: str):
        """Cancellation-safe worker: client disconnect must NOT discard the current roll."""
        with self.cv:
            if self.busy:
                raise RuntimeError('已有裁决正在进行，请勿再次推进')
            self.busy = True
            self.error = ''
        def worker():
            token = ACTIVE_DICE.set(self)
            try:
                return asyncio.run(call_engine('POST', path, 'axis'))
            finally:
                ACTIVE_DICE.reset(token)
        task = asyncio.create_task(asyncio.to_thread(worker))
        self._advance_task = task
        def done(t):
            with self.cv:
                self.busy = False
                # No pending roll should remain on normal completion.
                self.current = None
                try:
                    exc = t.exception()
                    if exc is not None:
                        self.error = f'引擎裁决异常：{type(exc).__name__}（详见主机终端）'
                        print('[LAN DICE] advance failed:', repr(exc), flush=True)
                except asyncio.CancelledError:
                    self.error = '裁决工作线程被取消，请重启服务器并检查原版存档'
                self.cv.notify_all()
        task.add_done_callback(done)
        # Shield keeps the underlying worker (and rolls) alive if the HTTP client disconnects.
        return await asyncio.shield(task)

    def register(self, app: FastAPI, get_player: Callable, origin_ok: Callable) -> None:
        bridge = self
        @app.get('/lan/dice/state')
        async def dice_state(request: Request):
            side = get_player(request)
            return JSONResponse(bridge.public(side), headers={'Cache-Control': 'no-store'})
        @app.post('/lan/dice/roll')
        async def dice_roll(request: Request):
            side = get_player(request)
            if not origin_ok(request):
                raise HTTPException(403, '跨站投骰请求被拒绝')
            data = await request.json()
            rid = data.get('id') if isinstance(data, dict) else None
            if not isinstance(rid, str) or len(rid) > 128:
                raise HTTPException(422, '缺少有效骰点请求ID')
            await asyncio.to_thread(bridge.roll, side, rid)
            return JSONResponse({'accepted': True}, headers={'Cache-Control': 'no-store'})
        @app.post('/lan/dice/ack')
        async def dice_ack(request: Request):
            side = get_player(request)
            if not origin_ok(request):
                raise HTTPException(403, '跨站结果确认请求被拒绝')
            data = await request.json()
            rid = data.get('id') if isinstance(data, dict) else None
            if not isinstance(rid, str) or len(rid) > 128:
                raise HTTPException(422, '缺少有效骰点请求ID')
            await asyncio.to_thread(bridge.acknowledge, side, rid)
            return JSONResponse({'accepted': True}, headers={'Cache-Control': 'no-store'})

        @app.get('/lan/dice/client.js')
        async def dice_script(request: Request):
            get_player(request)
            script = Path(__file__).with_name('lan_dice_client.js').read_text(encoding='utf-8')
            return Response(script, media_type='application/javascript', headers={
                'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
