# 企业微信抽取工具现状快照

快照日期：2026-05-28。

## 结论

这次没有找到成熟的“本机企业微信 `Documents\WXWork\...\*.db` 定位 + 解密 + 聊天正文导出”开源项目。GitHub 上相对成熟、仍可见的项目主要是企业微信官方“会话内容存档 / Finance SDK”的封装。

这两条路线要分开：

- 本地 DB 路线：处理 `Documents\WXWork` 下的 `message_lookup.db`、`session.db`、`message_index*.db` 等文件。当前只能做定位、schema 检查和后续自研 adapter。
- 官方会话存档路线：通过企业微信后台开通的会话内容存档能力拉取消息，需要 `corpid`、会话存档 `secret`、RSA 私钥和官方 SDK 动态库。它不读取本机 DB。

## 当前下载的 vendor

已下载：

- `wechat_record_kit/vendors/PyWeWorkFinance`
- 上游：`https://github.com/911061873/PyWeWorkFinance`
- 当前本地 commit：`b1e335071686478d805d33eb7ca1e8cacb431525`
- 说明：Python 封装的企业微信会话存档 SDK，支持 Windows/Linux，仓库内包含官方 SDK 动态库。

这个 vendor 被 `.gitignore` 忽略，避免把第三方二进制库直接提交进后续仓库。

## 候选项目判断

| 项目 | 类型 | 当前判断 | 适合度 |
| --- | --- | --- | --- |
| `911061873/PyWeWorkFinance` | Python 官方会话存档 SDK 封装 | 代码小，支持 Windows，已下载到本地 vendor | 适合做 Python adapter |
| `vesio/WeComFinanceSdk_python` | Python 官方会话存档 SDK 封装 | 也支持 Windows/Linux，但更像单文件封装，无 release | 备选 |
| `Hanson/WeworkMsg` | Go 服务端 + CLI | 有 HTTP/CLI，适合服务化拉取会话存档；Linux 服务端为主，Windows CLI | 如果要长期跑服务可考虑 |
| `pangdahua/php7-wxwork-finance-sdk` | PHP 扩展 | star 较多，偏 PHP 生态 | 不适合当前 Python 工作流 |
| `chinayin/WeworkChatSDK` | Java 服务 | Java 版会话存档服务 | 需要 Java 服务栈时再看 |

## 本地 DB 路线缺口

当前本机自动定位到的企业微信 DB 候选包括：

- `Data\message_lookup.db`
- `Data\session.db`
- `Index\message_index.db`
- `Index\message_index_log.db`
- `Index\message_index_v1_1.db`
- `Index\session_index.db`
- `Index\session_index_log.db`

这些文件名看起来像索引/会话 lookup 层，并不等价于“可直接导出完整聊天正文”。后续应先做只读 schema 检查，再判断正文是否在 SQLite、LevelDB、加密 blob 或其他存储里。

本机 2026-05-27 的只读 schema 快照：

| 文件 | 结果 |
| --- | --- |
| `message_lookup.db` | 不是普通 SQLite，前 16 字节不是 `SQLite format 3` |
| `session.db` | 不是普通 SQLite |
| `message_index.db` | 不是普通 SQLite |
| `message_index_v1_1.db` | 不是普通 SQLite |
| `session_index.db` | 不是普通 SQLite |
| `message_index_log.db` | 普通 SQLite；包含 `general_kv`、`message_excludeV2`、`message_include`，当前行数为 0 |
| `session_index_log.db` | 普通 SQLite；包含 `session_exclude_v2`、`session_include` 等，当前行数为 0 |

非 SQLite 主库的前 8 字节当前都以 `01 43 EA EF 7C DC 3F C8` 开头，说明它们可能是企业微信自定义/加密存储，而不是可直接 `sqlite3` 打开的明文库。

## 推荐集成策略

1. 保留 `inventory_wechat_paths.ps1` 做定位。
2. 对本地 DB 用 `inspect_decrypted_sqlite.py` 做结构图，不直接读正文。
3. 对官方会话存档，用 `fetch_wecom_finance_archive.py` 通过 `PyWeWorkFinance` 拉取并归一化。
4. 所有输出统一成 `schemas/normalized_message.schema.json`。
