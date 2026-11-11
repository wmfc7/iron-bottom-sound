"""Anchored LAN gateway patch for a two-player gunnery report checkpoint.

No SQL or game-engine file is modified. Designed to fail safely if the gateway
has diverged. The installed LAN gateway is the only authority for advancing.
"""
from __future__ import annotations

MARK = '# IBS_LAN_GUNNERY_REPORT_CHECKPOINT_V6'


def exact(s: str, before: str, after: str, label: str) -> str:
    count = s.count(before)
    if count != 1:
        raise ValueError(f'{label}: expected one anchor, found {count}; no files changed')
    return s.replace(before, after, 1)


def patch_gateway(source: str) -> str:
    # The installer calls decode('utf8') on read_bytes(), which retains Windows
    # CRLF characters. All anchor and regex matches below expect LF. Normalize
    # only for matching, then restore the predominant original newline style.
    # This is intentionally inside this function: no files are written until
    # the installer's other source checks and syntax checks have succeeded.
    if MARK in source:
        return source
    if '\r' in source.replace('\r\n', ''):
        raise ValueError('Unsupported bare CR newline in lan_server.py; no files changed')
    crlf = source.count('\r\n')
    lf = source.count('\n') - crlf
    newline = '\r\n' if crlf > lf else '\n'
    source = source.replace('\r\n', '\n')
    if "from lan_dice import DiceBridge" not in source or "_dice_bridge.register(app, get_player, origin_ok)" not in source:
        raise ValueError('Expected installed LAN dice gateway; refusing unknown source')
    if source.count('async def settle_after_submit()') != 1 or source.count('async def reconcile_once()') != 1:
        raise ValueError('Gateway phase coordinator not recognized')

    # Trigger checkpoint immediately after the original engine has FINISHED
    # resolving gunnery. The next automatic phase is held until both see the
    # original viewer-filtered GunneryOutcomeModal and acknowledge it.
    # The previous v6 patch expected the two statements below to be adjacent:
    #     await advance_until_order_phase()
    #     after = await observation()
    # Local LAN gateways may have diagnostics or extra logic between them.
    # Identify only the single stage-forwarding statement in settle_after_submit.
    # Never patch other callers or guess when this call is missing/ambiguous.
    a = source.index('async def settle_after_submit()')
    b = source.index('async def reconcile_once()', a)
    before, section, after = source[:a], source[a:b], source[b:]
    import re
    matches = list(re.finditer(
        r'^(?P<indent>[ \t]*)await advance_until_order_phase\(\)[ \t]*(?:\#.*)?$',
        section, re.MULTILINE))
    if len(matches) != 1:
        raise ValueError(
            'after-gunnery transition: expected exactly one '
            'await advance_until_order_phase() within settle_after_submit; '
            f'found {len(matches)}. No files changed. '
            'Please provide the settle_after_submit function from lan_server.py '
            '(remove any tokens or passwords).')
    match = matches[0]
    indent = match.group('indent')
    # Install a checkpoint only after a successful gunnery engine advance.
    # Preserve the original transition and any code following it.
    checkpoint = (
        f"{indent}if response.get('phase') == 'gunnery':\n"
        f"{indent}    # IBS_LAN_GUNNERY_REPORT_CHECKPOINT_V6\n"
        f"{indent}    # The original gunnery advance completed and persisted.\n"
        f"{indent}    # Hold subsequent phases until both viewers acknowledge.\n"
        f"{indent}    _room['gunnery_checkpoint'] = {{\n"
        f"{indent}        'game_id': _room['game_id'], 'turn': response.get('turn'),\n"
        f"{indent}        'acks': {{'axis': False, 'allies': False}}}}\n"
        f"{indent}    save_room()\n"
        f"{indent}    print('[LAN GUNNERY] Waiting for report acknowledgements', flush=True)\n"
        f"{indent}    _last_error = ''\n"
        f"{indent}    return\n"
    )
    section = section[:match.start()] + checkpoint + section[match.start():]
    source = before + section + after

    # Manual retry and any other caller also respect the pause, not just the
    # recovery watchdog. Without this guard /lan/retry would skip the report.
    a = source.index('async def advance_until_order_phase()')
    b = source.index('async def settle_after_submit()', a)
    before, section, after = source[:a], source[a:b], source[b:]
    section = exact(section, '    global _last_error\n',
        '    global _last_error\n    if _room.get(\'gunnery_checkpoint\'):\n        return\n',
        'advance guard')
    source = before + section + after

    # Recovery watchdog and duplicate advance requests must respect checkpoint.
    a = source.index('async def reconcile_once()')
    b = source.index('async def recovery_watchdog()', a)
    before, section, after = source[:a], source[a:b], source[b:]
    old = """    async with _guard:
        try:
            state = await observation()
"""
    new = """    async with _guard:
        try:
            if _room.get('gunnery_checkpoint'):
                return  # Report is awaiting both players; do not auto-advance.
            state = await observation()
"""
    section = exact(section, old, new, 'watchdog checkpoint guard')
    source = before + section + after

    # Existing public lobby links and authorization stay unchanged.
    route = """
@app.get('/lan/gunnery/checkpoint')
async def lan_gunnery_checkpoint(request: Request):
    side = get_player(request)
    # This route reveals no other-side private events or game state.
    checkpoint = _room.get('gunnery_checkpoint')
    if not checkpoint or checkpoint.get('game_id') != _room.get('game_id'):
        return JSONResponse({'pending': False}, headers={'Cache-Control': 'no-store'})
    return JSONResponse({'pending': True, 'turn': checkpoint['turn'],
                         'acknowledged': bool(checkpoint['acks'].get(side))},
                        headers={'Cache-Control': 'no-store'})

@app.post('/lan/gunnery/ack')
async def lan_gunnery_ack(request: Request):
    side = get_player(request)
    if not origin_ok(request):
        raise HTTPException(403, 'Cross-origin acknowledgement rejected')
    async with _guard:
        checkpoint = _room.get('gunnery_checkpoint')
        if not checkpoint or checkpoint.get('game_id') != _room.get('game_id'):
            return {'pending': False}
        if checkpoint['acks'].get(side) is not True:
            checkpoint['acks'][side] = True
            save_room()
        if all(checkpoint['acks'].values()):
            _room.pop('gunnery_checkpoint', None)
            save_room()
            # Do not make a UI HTTP request wait for several subsequent rolls.
            asyncio.create_task(reconcile_once())
            return {'pending': False, 'both_confirmed': True}
        return {'pending': True, 'both_confirmed': False}

"""
    anchor = "@app.get('/lan/control', response_class=HTMLResponse)"
    source = exact(source, anchor, route + anchor, 'report route placement')
    return source.replace('\n', newline)
