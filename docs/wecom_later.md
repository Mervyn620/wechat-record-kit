# 企业微信后续准备

企业微信不要直接套普通微信路径假设。后续有环境时，先做只读定位和版本记录，再决定是否单独写 adapter。

## 需要现场记录

- 企业微信版本号。
- Windows 安装路径。
- 数据根目录。
- 登录账号、企业/组织标识是否体现在目录结构里。
- 是否有 `WXWork`、`WeCom`、`WeChat Files` 之外的专用目录。
- 是否存在 SQLite、LevelDB、日志、缓存、媒体目录。
- 是否能通过官方导出、合规后台、企业管理侧接口或本地客户端查看历史。

## 复用普通微信 kit 的部分

可复用：

- 只读目录 inventory 思路。
- SQLite schema 检查脚本。
- normalized JSONL schema。
- adapter 规范。
- runbook 记录方式。

不可直接复用：

- 普通微信 DB 文件名假设。
- 普通微信 key/decrypt 工具。
- 普通微信联系人/群聊字段映射。

## 推荐开工顺序

1. 只读扫描 `Documents`、`AppData\Roaming`、`AppData\Local` 下的企业微信目录，并用 `-IncludeWeCom` 记录安装目录候选。
2. 复制候选数据到隔离工作目录。
3. 对 `.db` / `.sqlite` / `.ldb` / 日志文件做类型识别，不直接读正文。
4. 先写 schema map，再写 adapter。
5. 输出仍走 `normalized_message.schema.json`，保证下游不用关心来源是普通微信还是企业微信。

## 示例验证记录

一次只读 inventory 记录的字段示例：

- 安装目录：`<WXWORK_INSTALL_DIR>`
- 可执行文件：`WXWork.exe`
- 数据目录候选：`<USER_DOCUMENTS>\WXWork`、`<APPDATA>\Tencent\WXWork`

不要把真实用户名、机器名、公司名、账号目录或 inventory 原始输出提交到仓库。

## 官方会话存档路线

GitHub 上更成熟的是官方会话内容存档 SDK 封装，不是本地 DB 解密工具。可以把第三方 SDK 下载到 `wechat_record_kit/vendors/` 做本地 adapter 测试；该目录默认被 `.gitignore` 忽略，避免提交第三方二进制库或运行产物。

这个路线需要：

- 企业后台开通会话内容存档。
- `WECOM_CORP_ID`
- `WECOM_FINANCE_SECRET`
- `WECOM_RSA_PRIVATE_KEY`

示例：

```powershell
$env:WECOM_CORP_ID="..."
$env:WECOM_FINANCE_SECRET="..."
$env:WECOM_RSA_PRIVATE_KEY="D:\path\to\private_key.pem"
python -X utf8 .\wechat_record_kit\scripts\fetch_wecom_finance_archive.py --seq 0 --limit 100 --out .\wechat_record_kit\runs\wecom_archive.normalized.jsonl
```

如果只有本机 `Documents\WXWork` 数据库，没有企业后台会话存档配置，则这条路线不能用，需要继续走本地 DB schema/adapter 逆向。
