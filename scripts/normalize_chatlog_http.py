#!/usr/bin/env python3
"""Normalize messages from a local Chatlog HTTP API into JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


def fetch_json(base_url: str, talker: str | None, time_range: str | None, limit: int | None) -> Any:
    params: dict[str, Any] = {"format": "json"}
    if talker:
        params["talker"] = talker
    if time_range:
        params["time"] = time_range
    if limit is not None:
        params["limit"] = limit

    endpoint = urljoin(base_url.rstrip("/") + "/", "api/v1/chatlog")
    url = endpoint + "?" + urlencode(params)
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "wechat-record-kit"})
    with urlopen(req, timeout=30) as resp:  # noqa: S310 - local user-supplied API endpoint.
        body = resp.read().decode("utf-8", errors="replace")

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Chatlog response is not JSON: {exc}") from exc


def extract_messages(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [m for m in payload if isinstance(m, dict)]
    if isinstance(payload, dict):
        for key in ("messages", "data", "items", "rows", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return [m for m in value if isinstance(m, dict)]
            if isinstance(value, dict):
                nested = extract_messages(value)
                if nested:
                    return nested
    return []


def first_present(message: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in message and message[key] is not None:
            return message[key]
    return None


def normalize_message(message: dict[str, Any], account_id: str | None, keep_raw: bool) -> dict[str, Any]:
    content = first_present(message, "content", "text", "StrContent", "msg", "message")
    normalized = {
        "source_platform": "wechat",
        "source_adapter": "chatlog-http",
        "account_id": account_id,
        "talker_id": first_present(message, "talker", "talker_id", "Talker", "roomId"),
        "talker_name": first_present(message, "talkerName", "talker_name", "roomName"),
        "sender_id": first_present(message, "sender", "sender_id", "Sender", "fromUser"),
        "sender_name": first_present(message, "senderName", "sender_name", "fromName"),
        "is_self": first_present(message, "isSelf", "is_self"),
        "time": first_present(message, "time", "createTime", "CreateTime", "timestamp"),
        "message_id": first_present(message, "seq", "id", "localId", "MsgSvrID"),
        "message_type": first_present(message, "type", "msgType", "Type"),
        "message_subtype": first_present(message, "subType", "sub_type"),
        "content": content,
        "media": first_present(message, "media", "contents"),
        "raw": message if keep_raw else None,
    }
    return normalized


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5030", help="Local Chatlog base URL.")
    parser.add_argument("--talker", help="Talker wxid/group/nickname accepted by Chatlog.")
    parser.add_argument("--time", dest="time_range", help="Date or range, e.g. 2024-01-01~2024-12-31.")
    parser.add_argument("--limit", type=int, help="Optional API limit.")
    parser.add_argument("--account-id", help="Optional account id to stamp on output rows.")
    parser.add_argument("--out", type=Path, required=True, help="Output JSONL path.")
    parser.add_argument("--keep-raw", action="store_true", help="Keep raw API message in each row.")
    args = parser.parse_args(argv)

    try:
        payload = fetch_json(args.base_url, args.talker, args.time_range, args.limit)
        messages = extract_messages(payload)
        normalized = [
            normalize_message(message, account_id=args.account_id, keep_raw=args.keep_raw)
            for message in messages
        ]
        write_jsonl(args.out, normalized)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"wrote {len(normalized)} messages to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

