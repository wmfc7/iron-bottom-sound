"""Fail-closed patches for a LAN-patched iron-bottom-sound checkout."""
from __future__ import annotations

import ast
import re
from pathlib import Path

MARK_SERVER = "# IBS_LAN_UNSEAL_V1"
MARK_UI = "{/* IBS_LAN_UNSEAL_V1 */}"


def expect_one(text: str, needle: str, label: str) -> None:
    n = text.count(needle)
    if n != 1:
        raise ValueError(f"{label}: expected one anchor, found {n}; no files changed")


def patch_server(text: str) -> str:
    if MARK_SERVER in text:
        return text
    # Make newline-insensitive for Windows CRLF and restore original style on output.
    newline = "\r\n" if text.count("\r\n") >= max(1, text.count("\n") // 2) else "\n"
    text = text.replace("\r\n", "\n")
    if "async def settle_after_submit()" not in text or "@app.api_route('/api/{relative:path}'" not in text:
        raise ValueError("Not a recognized LAN gateway")
    anchor = "from pathlib import Path\n"
    expect_one(text, anchor, "gateway imports")
    text = text.replace(anchor, anchor + "from lan_unseal import PendingSubmissionStore, UnsealError  # IBS_LAN_UNSEAL_V1\n", 1)
    guard = "_room: dict = {}\n_last_error = ''\n"
    expect_one(text, guard, "gateway state")
    text = text.replace(guard, guard + "_unseal_store = PendingSubmissionStore(ROOT / 'backend' / 'lan-unseal-checkpoint.json')\n", 1)
    # Limit all changes to the orders branch of the LAN gateway.
    a = text.index("    if action == 'orders':")
    b = text.index("    body = await request.body()", a)
    section = text[a:b]
    post = "            res = await call_engine('POST', '/' + relative, side, json.dumps(payload).encode('utf-8'))\n"
    expect_one(section, post, "orders POST")
    section = section.replace(post,
        "            # Persist the pristine state BEFORE the first successful seal.\n"
        "            _unseal_store.prepare(upstream_api.get_game(_room['game_id']), side, payload)\n"
        + post +
        "            if res.status_code >= 400:\n"
        "                _unseal_store.discard_failed(_room['game_id'], side)\n", 1)
    text = text[:a] + section + text[b:]

    anchor = "@app.get('/lan/status')\n"
    expect_one(text, anchor, "LAN status route")
    route = '''@app.post('/lan/retract-orders')
async def lan_retract_orders(request: Request):
    side = get_player(request)
    if not origin_ok(request):
        raise HTTPException(403, '跨站撤回请求被拒绝')
    if not _room.get('game_id'):
        raise HTTPException(409, '当前房间尚未开始对局')
    # Same lock as submission and adjudication: check+restore are atomic.
    async with _guard:
        view = await observation(side)
        if (view.get('phase') not in ORDER_PHASES
                or not view.get('own_orders_submitted')
                or view.get('both_orders_submitted')):
            raise HTTPException(409, '只有本方已封存且对方尚未封存时可以撤回')
        state = upstream_api.get_game(_room['game_id'])
        try:
            outcome = _unseal_store.retract(state, side, upstream_api.engine, upstream_api.repository)
        except UnsealError as exc:
            raise HTTPException(409, str(exc)) from exc
        return JSONResponse({'ok': True, **outcome}, headers={'Cache-Control': 'no-store'})


'''
    text = text.replace(anchor, route + anchor, 1)
    ast.parse(text)
    return text.replace("\n", newline)


def patch_frontend(text: str) -> str:
    if MARK_UI in text:
        return text
    newline = "\r\n" if text.count("\r\n") >= max(1, text.count("\n") // 2) else "\n"
    s = text.replace("\r\n", "\n")
    if "const LAN_MODE = " not in s or "const act = async () => {" not in s:
        raise ValueError("Not an installed LAN frontend App.tsx")
    imports = 'import { useEffect, useMemo, useState } from "react";'
    if imports in s:
        s = s.replace(imports, 'import { useEffect, useMemo, useRef, useState } from "react";', 1)
    elif 'useRef' not in s.splitlines()[0]:
        raise ValueError('Unknown React import shape')
    anchor = '  const [draft, setDraft] = useState("");\n'
    expect_one(s, anchor, "draft state")
    s = s.replace(anchor, anchor + '  const retractedDraftRef = useRef<string | null>(null);\n', 1)
    # Preserve the player\'s original pre-processed submitted batch for editing.
    a = s.index('    if (view && game && orderPhases.has(view.phase) && !view.own_orders_submitted) {')
    b = s.index('      legalActions(game, side)', a)
    section = s[a:b]
    before = '''        setDraft("");
      suggestedOrders(game, side, guideProfiles[side])
        .then((batch) => {
          if (active) setDraft(JSON.stringify(batch, null, 2));
        })
        .catch(() => {
          if (active)
            setDraft(JSON.stringify(defaultBatch(view, side), null, 2));
        });
'''
    expect_one(section, before, 'draft restoration effect')
    after = '''        if (LAN_MODE && retractedDraftRef.current !== null) {
          setDraft(retractedDraftRef.current);
          retractedDraftRef.current = null;
        } else {
          setDraft("");
          suggestedOrders(game, side, guideProfiles[side])
            .then((batch) => {
              if (active) setDraft(JSON.stringify(batch, null, 2));
            })
            .catch(() => {
              if (active)
                setDraft(JSON.stringify(defaultBatch(view, side), null, 2));
            });
        }
'''
    section = section.replace(before, after, 1)
    s = s[:a] + section + s[b:]
    anchor = '  const act = async () => {\n'
    expect_one(s, anchor, 'act handler')
    handler = '''  const retractSealedOrders = async () => {
    if (!LAN_MODE || !game || !view || acting || llmBusy ||
        !orderPhases.has(view.phase) || !view.own_orders_submitted ||
        view.both_orders_submitted) return;
    setActing(true);
    try {
      const response = await fetch('/lan/retract-orders', {
        method: 'POST', credentials: 'same-origin', cache: 'no-store'
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      retractedDraftRef.current = JSON.stringify(data.draft, null, 2);
      await refresh(game, side);
      setError('');
    } catch (error) {
      setError('撤回封存失败：' + String(error));
      // Ensure a stale UI cannot keep offering an invalid withdrawal.
      try { await refresh(game, side); } catch (_) { /* Retry later */ }
    } finally {
      setActing(false);
    }
  };
'''
    s = s.replace(anchor, handler + anchor, 1)
    before = '''              : "执行引擎裁决"}
          </button>
        )}
      </header>'''
    expect_one(s, before, "submit button placement")
    after = '''              : "执行引擎裁决"}
          </button>
        )}
        {/* IBS_LAN_UNSEAL_V1 */}
        {LAN_MODE && orderPhases.has(view.phase) && view.own_orders_submitted &&
         !view.both_orders_submitted && (
          <button type="button" disabled={acting || llmBusy}
            onClick={() => { void retractSealedOrders(); }}
            title="仅在对方尚未封存本阶段计划时可撤回">
            取消封存
          </button>
        )}
      </header>'''
    s = s.replace(before, after, 1)
    return s.replace('\n', newline)
