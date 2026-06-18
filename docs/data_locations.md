# 普通微信 Windows 数据定位笔记

本页只用于定位自有数据。路径和文件名会随微信版本变化，必须以 `inventory_wechat_paths.ps1` 和实际 schema 检查结果为准。

## 常见根目录

普通微信 PC 版通常会有一个可配置的数据根目录，常见位置包括：

- `%USERPROFILE%\Documents\WeChat Files`
- `%APPDATA%\Tencent\WeChat`
- `%LOCALAPPDATA%\Tencent\WeChat`

历史上也常见这个配置文件指向实际 `WeChat Files` 位置：

- `%APPDATA%\Tencent\WeChat\All Users\config\3ebffe94.ini`

如果用户在微信设置里改过文件管理路径，应优先相信微信设置和该配置文件，再用脚本扫描确认。

## 账号目录

数据根目录下通常按账号分目录，例如：

- `wxid_*`
- 自定义微信号或其他账号标识

一个机器可能有多个账号目录。抽取前需要记录：

- 账号目录路径。
- 最近修改时间。
- 数据库候选数量。
- 媒体目录大小和最近修改时间。

## 老版本/3.x 常见文件线索

以下名称常作为定位线索，不代表每台机器一定存在：

- `Msg\MSG*.db`
- `Msg\MicroMsg.db`
- `Msg\MediaMSG*.db`
- `Msg\PublicMsg.db`
- `Msg\Favorite.db`
- `Msg\OpenIMContact.db`
- `FileStorage\File`
- `FileStorage\Image`
- `FileStorage\Video`
- `FileStorage\Voice`

## 新版本/4.x 常见变化

公开工具文档和源码索引显示，新版普通微信可能使用更多分组数据库和按时间分片的 message 数据库，例如 `message_*.db` 一类文件。不要硬编码旧版路径；先扫描文件名，再用 SQLite schema 判断表结构。

## 采集原则

- 先复制原始目录到工作区外的只读备份，再处理副本。
- 不在 repo 中保存数据库、解密 key、原始聊天 JSONL 或媒体文件。
- 每次抽取都写一份 `templates/extraction_runbook.md` 的运行记录。
- 对中文路径统一用 `python -X utf8`，避免 PowerShell 显示乱码误判为文件损坏。

