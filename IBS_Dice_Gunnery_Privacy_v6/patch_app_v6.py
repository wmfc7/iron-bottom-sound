"""Targeted patch: use the original GunneryOutcomeModal in LAN mode."""
from __future__ import annotations

MARK = '// IBS_LAN_GUNNERY_OUTCOME_V6'

def exact(s: str, before: str, after: str, label: str) -> str:
    count = s.count(before)
    if count != 1:
        raise ValueError(f'{label}: expected one anchor, found {count}; no files changed')
    return s.replace(before, after, 1)

def patch_app(s: str) -> str:
    if MARK in s:
        return s
    if 'const LAN_MODE = ' not in s or 'GunneryOutcomeModal' not in s:
        raise ValueError('This is not the expected LAN-patched App.tsx')
    s = exact(s, 'import { useEffect, useMemo, useState } from "react";',
              'import { useEffect, useMemo, useState } from "react";', 'React import') if 'useRef' in s[:100] else s
    anchor = """  const llmConfig: LLMConnectionConfig = {"""
    inject = """  // IBS_LAN_GUNNERY_OUTCOME_V6
  // Reuse the original side-filtered artillery report instead of exposing raw
  // unfiltered world-state events. The server holds its next phase until both
  // players confirm this exact existing report modal.
  useEffect(() => {
    if (!LAN_MODE || !game || reportMode) return;
    let alive = true;
    let inFlight = false;
    let loadedKey: string | null = null;
    const check = async () => {
      if (!alive || inFlight) return;
      inFlight = true;
      try {
        const response = await fetch('/lan/gunnery/checkpoint', {
          credentials: 'same-origin', cache: 'no-store'
        });
        if (!response.ok) return;
        const state = await response.json() as {
          pending: boolean; turn?: number; acknowledged?: boolean
        };
        if (!state.pending || state.acknowledged || state.turn == null) return;
        const key = `${game}:${state.turn}`;
        if (loadedKey === key) return;
        // The existing /events endpoint is side-filtered by the LAN gateway.
        const events = await gameEvents(game, side, 0);
        if (!alive) return;
        loadedKey = key;
        setGunneryOutcome({
          events: events.filter(e => e.turn === state.turn &&
            (e.type === 'gun_mount_attack' || e.type === 'gunnery_result')),
          viewer: side, turn: state.turn
        });
      } catch (_) {
        // Retried on next poll. Never bypass the two-player report checkpoint.
      } finally { inFlight = false; }
    };
    void check();
    const timer = window.setInterval(() => { void check(); }, 1600);
    return () => { alive = false; window.clearInterval(timer); };
  }, [game, side, reportMode]);
  const closeGunneryOutcome = async () => {
    if (!LAN_MODE) { setGunneryOutcome(null); return; }
    try {
      const r = await fetch('/lan/gunnery/ack', {
        method: 'POST', credentials: 'same-origin', cache: 'no-store'
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setGunneryOutcome(null);
    } catch (err) {
      setError('无法确认炮击战果，请保持当前弹窗并重试：' + String(err));
    }
  };
"""
    s = exact(s, anchor, inject + anchor, 'App report hooks')
    before = 'onClose={() => setGunneryOutcome(null)}'
    n=s.count(before)
    if n!=2:
        raise ValueError(f'Expected 2 original gunnery modal close handlers, found {n}')
    s=s.replace(before,'onClose={() => { void closeGunneryOutcome(); }}')
    return s
