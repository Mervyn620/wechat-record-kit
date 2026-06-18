#!/usr/bin/env python3
"""Fetch and normalize WeCom official finance archive messages.

This adapter uses the official WeCom/WeChat Work Finance SDK wrapper from
``wechat_record_kit/vendors/PyWeWorkFinance`` or an installed
``pyweworkfinance`` package. It does not read local ``Documents/WXWork`` DBs.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
VENDORED_PYWEWORKFINANCE = REPO_ROOT / "vendors" / "PyWeWorkFinance" / "src"
if VENDORED_PYWEWORKFINANCE.exists():
    sys.path.insert(0, str(VENDORED_PYWEWORKFINANCE))


def load_private_key(path: Path):
    try:
        from Crypto.Cipher import PKCS1_v1_5
        from Crypto.PublicKey import RSA
    except ImportError as exc:  # pragma: no cover - environment dependent.
        raise RuntimeError("pycryptodome is required for RSA decrypt: pip install pycryptodome") from exc

    key = RSA.import_key(path.read_bytes())
    return PKCS1_v1_5.new(key)


def decrypt_random_key(cipher: Any, encrypt_random_key: str) -> str:
    encrypted = base64.b64decode(encrypt_random_key)
    decrypted = cipher.decrypt(encrypted, None)
    if decrypted is None:
        raise RuntimeError("failed to decrypt encrypt_random_key with the provided RSA private key")
    return decrypted.decode("utf-8")


def first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def normalize_archive_message(message: dict[str, Any], keep_raw: bool) -> dict[str, Any]:
    msgtype = first_present(message, "msgtype", "type")
    content = None

    if msgtype and isinstance(message.get(msgtype), dict):
        content = first_present(message[msgtype], "content", "title", "description")
    if content is None:
        content = first_present(message, "content", "text")

    tolist = first_present(message, "tolist", "to_list")
    roomid = first_present(message, "roomid", "room_id")
    sender = first_present(message, "from", "from_user", "sender")

    return {
        "source_platform": "wecom",
        "source_adapter": "wecom-finance-archive",
        "account_id": None,
        "talker_id": roomid or (tolist[0] if isinstance(tolist, list) and tolist else None),
        "talker_name": None,
        "sender_id": sender,
        "sender_name": None,
        "is_self": None,
        "time": first_present(message, "msgtime", "time", "timestamp"),
        "message_id": first_present(message, "msgid", "id"),
        "message_type": msgtype,
        "message_subtype": None,
        "content": content,
        "media": extract_media(message),
        "raw": message if keep_raw else None,
    }


def extract_media(message: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("image", "voice", "video", "file", "emotion"):
        value = message.get(key)
        if isinstance(value, dict):
            return {
                "kind": key,
                "sdk_file_id": first_present(value, "sdkfileid", "sdk_file_id"),
                "md5sum": first_present(value, "md5sum", "md5"),
                "filename": first_present(value, "filename", "file_name"),
                "filesize": first_present(value, "filesize", "file_size"),
            }
    return None


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_json_array(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def env_or_arg(value: str | None, env_name: str) -> str | None:
    return value if value else os.environ.get(env_name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpid", help="WeCom corp id. Env: WECOM_CORP_ID")
    parser.add_argument("--secret", help="Finance archive secret. Env: WECOM_FINANCE_SECRET")
    parser.add_argument("--private-key", type=Path, help="RSA private key path. Env: WECOM_RSA_PRIVATE_KEY")
    parser.add_argument("--dll-path", help="Optional custom official SDK dll/so path.")
    parser.add_argument("--seq", type=int, default=0, help="Start seq.")
    parser.add_argument("--limit", type=int, default=100, help="Batch limit.")
    parser.add_argument("--batches", type=int, default=1, help="Number of batches to fetch.")
    parser.add_argument("--timeout", type=int, default=5)
    parser.add_argument("--proxy", default="")
    parser.add_argument("--passwd", default="")
    parser.add_argument("--out", type=Path, required=True, help="Normalized JSONL output path.")
    parser.add_argument("--raw-out", type=Path, help="Optional decrypted raw JSON output path.")
    parser.add_argument("--keep-raw", action="store_true", help="Keep decrypted raw message in normalized rows.")
    parser.add_argument("--dry-run", action="store_true", help="Validate local imports and configuration only.")
    args = parser.parse_args(argv)

    corpid = env_or_arg(args.corpid, "WECOM_CORP_ID")
    secret = env_or_arg(args.secret, "WECOM_FINANCE_SECRET")
    private_key = args.private_key or (
        Path(os.environ["WECOM_RSA_PRIVATE_KEY"]) if os.environ.get("WECOM_RSA_PRIVATE_KEY") else None
    )

    missing = [
        name
        for name, value in (
            ("corpid/WECOM_CORP_ID", corpid),
            ("secret/WECOM_FINANCE_SECRET", secret),
            ("private-key/WECOM_RSA_PRIVATE_KEY", private_key),
        )
        if not value
    ]
    if missing:
        print("missing required config: " + ", ".join(missing), file=sys.stderr)
        return 2

    if private_key is None or not private_key.exists():
        print(f"private key not found: {private_key}", file=sys.stderr)
        return 2

    try:
        from pyweworkfinance import WeWorkFinance
    except ImportError as exc:
        print(
            "pyweworkfinance is not importable. Clone vendor or run: pip install pyweworkfinance",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc

    if args.dry_run:
        print("config/import dry-run ok")
        return 0

    cipher = load_private_key(private_key)
    sdk = WeWorkFinance(
        corpid=corpid,
        secret=secret,
        dll_path=args.dll_path,
        default_timeout=args.timeout,
    )

    next_seq = args.seq
    normalized_count = 0
    raw_messages: list[dict[str, Any]] = []

    for _ in range(args.batches):
        response = sdk.get_chat_data(
            seq=next_seq,
            limit=args.limit,
            proxy=args.proxy,
            passwd=args.passwd,
            timeout=args.timeout,
        )

        batch_rows: list[dict[str, Any]] = []
        max_seq = next_seq
        for chat in response.chatdata:
            max_seq = max(max_seq, int(chat.seq))
            random_key = decrypt_random_key(cipher, chat.encrypt_random_key)
            message = sdk.decrypt_data(random_key, chat.encrypt_chat_msg)
            raw_messages.append(message)
            batch_rows.append(normalize_archive_message(message, keep_raw=args.keep_raw))

        if batch_rows:
            write_jsonl(args.out, batch_rows)
            normalized_count += len(batch_rows)

        if max_seq <= next_seq:
            break
        next_seq = max_seq

    if args.raw_out:
        write_json_array(args.raw_out, raw_messages)

    print(f"wrote {normalized_count} normalized messages to {args.out}; next_seq={next_seq}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

