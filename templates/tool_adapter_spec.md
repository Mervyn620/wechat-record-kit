# Tool Adapter Spec

adapter 的目标是把外部工具输出转换成 `schemas/normalized_message.schema.json`，不要把第三方工具逻辑扩散到下游。

## 必填信息

- adapter 名称：
- 外部工具来源 URL：
- 工具版本/commit：
- 支持平台：
- 支持微信版本：
- 输入：
- 输出：
- 是否需要 key：
- 是否读取 live process：
- 是否联网：

## adapter 规则

- 所有输入路径必须显式传入，不自动扫描全盘。
- 默认只读。
- 输出写入 `wechat_record_kit/runs/` 或用户指定目录。
- 不在日志中打印 key、完整消息正文、手机号、邮箱或 token。
- 失败时保留错误原因和工具版本，不吞掉异常。
- 每条消息必须尽量填充 `talker_id`、`sender_id`、`time`、`content`。

## 最小验收

- 能处理空结果。
- 能处理中文路径。
- 能处理非文本消息。
- 能输出 JSONL。
- 能统计输入/输出条数。
- 能重复运行且不覆盖原始数据。

