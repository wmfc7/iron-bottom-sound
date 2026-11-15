"""Private server-side LAN checkpoints; never serve the full bundle to players.

A checkpoint is a complete save bundle from the authoritative game's existing
save API. Only redacted metadata is returned through the multiplayer gateway.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from uuid import uuid4

MAX_SAVE_BYTES = 128 * 1024 * 1024
MAX_LABEL_CHARS = 60
_ID = re.compile(r'^[0-9a-f]{32}$')


class LobbySaveStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def _path(self, save_id: str, suffix: str) -> Path:
        if not isinstance(save_id, str) or not _ID.fullmatch(save_id):
            raise ValueError('存档编号无效')
        return self.directory / f'{save_id}.{suffix}'

    def create(self, bundle: dict, label: str = '') -> dict:
        if not isinstance(bundle, dict) or bundle.get('format') != 'iron-bottom-sound-save':
            raise ValueError('服务器返回了不支持的存档格式')
        state = bundle.get('state')
        if not isinstance(state, dict) or state.get('options', {}).get('mode') != 'hotseat':
            raise ValueError('仅允许联机双人模式存档')
        if not isinstance(label, str) or len(label.strip()) > MAX_LABEL_CHARS:
            raise ValueError('存档名称不能超过60字')
        content = json.dumps(bundle, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        if len(content) > MAX_SAVE_BYTES:
            raise ValueError('本次存档超过128 MiB，未保存')
        save_id = uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
        meta = {'id': save_id, 'label': label.strip() or f'第 {state.get("turn", "?")} 回合',
                'saved_at': created_at, 'game_id': str(state.get('game_id', '')),
                'scenario_id': str(state.get('scenario_id', ''))[:90],
                'scenario_title': str(state.get('scenario_title', ''))[:150],
                'turn': state.get('turn'), 'phase': state.get('phase')}
        self.directory.mkdir(parents=True, exist_ok=True)
        data_path = self._path(save_id, 'ibs-save.json')
        meta_path = self._path(save_id, 'meta.json')
        try:
            self._write_exclusive(data_path, content)
            self._write_exclusive(meta_path, json.dumps(meta, ensure_ascii=False).encode('utf-8'))
        except Exception:
            data_path.unlink(missing_ok=True)
            meta_path.unlink(missing_ok=True)
            raise
        return meta

    @staticmethod
    def _write_exclusive(path: Path, content: bytes) -> None:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

    def list(self) -> list[dict]:
        if not self.directory.is_dir():
            return []
        rows = []
        for path in self.directory.glob('*.meta.json'):
            save_id = path.name.split('.')[0]
            if not _ID.fullmatch(save_id) or not self._path(save_id, 'ibs-save.json').is_file():
                continue
            try:
                entry = json.loads(path.read_text(encoding='utf-8'))
                if isinstance(entry, dict) and entry.get('id') == save_id:
                    rows.append(entry)
            except (OSError, UnicodeError, ValueError):
                continue
        return sorted(rows, key=lambda row: row['saved_at'], reverse=True)

    def read(self, save_id: str) -> dict:
        path = self._path(save_id, 'ibs-save.json')
        if not path.is_file():
            raise FileNotFoundError('该存档不存在')
        if path.stat().st_size > MAX_SAVE_BYTES:
            raise ValueError('存档过大，已拒绝读取')
        bundle = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(bundle, dict) or bundle.get('format') != 'iron-bottom-sound-save':
            raise ValueError('存档格式无效')
        return bundle
