"""Private reversible first-submission checkpoint for the LAN gateway.

Only the gateway calls this module while holding its single asyncio _guard.
Never mount CHECKPOINT_PATH as a public static path.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path


class UnsealError(Exception):
    """A rejected retraction (safe to report as HTTP 409)."""


class PendingSubmissionStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _load(self) -> dict | None:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def _save(self, record: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Do not write full private game state to a public directory.
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, self.path)
        finally:
            tmp.unlink(missing_ok=True)

    def prepare(self, state, side: str, original_draft: dict) -> None:
        if set(state.submitted_orders):
            # Never overwrite a checkpoint for another side.
            # In ordinary LAN flow the only submission requiring a checkpoint
            # is the first one, before either side has sealed.
            return
        record = {
            "game_id": state.game_id,
            "turn": state.turn,
            "phase": state.phase.value,
            "side": side,
            "event_count": len(state.events),
            "snapshot": state.model_dump(mode="json"),
            "draft": original_draft,
        }
        self._save(record)

    def discard_failed(self, game_id: str, side: str) -> None:
        record = self._load()
        if record and record.get("game_id") == game_id and record.get("side") == side:
            self.path.unlink(missing_ok=True)

    def can_retract(self, state, side: str) -> bool:
        record = self._load()
        return bool(record and record.get("game_id") == state.game_id
                    and record.get("side") == side
                    and record.get("turn") == state.turn
                    and record.get("phase") == state.phase.value
                    and set(state.submitted_orders) == {side}
                    and len(state.events) > record.get("event_count", 100000000)
                    and state.events[-1].type == "orders_submitted"
                    and state.events[-1].payload.get("secret_side") == side
                    # Realistic movement submission may emit ship_detached events
                    # before the order itself is sealed.
                    and all(e.type == "ship_detached" for e in
                            state.events[record["event_count"]:-1]))

    def retract(self, state, side: str, engine, repository) -> dict:
        if not self.can_retract(state, side):
            raise UnsealError("无法安全撤回：对方已提交、阶段已改变或本次封存缺少回滚检查点")
        record = self._load()
        if record is None:
            raise UnsealError("没有找到回滚检查点")
        # Pre-submit snapshot restores realistic-command detachment side effects,
        # while preserving the append-only order submission audit event.
        prior = type(state).model_validate(record["snapshot"])
        events = list(state.events)
        old_values = {name: deepcopy(getattr(state, name)) for name in type(state).model_fields if name != 'events'}
        try:
            for name in type(state).model_fields:
                if name != "events":
                    setattr(state, name, deepcopy(getattr(prior, name)))
            engine._event(state, "orders_retracted", f"{side} 撤回本阶段已封存计划",
                          payload={"secret_side": side, "retracts_sequence": events[-1].sequence})
            repository.save(state)
        except Exception:
            # In-memory state should not diverge if persistence fails.
            for name, value in old_values.items():
                setattr(state, name, value)
            state.events = events
            raise
        self.path.unlink(missing_ok=True)
        return {"draft": record["draft"], "turn": state.turn, "phase": state.phase.value}
