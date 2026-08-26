import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Crypto.Cipher import AES


ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "apps" / "wechat_export_tool"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


locate = load_module("locate_wechat_db", TOOL_DIR / "locate_wechat_db.py")
decrypt = load_module("decrypt_wx_cli_raw", TOOL_DIR / "decrypt_wx_cli_raw.py")


class DecryptTests(unittest.TestCase):
    def test_decrypt_first_page_restores_sqlite_header_and_payload(self):
        raw_key = bytes(range(32))
        iv = bytes(range(16))
        plain_payload = bytes((i % 251 for i in range(4000)))
        encrypted_page = bytearray(decrypt.PAGE_SIZE)
        encrypted_page[: decrypt.SALT_SIZE] = b"salt-for-testing"
        encrypted_page[decrypt.SALT_SIZE : decrypt.PAGE_SIZE - decrypt.RESERVE_SIZE] = AES.new(
            raw_key, AES.MODE_CBC, iv
        ).encrypt(plain_payload)
        encrypted_page[
            decrypt.PAGE_SIZE - decrypt.RESERVE_SIZE :
            decrypt.PAGE_SIZE - decrypt.RESERVE_SIZE + 16
        ] = iv

        result = decrypt.decrypt_page(raw_key, bytes(encrypted_page), 1)

        self.assertEqual(result[:16], decrypt.SQLITE_HEADER)
        self.assertEqual(result[16 : decrypt.PAGE_SIZE - decrypt.RESERVE_SIZE], plain_payload)


class LocateTests(unittest.TestCase):
    def test_candidate_roots_skips_inaccessible_paths(self):
        original_exists = Path.exists

        def guarded_exists(path):
            if "Tencent" in str(path):
                raise PermissionError("denied")
            return original_exists(path)

        with patch.object(Path, "exists", guarded_exists):
            roots = locate.candidate_roots()

        self.assertIsInstance(roots, list)

    def test_find_candidates_accepts_account_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            account_dir = Path(tmp) / "wxid_test_suffix"
            db_storage = account_dir / "db_storage"
            (db_storage / "contact").mkdir(parents=True)
            (db_storage / "message").mkdir(parents=True)
            (db_storage / "contact" / "contact.db").write_bytes(b"contact")
            (db_storage / "message" / "message_0.db").write_bytes(b"message")

            results = locate.find_candidates(str(account_dir), max_depth=1)

            self.assertTrue(any(Path(item["path"]) == db_storage for item in results))


if __name__ == "__main__":
    unittest.main()
