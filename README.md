# WeChat Record Kit

普通微信聊天记录定位、授权解密、纯文本导出、结构检查和可选归一化的复用小项目。

这个目录保存流程、只读脚本、schema、适配器模板，以及一个可选的本机微信 4.x 导出工具。导出工具只应该用于你本人账号或已明确授权的数据；它会把 key、已解密 DB 和聊天正文作为本地运行产物处理，并通过 `.gitignore` 排除。

## 快速入口

1. 定位本机可能的微信数据目录，不读取聊天内容：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\wechat_record_kit\scripts\inventory_wechat_paths.ps1 -Out .\wechat_record_kit\runs\inventory.json
   ```

   如果要同时定位企业微信数据目录和安装目录：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\wechat_record_kit\scripts\inventory_wechat_paths.ps1 -IncludeWeCom -Out .\wechat_record_kit\runs\wecom_inventory.json
   ```

2. 检查已经解密好的 SQLite 数据库结构，不导出消息正文：

   ```powershell
   python -X utf8 .\wechat_record_kit\scripts\inspect_decrypted_sqlite.py --db "D:\path\to\MSG0.db" --counts --out .\wechat_record_kit\runs\db_schema.json
   ```

3. 如果后续使用本地 Chatlog HTTP 服务，可以转成统一 JSONL：

   ```powershell
   python -X utf8 .\wechat_record_kit\scripts\normalize_chatlog_http.py --talker wxid_xxx --time "2024-01-01~2024-12-31" --out .\wechat_record_kit\runs\chatlog.normalized.jsonl
   ```

4. 如果需要直接从本机微信 4.x 导出纯文本，可以使用可选导出器：

   ```powershell
   cd .\wechat_record_kit\apps\wechat_export_tool
   .\Export-WeChatRecords.ps1 -TargetChat "联系人备注或群聊名称"
   ```

   运行前需要打开并登录微信，用管理员 PowerShell 执行。默认会清理 `all_keys.json` 和已解密 DB；只有排查问题时才加 `-KeepSensitive`。

## 目录说明

- `docs/source_landscape_2026-05-28.md`: GitHub/PyPI 工具现状快照和可用性判断。
- `docs/data_locations.md`: 普通微信 Windows 数据目录与文件名定位笔记。
- `docs/pipeline_playbook.md`: 从定位、审计、解密到纯文本或 JSONL 交付的工作流。
- `docs/wecom_later.md`: 企业微信后续环境准备和差异提醒。
- `docs/wecom_source_landscape_2026-05-28.md`: 企业微信本地 DB 与官方会话存档工具现状。
- `scripts/inventory_wechat_paths.ps1`: 只读扫描候选路径和数据库文件名。
- `scripts/inspect_decrypted_sqlite.py`: 只读 SQLite schema 检查。
- `scripts/normalize_chatlog_http.py`: 从本地 Chatlog HTTP API 归一化消息。
- `scripts/fetch_wecom_finance_archive.py`: 通过官方会话存档 SDK 拉取并归一化企业微信消息。
- `apps/wechat_export_tool/`: 可选的本机微信 4.x 导出器，定位 `db_storage`、调用第三方 `wx-cli`、解密本地 DB 并导出 UTF-8 文本。
- `schemas/normalized_message.schema.json`: 后续抽取结果统一消息格式。
- `templates/extraction_runbook.md`: 每次实际抽取前填写的运行记录模板。
- `templates/tool_adapter_spec.md`: 第三方工具 adapter 接入规范。

## 项目边界

本 kit 只负责微信聊天记录的定位、授权解密、导出和格式整理。它负责回答：

- 数据在哪里。
- 哪些数据库或 API 结果可读。
- 当前工具链是否还能跑、有什么版本风险。
- 输出如何变成可阅读的 UTF-8 文本或稳定的 JSONL。

本仓库不生成或维护人物卡、Persona、AI 角色资产和聊天机器人。
