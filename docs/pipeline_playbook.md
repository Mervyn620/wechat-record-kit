# 工作流 Playbook

目标：把普通微信聊天记录从“本机数据/第三方工具/API”变成可阅读的 UTF-8 纯文本，或稳定、可复用、可审计的 JSONL。

## 阶段 0：边界确认

- 数据属于用户本人，或已获得明确授权。
- 只处理指定账号、指定时间范围、指定聊天对象。
- 不上传原始数据库、key、聊天正文到第三方服务。
- 不把任何 DB、key、原始导出文件加入 git。

## 阶段 1：环境与路径定位

运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\wechat_record_kit\scripts\inventory_wechat_paths.ps1 -Out .\wechat_record_kit\runs\inventory.json
```

产物用于回答：

- 数据根目录在哪里。
- 有哪些账号目录。
- 候选 DB 文件是什么、大小和更新时间如何。
- 是否存在媒体目录。

## 阶段 2：选择抽取路径

优先级建议：

1. 微信官方迁移到 PC，然后只处理本机副本。
2. 已有可信工具导出的 JSON/CSV/SQLite。
3. 本地 Chatlog HTTP API。
4. 已解密 SQLite DB。
5. `apps/wechat_export_tool/` 可选本机导出器，或其他第三方 key/decrypt 工具 adapter。

第 5 类会接触数据库 key 和已解密 DB。只在确认数据属于本人或已授权时使用，并在隔离输出目录里跑；默认不要保留中间敏感文件。

可选导出器用法：

```powershell
cd .\wechat_record_kit\apps\wechat_export_tool
.\Export-WeChatRecords.ps1 -TargetChat "联系人备注或群聊名称"
```

如果需要排查解密问题才使用：

```powershell
.\Export-WeChatRecords.ps1 -KeepSensitive
```

## 阶段 3：结构检查

对已解密 SQLite 运行：

```powershell
python -X utf8 .\wechat_record_kit\scripts\inspect_decrypted_sqlite.py --db "D:\path\to\db.sqlite" --counts --out .\wechat_record_kit\runs\db_schema.json
```

这个阶段默认不导出消息正文，只识别表、列、行数和 message/contact/session 候选表。

## 阶段 4：归一化

统一目标格式见 `schemas/normalized_message.schema.json`。核心字段：

- `source_platform`
- `source_adapter`
- `account_id`
- `talker_id`
- `sender_id`
- `is_self`
- `time`
- `message_type`
- `content`
- `raw`

如果使用 Chatlog HTTP：

```powershell
python -X utf8 .\wechat_record_kit\scripts\normalize_chatlog_http.py --talker wxid_xxx --time "2024-01-01~2024-12-31" --out .\wechat_record_kit\runs\chat.normalized.jsonl
```

如果使用其他工具，按 `templates/tool_adapter_spec.md` 写 adapter。

## 阶段 5：输出交付

根据使用场景选择最终产物：

- 人工阅读或提交给其他本地工具：使用 `exports_txt/all_chats.txt` 或 `exports_txt/by_chat/*.txt`。
- 程序化分析、检索或归档：使用符合 `normalized_message.schema.json` 的 JSONL。
- 只需要一个联系人或群聊：使用 `single_chat_exports/` 中的独立文本。

交付目录不得包含数据库 key、已解密数据库或未经确认的全量聊天副本。

## 阶段 6：验证

每次抽取至少验证：

- 消息总数。
- 指定联系人/群的日期范围。
- 空消息、图片、语音、撤回、系统消息等类型处理策略。
- 中文编码。
- 去重规则。
- 输出目录是否只包含用户明确需要的聊天范围。
