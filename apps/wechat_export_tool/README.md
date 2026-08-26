# WeChat Export Tool

Windows 一键导出本机微信 4.x 聊天记录为纯文本。

它会自动完成：

1. 定位微信 `db_storage`
2. 调用 `wx-cli` 从当前运行的 `Weixin.exe` 进程提取数据库 key
3. 解密匹配到的 SQLite 数据库
4. 导出：
   - `exports_txt/all_chats.txt`
   - `exports_txt/by_chat/*.txt`
   - 可选单人聊天：`single_chat_exports/<联系人>/<联系人>_聊天记录.txt`

## 前提

- 用户明确授权处理自己的微信数据。
- 微信已打开并登录。
- 用管理员身份打开 PowerShell。
- 机器有 Python 和 Node/npm。

## 最简单用法

在工具目录运行：

```powershell
.\Export-WeChatRecords.ps1
```

它会自动定位微信数据目录，并把结果放到：

```text
wechat_export_tool\runs\<时间戳>\
```

## 手动指定数据库目录

如果自动定位失败，手动传入 `db_storage`：

```powershell
.\Export-WeChatRecords.ps1 `
  -DbDir "D:\path\to\xwechat_files\wxid_xxx_xxxx\db_storage"
```

## 单独导出某个人

```powershell
.\Export-WeChatRecords.ps1 `
  -TargetChat "联系人备注或群聊名称"
```

也可以同时指定输出目录：

```powershell
.\Export-WeChatRecords.ps1 `
  -DbDir "D:\path\to\xwechat_files\wxid_xxx_xxxx\db_storage" `
  -TargetChat "联系人备注或群聊名称" `
  -OutputRoot "D:\path\to\wechat_export_run"
```

## 我/对方判断

工具会优先从账号目录名推断自己的 wxid。例如：

```text
wxid_xxx_xxxx
```

会推断：

```text
wxid_xxx
```

如果判断不准，手动指定：

```powershell
.\Export-WeChatRecords.ps1 -SelfWxid "wxid_xxxxx"
```

## 输出

成功后会显示：

```text
输出目录：...
总聊天文本：...\exports_txt\all_chats.txt
分会话目录：...\exports_txt\by_chat
单人聊天：...\single_chat_exports\...\聊天记录.txt
运行摘要：...\run_summary.json
```

## 敏感文件

默认会在文本导出成功后清理中间文件：

```text
all_keys.json
decrypted_wx_cli_all/
```

它们很敏感。只有在排查问题时才建议保留：

```powershell
.\Export-WeChatRecords.ps1 -KeepSensitive
```

兼容旧用法：如果同时传入 `-CleanSensitive`，仍会强制清理。

## 常见问题

### 没找到 Weixin.exe

先打开微信并确认已登录：

```powershell
Get-Process Weixin
```

### 提取 key 为 0

处理：

- 用管理员 PowerShell。
- 重启微信后重试。
- 打开一个聊天窗口后重试。
- 手动指定 `-DbDir`。

### 自动定位太慢

默认只查常见位置。只有确实找不到时再用：

```powershell
.\Export-WeChatRecords.ps1 -SearchAllDrives
```

### 中文乱码

脚本内部已设置 UTF-8。如果外部终端显示乱码，文件本身仍通常是 UTF-8。用 VS Code 或支持 UTF-8 的编辑器打开导出的 `.txt`。

## 后续微信版本变化

这个工具依赖 `@jackwener/wx-cli` 对微信 4.x 的内存 key 扫描能力。后续微信版本如果改变 key 缓存形态，可能需要更新 `wx-cli` 或替换扫描模块；导出和解密脚本仍可以复用。
