import argparse
import json
import os
import string
from pathlib import Path


def fixed_drives():
    if os.name != "nt":
        return []
    drives = []
    for letter in string.ascii_uppercase:
        root = Path(f"{letter}:\\")
        if root.exists():
            drives.append(root)
    return drives


def candidate_roots(search_all_drives=False):
    roots = []
    env = os.environ
    for key in ("WECHAT_DB_DIR", "WECHAT_HOME"):
        value = env.get(key)
        if value:
            roots.append(Path(value))
    for key in ("APPDATA", "LOCALAPPDATA", "USERPROFILE"):
        value = env.get(key)
        if value:
            base = Path(value)
            roots.extend([
                base,
                base / "Tencent",
                base / "Tencent" / "xwechat",
                base / "Documents",
                base / "Documents" / "WeChat Files",
                base / "Documents" / "xwechat_files",
            ])
    for drive in fixed_drives():
        roots.extend([
            drive / "HuaweiMoveData" / "Users" / os.environ.get("USERNAME", ""),
            drive / "HuaweiMoveData" / "Users",
            drive / "xwechat_files",
        ])
        if search_all_drives:
            roots.append(drive)
    seen = set()
    out = []
    for root in roots:
        try:
            resolved = root.resolve()
        except Exception:
            resolved = root
        key = str(resolved).lower()
        if key not in seen and root.exists():
            seen.add(key)
            out.append(root)
    return out


def score_db_storage(path: Path):
    checks = {
        "contact": path / "contact" / "contact.db",
        "session": path / "session" / "session.db",
        "message0": path / "message" / "message_0.db",
        "message1": path / "message" / "message_1.db",
        "biz": path / "message" / "biz_message_0.db",
    }
    score = sum(1 for p in checks.values() if p.exists())
    if score < 2:
        return None
    db_count = 0
    total_size = 0
    newest = 0.0
    try:
        for db in path.rglob("*.db"):
            db_count += 1
            try:
                st = db.stat()
            except OSError:
                continue
            total_size += st.st_size
            newest = max(newest, st.st_mtime)
    except OSError:
        pass
    return {
        "path": str(path),
        "score": score,
        "db_count": db_count,
        "total_size": total_size,
        "newest_mtime": newest,
        "account_dir": path.parent.name,
    }


def walk_for_db_storage(root: Path, max_depth: int):
    root = root.resolve()
    stack = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        if current.name.lower() == "db_storage":
            yield current
            continue
        if depth >= max_depth:
            continue
        try:
            children = list(current.iterdir())
        except (OSError, PermissionError):
            continue
        for child in children:
            if not child.is_dir():
                continue
            name = child.name.lower()
            if name in {
                "$recycle.bin", "windows", "program files", "program files (x86)",
                "programdata", "node_modules", ".git", ".venv", "appdata"
            } and depth == 0:
                continue
            stack.append((child, depth + 1))


def find_candidates(db_dir=None, search_all_drives=False, max_depth=6):
    candidates = []
    if db_dir:
        path = Path(db_dir)
        if path.name.lower() != "db_storage":
            path = path / "db_storage"
        info = score_db_storage(path)
        if info:
            candidates.append(info)
    for root in candidate_roots(search_all_drives=search_all_drives):
        for db_storage in walk_for_db_storage(root, max_depth=max_depth):
            info = score_db_storage(db_storage)
            if info:
                candidates.append(info)
    deduped = {}
    for item in candidates:
        deduped[item["path"].lower()] = item
    candidates = list(deduped.values())
    candidates.sort(key=lambda x: (x["score"], x["db_count"], x["total_size"], x["newest_mtime"]), reverse=True)
    return candidates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-dir", default="")
    parser.add_argument("--search-all-drives", action="store_true")
    parser.add_argument("--max-depth", type=int, default=6)
    args = parser.parse_args()
    candidates = find_candidates(args.db_dir, args.search_all_drives, args.max_depth)
    print(json.dumps({"candidates": candidates}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
