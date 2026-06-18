import argparse
import hashlib
import json
import re
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import zstandard as zstd


TYPE_LABELS = {
    1: "文本",
    3: "图片",
    34: "语音",
    42: "名片",
    43: "视频",
    47: "表情",
    48: "位置",
    49: "链接/文件",
    50: "通话",
    10000: "系统",
    10002: "撤回",
}


def base_type(local_type: int) -> int:
    return local_type & 0xFFFFFFFF


def safe_name(name: str, fallback: str) -> str:
    name = (name or fallback).strip() or fallback
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = "".join("_" if ord(ch) < 32 else ch for ch in name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:80] or fallback


def maybe_decompress(value, ct: int) -> str:
    if value is None:
        return ""
    data = value if isinstance(value, bytes) else str(value).encode("utf-8", errors="replace")
    if ct == 4 and data:
        try:
            return zstd.ZstdDecompressor().decompress(data).decode("utf-8", errors="replace")
        except Exception:
            pass
    return data.decode("utf-8", errors="replace")


def extract_tag(xml: str, tag: str) -> str:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", xml or "", flags=re.S)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def format_content(local_id: int, local_type: int, content: str, is_group: bool) -> str:
    t = base_type(local_type)
    if is_group and ":\n" in content:
        content = content.split(":\n", 1)[1]
    if t == 1:
        return content
    if t == 3:
        return f"[图片] local_id={local_id}"
    if t == 34:
        return "[语音]"
    if t == 42:
        return "[名片]"
    if t == 43:
        return "[视频]"
    if t == 47:
        return "[表情]"
    if t == 48:
        return "[位置]"
    if t == 50:
        return "[通话]"
    if t == 10000:
        return content if content else "[系统消息]"
    if t == 10002:
        return content if content else "[撤回了一条消息]"
    if t == 49:
        title = extract_tag(content, "title")
        app_type = extract_tag(content, "type")
        if app_type == "6":
            return f"[文件] {title}".strip()
        if app_type in {"33", "36", "44"}:
            return f"[小程序] {title}".strip()
        if app_type == "57":
            ref = extract_tag(content, "content")
            return f"[引用] {title}".strip() + (f"\n  ↳ {ref}" if ref else "")
        return f"[链接/文件] {title}".strip() if title else "[链接/文件]"
    return content if content else f"[{TYPE_LABELS.get(t, f'type={t}')}]"


def load_contacts(db_root: Path):
    contacts = {}
    verify_flags = {}
    contact_db = db_root / "contact" / "contact.db"
    if contact_db.exists():
        con = sqlite3.connect(contact_db)
        con.row_factory = sqlite3.Row
        for row in con.execute("SELECT username, nick_name, remark, verify_flag FROM contact"):
            username = row["username"]
            display = row["remark"] or row["nick_name"] or username
            contacts[username] = display
            verify_flags[username] = row["verify_flag"] or 0
        con.close()
    session_db = db_root / "session" / "session.db"
    if session_db.exists():
        con = sqlite3.connect(session_db)
        con.row_factory = sqlite3.Row
        for row in con.execute("SELECT username FROM SessionTable"):
            contacts.setdefault(row["username"], row["username"])
        con.close()
    return contacts, verify_flags


def load_id2u(con: sqlite3.Connection):
    try:
        return {row[0]: row[1] for row in con.execute("SELECT rowid, user_name FROM Name2Id")}
    except sqlite3.Error:
        return {}


def sender_info(real_sender_id, content, is_group, chat_username, id2u, contacts, self_wxid):
    sender_uname = id2u.get(real_sender_id, "")
    if is_group:
        if sender_uname == self_wxid:
            return True, ""
        if sender_uname and sender_uname != chat_username:
            return False, contacts.get(sender_uname, sender_uname)
        if ":\n" in content:
            raw = content.split(":\n", 1)[0]
            if raw == self_wxid:
                return True, ""
            return False, contacts.get(raw, raw)
        return False, ""
    if sender_uname == self_wxid:
        return True, ""
    if sender_uname and sender_uname != chat_username:
        return True, ""
    return False, contacts.get(chat_username, chat_username)


def chat_type(username, verify_flags):
    if "@chatroom" in username:
        return "group"
    if username in {"brandsessionholder", "@placeholder_foldgroup"}:
        return "folded"
    if verify_flags.get(username, 0) != 0 or username.startswith(("gh_", "biz_", "@")):
        return "official_account"
    return "private"


def collect_possible_usernames(db_root: Path, contacts):
    usernames = set(contacts)
    db_paths = [db_root / "session" / "session.db"]
    msg_dir = db_root / "message"
    if msg_dir.exists():
        db_paths.extend(msg_dir.glob("*.db"))
    for db_path in db_paths:
        if not db_path.exists():
            continue
        try:
            con = sqlite3.connect(db_path)
            for table, col in [("Name2Id", "user_name"), ("SessionTable", "username")]:
                try:
                    for (u,) in con.execute(f"SELECT {col} FROM {table}"):
                        if u:
                            usernames.add(u)
                except sqlite3.Error:
                    pass
            con.close()
        except sqlite3.Error:
            pass
    return usernames


def infer_self_wxid(db_root: Path):
    account_dir = db_root.parent.name
    match = re.match(r"^(wxid_.+)_([0-9a-zA-Z]+)$", account_dir)
    return match.group(1) if match else ""


def write_single_chat(target_chat: str, out_root: Path, summary):
    if not target_chat:
        return None
    target_norm = target_chat.lower()
    exact = [
        row for row in summary
        if row["display"].lower() == target_norm or row["username"].lower() == target_norm
    ]
    partial = [
        row for row in summary
        if target_norm in row["display"].lower() or target_norm in row["username"].lower()
    ]
    matches = exact or partial
    if not matches:
        return {"target": target_chat, "matched": False}
    row = sorted(matches, key=lambda x: x["messages"], reverse=True)[0]
    src = out_root / row["file"]
    dest_dir = out_root.parent / "single_chat_exports" / safe_name(row["display"], row["username"])
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{safe_name(row['display'], row['username'])}_聊天记录.txt"
    shutil.copy2(src, dest)
    return {
        "target": target_chat,
        "matched": True,
        "display": row["display"],
        "username": row["username"],
        "messages": row["messages"],
        "file": str(dest),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-root", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--self-wxid", default="")
    parser.add_argument("--target-chat", default="")
    args = parser.parse_args()

    db_root = Path(args.db_root)
    out_root = Path(args.out_root)
    by_chat = out_root / "by_chat"
    self_wxid = args.self_wxid or infer_self_wxid(db_root)
    if not self_wxid:
        raise SystemExit("Cannot infer self wxid. Pass --self-wxid.")

    out_root.mkdir(parents=True, exist_ok=True)
    by_chat.mkdir(parents=True, exist_ok=True)

    contacts, verify_flags = load_contacts(db_root)
    md5_to_username = {
        hashlib.md5(u.encode("utf-8")).hexdigest(): u
        for u in collect_possible_usernames(db_root, contacts)
    }

    chats = defaultdict(list)
    message_dir = db_root / "message"
    db_paths = []
    if message_dir.exists():
        db_paths.extend(sorted(message_dir.glob("message_*.db")))
        biz = message_dir / "biz_message_0.db"
        if biz.exists():
            db_paths.append(biz)

    for db_path in db_paths:
        if db_path.name.endswith("_fts.db") or db_path.name.endswith("_resource.db"):
            continue
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        id2u = load_id2u(con)
        tables = [
            row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'"
            )
        ]
        for table in tables:
            table_hash = table[4:]
            chat_username = md5_to_username.get(table_hash, table)
            display = contacts.get(chat_username, chat_username)
            ctype = chat_type(chat_username, verify_flags)
            is_group = ctype == "group"
            sql = (
                f'SELECT local_id, local_type, create_time, real_sender_id, '
                f'message_content, WCDB_CT_message_content FROM "{table}" ORDER BY create_time ASC'
            )
            try:
                rows = con.execute(sql)
            except sqlite3.Error:
                continue
            for row in rows:
                raw_content = maybe_decompress(row["message_content"], row["WCDB_CT_message_content"] or 0)
                is_self, sender = sender_info(
                    row["real_sender_id"], raw_content, is_group, chat_username, id2u, contacts, self_wxid
                )
                who = "我" if is_self else (f"对方({sender})" if sender else "对方")
                t = base_type(row["local_type"])
                ts = row["create_time"]
                content = format_content(row["local_id"], row["local_type"], raw_content, is_group)
                chats[(chat_username, display, ctype)].append({
                    "timestamp": ts,
                    "time": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
                    "who": who,
                    "type": TYPE_LABELS.get(t, f"type={t}"),
                    "content": content,
                    "local_id": row["local_id"],
                })
        con.close()

    all_blocks = []
    summary = []
    used_names = set()
    for idx, ((username, display, ctype), messages) in enumerate(
        sorted(chats.items(), key=lambda item: (item[0][1].lower(), item[0][0]))
    ):
        messages.sort(key=lambda m: (m["timestamp"], m["local_id"]))
        title = f"{display} ({username})"
        header = f"=== {title} | {ctype} | {len(messages)} 条 ==="
        lines = [header, ""]
        for m in messages:
            content = m["content"].replace("\r\n", "\n").replace("\r", "\n")
            content = content.replace("\n", "\n    ")
            lines.append(f'[{m["time"]}] {m["who"]} [{m["type"]}]: {content}')
        text = "\n".join(lines).rstrip() + "\n"
        base = safe_name(display, username)
        filename = f"{idx + 1:04d}_{base}.txt"
        while filename.lower() in used_names:
            filename = f"{idx + 1:04d}_{base}_{username[-6:]}.txt"
        used_names.add(filename.lower())
        (by_chat / filename).write_text(text, encoding="utf-8")
        all_blocks.append(text)
        summary.append({
            "display": display,
            "username": username,
            "chat_type": ctype,
            "messages": len(messages),
            "file": str((by_chat / filename).relative_to(out_root)),
            "first_time": messages[0]["time"] if messages else "",
            "last_time": messages[-1]["time"] if messages else "",
        })

    (out_root / "all_chats.txt").write_text("\n\n".join(all_blocks), encoding="utf-8")
    (out_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    single = write_single_chat(args.target_chat, out_root, summary)
    result = {
        "self_wxid": self_wxid,
        "chats": len(summary),
        "messages": sum(s["messages"] for s in summary),
        "out_root": str(out_root),
        "single_chat": single,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
