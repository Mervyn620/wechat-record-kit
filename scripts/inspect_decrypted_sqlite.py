#!/usr/bin/env python3
"""Inspect an already-decrypted SQLite database without exporting message text."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote


MESSAGE_HINTS = {
    "msgsvrid",
    "msgserverid",
    "localid",
    "talker",
    "talkerid",
    "sender",
    "strcontent",
    "content",
    "createtime",
    "timestamp",
}
CONTACT_HINTS = {"username", "nickname", "remark", "alias", "contact"}
SESSION_HINTS = {"session", "conversation", "lastmsg", "lasttime", "unread"}


def sqlite_uri(path: Path) -> str:
    normalized = path.resolve().as_posix()
    return "file:" + quote(normalized, safe="/:") + "?mode=ro"


def open_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(sqlite_uri(path), uri=True)


def table_columns(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    rows = conn.execute(f"PRAGMA table_info({quote_identifier(table)})").fetchall()
    return [
        {
            "cid": row[0],
            "name": row[1],
            "type": row[2],
            "notnull": bool(row[3]),
            "default": row[4],
            "pk": bool(row[5]),
        }
        for row in rows
    ]


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def classify_table(name: str, columns: list[dict[str, Any]]) -> list[str]:
    lowered = {c["name"].lower() for c in columns}
    labels: list[str] = []
    if lowered & MESSAGE_HINTS or name.lower().startswith(("msg", "message")):
        labels.append("message_like")
    if lowered & CONTACT_HINTS or "contact" in name.lower():
        labels.append("contact_like")
    if lowered & SESSION_HINTS or "session" in name.lower():
        labels.append("session_like")
    return labels


def inspect_db(path: Path, include_counts: bool) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    if not path.is_file():
        raise ValueError(f"not a file: {path}")

    conn = open_readonly(path)
    try:
        schema_rows = conn.execute(
            """
            SELECT type, name, sql
            FROM sqlite_master
            WHERE type IN ('table', 'view')
            ORDER BY type, name
            """
        ).fetchall()

        objects: list[dict[str, Any]] = []
        for object_type, name, sql in schema_rows:
            columns = table_columns(conn, name) if object_type == "table" else []
            item: dict[str, Any] = {
                "type": object_type,
                "name": name,
                "labels": classify_table(name, columns),
                "columns": columns,
                "sql_present": bool(sql),
            }
            if include_counts and object_type == "table":
                try:
                    item["row_count"] = conn.execute(
                        f"SELECT COUNT(*) FROM {quote_identifier(name)}"
                    ).fetchone()[0]
                except sqlite3.Error as exc:
                    item["row_count_error"] = str(exc)
            objects.append(item)

        return {
            "path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "sqlite_ok": True,
            "objects": objects,
            "summary": {
                "tables": sum(1 for o in objects if o["type"] == "table"),
                "views": sum(1 for o in objects if o["type"] == "view"),
                "message_like_tables": [
                    o["name"] for o in objects if "message_like" in o["labels"]
                ],
                "contact_like_tables": [
                    o["name"] for o in objects if "contact_like" in o["labels"]
                ],
                "session_like_tables": [
                    o["name"] for o in objects if "session_like" in o["labels"]
                ],
            },
        }
    finally:
        conn.close()


def run_self_test() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "sample.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "CREATE TABLE MSG(localId INTEGER PRIMARY KEY, StrContent TEXT, CreateTime INTEGER)"
            )
            conn.execute("CREATE TABLE Contact(UserName TEXT, NickName TEXT)")
            conn.execute("INSERT INTO MSG(StrContent, CreateTime) VALUES ('hello', 1)")
            conn.commit()
        finally:
            conn.close()

        result = inspect_db(db_path, include_counts=True)
        assert result["summary"]["tables"] == 2
        assert "MSG" in result["summary"]["message_like_tables"]
        assert "Contact" in result["summary"]["contact_like_tables"]
    print("self-test ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, help="Path to an already-decrypted SQLite DB.")
    parser.add_argument("--out", type=Path, help="Write JSON report to this path.")
    parser.add_argument("--counts", action="store_true", help="Include table row counts.")
    parser.add_argument("--self-test", action="store_true", help="Run built-in smoke test.")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()
    if args.db is None:
        parser.error("--db is required unless --self-test is used")

    try:
        result = inspect_db(args.db, include_counts=args.counts)
    except Exception as exc:  # noqa: BLE001 - CLI should return structured error.
        result = {
            "path": str(args.db),
            "sqlite_ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)

    return 0 if result.get("sqlite_ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())

