#!/usr/bin/env python3
"""Conservative, reversible root declutter for iron-bottom-sound online-test.

Default is review-only; --apply uses git mv on an explicit allowlist of
historical files/directories. Never touches current runtime, saves, secrets,
original game resources, the CPU RNG DLL, or repository history.

Usage:
  python IBS_organize_online_test.py --root .
  python IBS_organize_online_test.py --root . --apply
  python IBS_organize_online_test.py --root . --undo path/to/manifest.json
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

# Exact paths from the user's November 11, 2026 audit.
# The v6 directory and installer-referenced backup are deliberately excluded.
MOVES = {
    "IBS_Dice_Privacy_UI_v6_3": "maintenance/archive/patches/IBS_Dice_Privacy_UI_v6_3",
    "IBS_Dice_Sync_v3": "maintenance/archive/patches/IBS_Dice_Sync_v3",
    "IBS_Dice_Sync_v4": "maintenance/archive/patches/IBS_Dice_Sync_v4",
    "IBS_Dice_Unblock_v5": "maintenance/archive/patches/IBS_Dice_Unblock_v5",
    "IBS_LAN_Unsubmit_v1": "maintenance/archive/patches/IBS_LAN_Unsubmit_v1",
    "ibs-dice-privacy-ui-v6_3-backup-20261111-183702": "maintenance/archive/backups/ibs-dice-privacy-ui-v6_3-backup-20261111-183702",
    "ibs-dice-v6-backup-20261111-182235": "maintenance/archive/backups/ibs-dice-v6-backup-20261111-182235",
    "ibs-unsubmit-v1-backup-20261111-191101": "maintenance/archive/backups/ibs-unsubmit-v1-backup-20261111-191101",
    "lan_dice.py.before-sync-v3-20261111-163542-408.bak": "maintenance/archive/backups/lan_dice.py.before-sync-v3-20261111-163542-408.bak",
    "lan_dice.py.pre-unblock-v5-20261111-173249.bak": "maintenance/archive/backups/lan_dice.py.pre-unblock-v5-20261111-173249.bak",
    "lan_dice_client.js.before-collapse-20261111-132545.bak": "maintenance/archive/backups/lan_dice_client.js.before-collapse-20261111-132545.bak",
    "lan_dice_client.js.before-sync-v3-20261111-163542-408.bak": "maintenance/archive/backups/lan_dice_client.js.before-sync-v3-20261111-163542-408.bak",
    "lan_server.py.before-dice-v2-20261111-120819.bak": "maintenance/archive/backups/lan_server.py.before-dice-v2-20261111-120819.bak",
    "ibs-dice-diagnostic-20261111-170603": "maintenance/archive/diagnostics/ibs-dice-diagnostic-20261111-170603",
}


def git(root, *args, check=True):
    proc = subprocess.run(["git", *args], cwd=root, encoding="utf-8", errors="replace", capture_output=True)
    if check and proc.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc


def verify_repo(root):
    if not (root / ".git").exists():
        raise RuntimeError("No .git directory at --root; use a local Git checkout")
    repo = Path(git(root, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    if repo != root.resolve():
        raise RuntimeError(f"--root must be the repository top level: {repo}")
    for critical in ["lan_server.py", "lan_dice.py", "lan_dice_client.js", "lan_unseal.py", "frontend/src/App.tsx"]:
        if not (root / critical).is_file():
            raise RuntimeError(f"Not the expected project root: {critical} not found")


def assert_clean_tracked(root):
    # Untracked scans and game data may exist; protect all tracked edits.
    if git(root, "diff", "--quiet", check=False).returncode != 0:
        raise RuntimeError("Uncommitted edits found: git diff. Commit or stash them before --apply")
    if git(root, "diff", "--cached", "--quiet", check=False).returncode != 0:
        raise RuntimeError("Staged edits found: git diff --cached. Commit or unstage before --apply")


def review(root):
    print("Review only — nothing will be changed.\n")
    count = 0
    for source, destination in MOVES.items():
        path = root / source
        if not path.exists():
            status = "SKIP: not found"
        elif (root / destination).exists():
            status = "BLOCK: destination exists"
        else:
            tracked = git(root, "ls-files", "--", source).stdout.splitlines()
            untracked = git(root, "ls-files", "--others", "--exclude-standard", "--", source).stdout.splitlines()
            if not tracked:
                status = "BLOCK: not Git-tracked"
            elif untracked:
                status = f"BLOCK: contains {len(untracked)} untracked files"
            else:
                status = "READY: Git-tracked"
                count += 1
        print(f"{status:38} {source} -> {destination}")
    print(f"\n{count} eligible path(s). No database, source runtime, rules, or assets are moved.")
    print("For actual archiving: --apply. Confirm tests before committing the renames.")


def apply(root):
    assert_clean_tracked(root)
    ready = []
    for source, destination in MOVES.items():
        if not (root / source).exists():
            continue
        if (root / destination).exists():
            raise RuntimeError(f"Destination already exists: {destination}")
        tracked = git(root, "ls-files", "--", source).stdout.splitlines()
        if not tracked:
            raise RuntimeError(f"Not Git-tracked (refuse to touch): {source}")
        untracked = git(root, "ls-files", "--others", "--exclude-standard", "--", source).stdout.splitlines()
        if untracked:
            raise RuntimeError(f"Untracked files inside candidate (refuse to move): {source}")
        ready.append((source, destination))
    if not ready:
        print("No eligible paths found. No changes made.")
        return
    performed = []
    try:
        for source, destination in ready:
            (root / destination).parent.mkdir(parents=True, exist_ok=True)
            git(root, "mv", "--", source, destination)
            performed.append({"from": source, "to": destination})
            print(f"Moved: {source} -> {destination}")
    except Exception:
        for row in reversed(performed):
            git(root, "mv", "--", row["to"], row["from"], check=False)
        raise
    history = root.parent / f"{root.name}-cleanup-history"
    history.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    outfile = history / f"move-manifest-{stamp}.json"
    outfile.write_text(json.dumps({"root": str(root), "moves": performed}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nMove manifest (outside repo): {outfile}")
    print("Now run tests and inspect `git diff --cached --stat`. Revert with --undo before committing if needed.")


def undo(root, path):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if Path(manifest["root"]).resolve() != root.resolve():
        raise RuntimeError("Manifest belongs to a different repository")
    for row in reversed(manifest["moves"]):
        src = row["from"]
        dst = row["to"]
        if (root / dst).exists() and not (root / src).exists():
            (root / src).parent.mkdir(parents=True, exist_ok=True)
            git(root, "mv", "--", dst, src)
            print(f"Restored: {src}")
        else:
            print(f"Skipped (already changed): {src}")
    print("Review `git status` afterwards.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true", help="Move approved tracked historical files using git mv")
    group.add_argument("--undo", type=Path, help="Restore moves from generated manifest")
    args = parser.parse_args()
    root = args.root.resolve()
    verify_repo(root)
    if args.undo:
        undo(root, args.undo.resolve())
    elif args.apply:
        apply(root)
    else:
        review(root)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
