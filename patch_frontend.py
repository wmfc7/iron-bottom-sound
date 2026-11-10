"""Idempotent source-level patch for upstream frontend/src/App.tsx LAN mode."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / 'frontend' / 'src' / 'App.tsx'
FLAG = 'const LAN_MODE = new URLSearchParams(window.location.search).get("lan") === "1";'


def single(source: str, needle: str, replacement: str, name: str) -> str:
    count = source.count(needle)
    if count != 1:
        raise RuntimeError(f'{name}: 预期 1 处源码锚点，发现 {count} 处，项目可能已更新；没有写入文件。')
    return source.replace(needle, replacement, 1)


def patch(source: str) -> str:
    if FLAG in source:
        return source
    source = single(source, 'const ACTIVE_GAME_KEY = "ibs.active-game.v1";',
                    FLAG + '\nconst ACTIVE_GAME_KEY = "ibs.active-game.v1";', 'LAN_MODE')
    # Add read-only polling, but do not reset the unsent draft on every poll.
    poll = '''useEffect(() => {
    if (!LAN_MODE || !game || reportMode) return;
    let alive = true;
    const timer = window.setInterval(() => {
      viewGame(game, side, false).then((next) => {
        if (!alive) return;
        setView((old) => {
          if (!old || old.phase !== next.phase || old.turn !== next.turn ||
              old.own_orders_submitted !== next.own_orders_submitted ||
              old.both_orders_submitted !== next.both_orders_submitted) return next;
          return old;
        });
      }).catch(() => {});
    }, 1800);
    return () => { alive = false; window.clearInterval(timer); };
  }, [game, side, reportMode]);

  '''
    source = single(source, 'const start = async (', poll + 'const start = async (', '自动刷新')
    start = source.index('const act = async () => {')
    end = source.index('const unlock = async () => {', start)
    section = source[start:end]
    section = single(section, 'setActing(true);\n    try {', '''setActing(true);
    try {
    if (LAN_MODE) {
      // 联机模式：只提交本方命令，服务器自动协调双方封存及阶段推进。
      // 不调用 handoff，不在客户端主动 advance，不切换阵营。
      if (orderPhases.has(view.phase) && !view.own_orders_submitted) {
        await submitOrders(game, side, JSON.parse(draft));
      }
      await refresh(game, side);
      setError("");
      return;
    }''', '联机提交分支')
    source = source[:start] + section + source[end:]
    source = single(source, 'const unlock = async () => {',
                    'const unlock = async () => {\n    if (LAN_MODE) return; // 联机模式不能切换阵营', '阵营锁定')
    source = single(source, 'const toggleDebug = async () => {',
                    'const toggleDebug = async () => {\n    if (LAN_MODE) return; // 联机模式不提供调试视图', '调试限制')
    return source


def main():
    if not TARGET.exists():
        raise SystemExit(f'找不到 {TARGET}，请把补丁文件放到 GitHub 项目根目录。')
    original = TARGET.read_text(encoding='utf-8')
    if FLAG in original:
        print('前端补丁已经安装，无需重复操作。')
        return
    changed = patch(original)
    backup = TARGET.with_name('App.tsx.before-lan-duel.bak')
    if not backup.exists():
        backup.write_text(original, encoding='utf-8')
    TARGET.write_text(changed, encoding='utf-8')
    ignore = ROOT / '.gitignore'
    extra = ['/backend/lan-duel-room.json', '/frontend/src/App.tsx.before-lan-duel.bak']
    existing = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
    missing = [item for item in extra if item not in existing.splitlines()]
    if missing:
        ignore.write_text(existing.rstrip() + '\n' + '\n'.join(missing) + '\n', encoding='utf-8')
    print('前端联机补丁安装完成。备份文件：' + str(backup))


if __name__ == '__main__':
    main()
