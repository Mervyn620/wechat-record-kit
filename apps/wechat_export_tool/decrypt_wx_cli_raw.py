import argparse
import json
import os
from pathlib import Path

from Crypto.Cipher import AES


PAGE_SIZE = 4096
SALT_SIZE = 16
RESERVE_SIZE = 80
SQLITE_HEADER = b"SQLite format 3\x00"


def decrypt_page(raw_key: bytes, page: bytes, page_no: int) -> bytes:
    if len(page) < PAGE_SIZE:
        page = page + b"\x00" * (PAGE_SIZE - len(page))
    iv_offset = PAGE_SIZE - RESERVE_SIZE
    iv = page[iv_offset:iv_offset + 16]
    cipher = AES.new(raw_key, AES.MODE_CBC, iv)
    out = bytearray(PAGE_SIZE)
    if page_no == 1:
        dec = cipher.decrypt(page[SALT_SIZE:iv_offset])
        out[:16] = SQLITE_HEADER
        out[16:iv_offset] = dec
    else:
        dec = cipher.decrypt(page[:iv_offset])
        out[:iv_offset] = dec
    return bytes(out)


def decrypt_db(src: Path, dst: Path, raw_key_hex: str) -> None:
    raw_key = bytes.fromhex(raw_key_hex)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as f_in, dst.open("wb") as f_out:
        page_no = 1
        while True:
            page = f_in.read(PAGE_SIZE)
            if not page:
                break
            f_out.write(decrypt_page(raw_key, page, page_no))
            page_no += 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--keys", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    db_dir = Path(cfg["db_dir"])
    keys = json.loads(Path(args.keys).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)

    count = 0
    missing = []
    for rel, info in keys.items():
        if rel.startswith("_"):
            continue
        raw_key_hex = info["enc_key"] if isinstance(info, dict) else info
        rel_norm = rel.replace("/", os.sep).replace("\\", os.sep)
        src = db_dir / rel_norm
        dst = out_dir / rel_norm
        if not src.exists():
            missing.append(rel)
            continue
        decrypt_db(src, dst, raw_key_hex)
        count += 1

    print(json.dumps({
        "decrypted": count,
        "missing": missing,
        "out_dir": str(out_dir),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
