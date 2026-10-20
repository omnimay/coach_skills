---
name: flashcard-design
description: 通过 OmniMay MCP 工具对话式创建/编辑闪卡（考官V2）课程，支持上传文档作为出题素材。自动根据用户权限路由权限分叉（管理员=编辑链接 / 学员=自动练习）。触发：用户要建闪卡课/考官课/出题/改题数/基于文档出题。
---

# 闪卡（考官V2）MCP 对话式建课/编辑

用 6 个 MCP 工具完成「建课 → 上传文档 → 对话出题 → 轮询取果 → 验题 → 增量编辑」。

## 工具总览

| 工具 | 用途 |
|---|---|
| `training.flashcard.create` | 创建闪卡课（**权限分叉**：自动路由管理员/学员路径） |
| `training.flashcard.update` | 对话式建课/编辑（**异步**：提交即返 `taskId`） |
| `training.flashcard.update_status` | 轮询任务状态，取最终回复或失败原因 |
| `training.flashcard.get` | 读取课程详情（题目/配置/答案），用于验题 |
| `training.file.upload_document` | 上传文档（base64），返回 `fileId`；自动触发解析 |
| `training.file.status` | 轮询文件解析状态（`parseStatus`） |

**响应格式**：业务成功时 `code=20000`，错误信息在 `errorMessage` 字段。snake_case 后端字段经 `camelCaseKeys` 中间件自动转 camelCase（如 `course_id` → `courseId`）。

## 权限分叉（create 自动路由）

| 角色 | useTo | 默认交付物 | learnUrl |
|---|---|---|---|
| 管理员（有课程管理权限） | 0 | `editUrl` + `manageUrl` | ❌ 不生成 |
| 学员（无权限） | 4 | `seriesCourseId` + `learnUrl`（done 后经 update_status 返回） | ✅ 内容生成后 |

- 管理员：`editUrl` / `manageUrl` 禁止展示给用户（改课一律走对话式 update，不引导用户去管理页手工编辑）。
- 学员：内容生成完成后再交付 `learnUrl`（create 时课程为空）。
- **编辑隔离**：`useTo=0` 仅管理员可编辑；`useTo=4` 仅创建者可编辑。

## 核心工作流

```text
1. create → courseId
2. (可选) upload_document → fileId → status 至 parseStatus=2
3. update(courseId, message 原话, metadata.fileIds)
   → taskId（status=running）
4. 每 5 秒 update_status 轮询至 done/failed
5. ⚠ GATE 确认门检测 → 方案请求需走确认轮（→ references/gate-detection.md）
6. get 验题 → 交付 learnUrl（管理员路径禁止展示 editUrl/manageUrl）
```

## 文档上传

**禁止**直接调用 MCP 工具 `training.file.upload_document`。Agent 没有文件 I/O 能力，无法生成 base64。

**必须**使用脚本上传：

```bash
python3 <技能安装目录>/flashcard-design/scripts/upload_document.py <文件路径> [--mcp-url <url>]
```

`--mcp-url <url>` 仅覆盖服务器 URL，`Authorization` 仍从 `mcp.json` 读取。

脚本返回 `{"fileId": 7667, "fileName": "doc.pdf", "status": "ready", ...}`。上传成功后，在建课对话中通过 `metadata.fileIds: [fileId]` 传递。

> 脚本报错时先使用 coach-mcp-connect 技能重新连接。完整错误处理与状态说明见 [file-reference.md](references/file-reference.md)。

### 强制决策规则

当用户提供了**原始文档文件**（PDF/Word/PPT/Excel/图片等附件），**必须**走文档上传路径：
- ✅ 调用 `upload_document.py` 脚本上传 → 拿到 fileId → 在 `flashcard.update` 中通过 `metadata.fileIds` 传递
- ❌ 禁止把文档内容提取为纯文字后只通过 `message` 传入

**判断逻辑**（按顺序命中即停）：
1. 用户已提供原始文档文件 → 强制走文档上传
2. 无原始文档但参考资料 >1000 字或含表格/图表 → 建议文档上传
3. 仅简短场景描述（<1000 字）→ 直接用对话文本

**fileIds 规则**：正整数数组，≤20 个，不可重复。**每次 update 都应携带 fileIds**（重复携带合法且必要：服务端按指纹去重，并用于陈旧解析恢复）。

## ⚠ GATE 确认门

done 后的 response 可能是「方案确认请求」或「中间生成状态」而非成品。
必须向终端用户转述方案并征得同意后再发确认轮。关键词列表与检测逻辑见 → `references/gate-detection.md`。

## 硬性规则

1. `message` 必须是终端用户**原话**（verbatim），禁止改写/翻译/合并。
2. `fileIds` 正整数、去重、≤20；重复携带合法且必要。
3. 不要对同一 courseId 并行发起多个 update（43503）。
4. 管理员建课后不要自动创建练习任务。
5. `learnUrl` 延迟交付：内容生成并验题后再交付。
6. **禁止提前宣告「课程创建成功」**：create 只建了 0 题空壳；全部题目生成且 get 验题通过后才可宣告「创建成功/已完成」。create 后只能报中间态（如「课程骨架已就绪，正在出题…」）。
7. **文档上传必须用脚本**：禁止直接调用 MCP 工具 `training.file.upload_document`，必须通过 `upload_document.py` 脚本上传（agent 无法处理文件的 base64 编码）。

## 错误码速查

详见 → `references/error-codes.md`

| 常见 | 含义 |
|---|---|
| 42901 | 积分不足 |
| 43502 | 无编辑权限（useTo=0 仅管理员） |
| 43503 | 生成中，稍后再试 |
| 43505 | fileIds 非法 |
| 50002 | agent 调用失败 |

#### 50002 详细处理流程

写库完成与状态翻转存在竞态，`update_status` 报 failed 时内容可能已写入成功。按以下步骤处理：

1. **验证课程是否已就绪**：调用 `flashcard.get` 检查
   - ✅ 已有题目（`questions.length > 0`）→ 视为实际成功，无需重试
   - ❌ 确认未完成 → 继续步骤 2

2. **等待冷却**：等待 ≥60s

3. **重试 1 次**：用**同义改写的消息**重试（⚠️ 这是 verbatim 规则的例外：服务端按 `messageSha256` 去重，原文重发会被判重复提交。改写示例：原文"请开始建课" → 改写为"计划没问题，请开始生成课程内容"）

4. **仍失败则报告**：附 `taskId` / `conversationId` 上报

## 文档索引

| 文件 | 内容 |
|---|---|
| `references/gate-detection.md` | GATE 关键词全表 + 检测逻辑 |
| `references/error-codes.md` | 全量错误码 + 应对 |
| `references/file-reference.md` | 文件上传/解析/引用详细规则 |
| `references/multi-turn-editing.md` | 多轮编辑 + verbatim 详规 |
| `references/known-behaviors.md` | 服务端已知怪癖 |
