# Security and Privacy

This project is intended for authorized, local-first WeChat record inventory, export, and normalization workflows.

Do not commit or upload:

- WeChat databases, decrypted databases, WAL/SHM sidecar files, or media files.
- Decryption keys, API keys, RSA private keys, tokens, cookies, or memory dumps.
- Raw chat exports, normalized JSONL containing message text, contact lists, account IDs, phone numbers, or email addresses.
- Inventory outputs that contain real usernames, machine names, organization names, or local paths.

The optional `apps/wechat_export_tool/` workflow can invoke a third-party local `wx-cli` package to recover database keys from the user's own running WeChat process, decrypt local database copies, and export text. Use it only on data you own or have explicit permission to process. It is not intended for reading another person's chat data.

The export workflow is configured so generated keys and decrypted databases are local run artifacts, ignored by git, and cleaned by default unless the user explicitly opts to keep them for debugging.

Before publishing changes, run a secret scan over the staged files and verify `runs/`, `work/`, `exports/`, `exports_txt/`, `single_chat_exports/`, `decrypted*/`, `tools/`, `secrets/`, and `vendors/` remain ignored.
