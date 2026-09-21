---
name: ai_customer_design
description: 创建和修改公司培训课程、上传课程资料、查询课程并生成练习链接。触发关键词：建课、AI 客户课程、AI 设计师对话、改课、查询培训课程、生成练习链接。
metadata:
  description_zh: 创建和修改公司培训课程，上传资料并生成练习入口。
  description_en: Create and edit company training courses and generate practice links.
---

# 公司培训课程技能（ai_customer_design）

通过 MCP 协议连接企业培训服务器，执行建课、改课、查询等操作。

**前提**：MCP 服务器已通过 agent 的原生 MCP 客户端注册并完成认证配置。

## 工具调用方式

MCP 工具（`training.*`、`organization.*`）通过 agent 的**原生 MCP 工具**直接调用。异步工具集（`training.ai_customer.*`）是普通 HTTP 请求-响应，所有 MCP 客户端均可直接调用。

**MCP 连接问题**：如果 MCP 工具不可用，调用 `coach-mcp-connect` 技能恢复连接。

**必须本地脚本**：QR 二维码渲染（见「二维码 + 链接展示」章节）。

## AI 客户异步工具集（RFC-0014）

> `training.ai_customer.{create, update, update_status, get}`——对标闪卡 `training.flashcard.*` 命名。
> submit 秒返 → 无 120s 网关超时；独立 task store → 无会话保护锁死；非流式 → 无平台流式缺陷。

### 工具清单

| 工具 | 用途 | 关键参数 |
|------|------|---------|
| `training.ai_customer.create` | 创建课程（权限分叉：管理员返回 editUrl/manageUrl，学员返回 courseId） | `{}` |
| `training.ai_customer.update` | 异步对话（返回 taskId，后台生成分钟级完成） | `{"courseId":123,"message":"..."}` |
| `training.ai_customer.update_status` | 轮询任务状态（每 5s 一次直到 done/failed） | `{"courseId":123,"taskId":"uuid"}` |
| `training.ai_customer.get` | 读取课程完整配置（需编辑权限） | `{"courseId":123}` |

### 调用模式

```
ai_customer.update({"courseId":123, "message":"创建药品销售课程"})
→ 秒返 {"taskId":"xxx", "conversationId":"yyy", "messageSha256":"abc...", "status":"running", "pollIntervalSeconds":5}

ai_customer.update_status({"courseId":123, "taskId":"xxx"})
→ 轮询直到 {"status":"done", "response":"...", "errorCode":0} 或 {"status":"failed", "errorCode":50002, "errorMessage":"..."}
→ done 时还可能返回 {"seriesCourseId":8001, "learnUrl":"https://..."}（学员路径自动创建系列课）

ai_customer.get({"courseId":123})
→ 返回课程完整配置（验证内容是否就绪）
```

### 错误码（in-band）

HTTP 200 + `code=20000` 为业务成功，`code≠20000` 为业务失败。错误信息在 `msg` 字段。

| 码 | 含义 | 处理 |
|---|------|------|
| 40001 | 参数无效 | 检查参数（message≤8000字符、metadata键≤20） |
| 42901 | 配额超限 | 积分配额耗尽，等待或联系管理员 |
| 42902 | 频率超限（10次/分钟）或在飞任务超限（≤3个） | 等待后重试 |
| 43501 | 课程不存在 | 核对 courseId |
| 43502 | 无编辑权限 | 核对权限 |
| 43503 | 课程正在生成中（10分钟生成锁） | 等待当前任务完成 |
| 43504 | 任务不存在 / 已过期（TTL 2小时）/ 不属于当前用户 | 重新 submit |
| 43505 | fileIds 无效 | 检查文件 |
| 50002 | agent 调用失败 | 重试一次，仍失败则报告 |
| 50003 | 会话创建失败 | 等 60s 重试（冷却期） |
| 50000 | 内部错误 | 报告运维 |

## 建课工作流

```
Step 1: training.ai_customer.create({}) → courseId
  → 管理员返回 {courseId, editUrl, manageUrl}
  → 学员返回 {courseId}（系列课延迟到内容生成后自动创建）

Step 2: training.ai_customer.update({"courseId":<id>, "message":"<课程简报>"})
  → 秒返 {"taskId":"xxx", "conversationId":"yyy", "messageSha256":"...", "status":"running", "pollIntervalSeconds":5}
  → 告知用户"建课请求已提交，预计 3-6 分钟完成"

Step 3: training.ai_customer.update_status({"courseId":<id>, "taskId":"xxx"}) 轮询
  → 每 5 秒调用一次
  → status="done" → Step 4
  → status="failed" → 读 errorMessage，决定重试或报告
  → 43504（任务过期）→ 重新 Step 2
  → ⚠️ 轮询期间全程静默，禁止询问用户"还在吗"

Step 4: training.ai_customer.get({"courseId":<id>}) → 验证课程内容
  → 检查 status="create_status_created" 且 stages.length > 0
  → ✅ 建课完成 → Step 5
  → ⚠️ 内容未就绪 → 等 30s 再查（agent 可能仍在写入），轮询最长 10 分钟

Step 5: training.task.create_open_project({"courseId":<id>}) → 拿到 link → 渲染二维码
```

**多轮对话**：Step 2-3 可重复调用。agent 可能先提问/出计划，需用户确认后再调 update 发送确认消息。

> ⚠️ **实测经验**：首次 `update` 几乎必然返回计划卡片（plan card）要求确认，`update_status` 秒返 `done` 但课程并未真正创建。必须发送第二轮 `update`（如"确认，请直接建课。"或"确认，开始生成。"）才触发实际内容生成。这是**预期行为**，不是错误。
>
> **时间差异**：第一轮 update 秒返 done（<5s），第二轮 update 触发内容生成（3-8 分钟）。改课同理（实际修改约 3-5 分钟）。不要因第一轮秒返就认为建课完成。
>
> **轮询间隔建议**：第二轮 update 后的前 2 分钟用 5s 间隔快速检查，之后可放宽到 10-15s 减少请求量。

**文件上传建课**：Step 2 通过 `metadata.fileIds` 传递文档。先 `training.file.upload_document` 上传 → `training.file.status` 轮询至 parseStatus=2 → 携带 fileIds 调 `ai_customer.update`。

### 并发与容量约束

| 约束 | 限制 | 说明 |
|------|------|------|
| 提交频率 | 10 次/分钟/用户 | 超出返回 `42902` |
| 在飞任务 | ≤3 个/用户 | 超出返回 `42902` |
| 生成锁 | 10 分钟/课程 | 同课程同时只能有一个生成任务，超出返回 `43503` |
| message 长度 | ≤8000 Unicode 字符 | 超出返回 `40001` |
| metadata 键数 | ≤20 | 超出返回 `40001`（含 fileIds 算 1 个键） |
| 任务记录 TTL | 2 小时 | 过期后查询 status 返回 `43504` |
| running 超时 | 11 分钟 | 自动标记 failed（errorCode=50002） |

**批量建课**：串行执行，避免超过并发限制。

### 建课完成的判断标准

**唯一可靠判定**：`training.ai_customer.get` 返回的 config 中 `status="create_status_created"` 且 `stages.length > 0`。

**不要依赖**：
- ❌ `update` 的 response 文字（AI 回复可能说"建课完成"但实际未完成）
- ❌ `update_status` 的 status="done"（只表示本轮对话结束，不等于课程已创建）

**原则：只信 `ai_customer.get` 的字段值。**

### 课程简报（Agent 内部检查清单）

建课前，Agent 必须能用一句话说清"这门课为什么对练习者有价值"——说不清则信息不足，需追问用户。

| 要素 | 说明 |
|------|------|
| 课程场景 | 行业背景、客户画像、对话环境 |
| 角色设定 | 练习者和 AI 各自扮演谁 |
| 评估维度 | 本次训练重点评估哪些方面 |
| 对话流程 | 大致阶段划分 |
| 专业知识 | 特定商品参数、卖点、竞品对比 |
| 参考资料 | 是否需要上传文档？用户已提供原始文档文件时强制走文档上传路径 |

## 改课工作流

```
Step 1: training.ai_customer.get({"courseId":<id>}) → 记录当前各字段的实际值（基线）

Step 2: training.ai_customer.update({"courseId":<id>, "message":"<修改诉求>"})
  → 秒返 {"taskId":"xxx", "status":"running"}
  → ⚠️ 建课后改课需等待 ~60s 冷却期，遇到 50003 等 60s 后重试，最多 3 次

Step 3: training.ai_customer.update_status({"courseId":<id>, "taskId":"xxx"}) 轮询
  → 每 5 秒一次，直到 status="done" 或 "failed"

Step 4: training.ai_customer.get({"courseId":<id>}) → 验证修改是否真的生效
  → ⚠️ AI 回复具有误导性！只信 get 的字段值，不信 update 的 response 文字
  → 首轮验证失败先等 30s 再查一次
  → 验证通过 → Step 5
  → 验证失败 → 重试 Step 2-3，最多 3 次，仍无变化 → 告知用户

Step 5: training.task.create_open_project({"courseId":<id>}) → 生成新链接 → 渲染二维码
```

**注意**：AI 助手能改角色、阶段、评分等，不能改 roundLimit/timeLimit 等运行参数。

## 文档上传工作流

### 强制决策规则

当用户提供了**原始文档文件**（PDF/Word/PPT/Excel/图片等附件），**必须**走文档上传路径：
- ✅ 调用 `training.file.upload_document` 上传 → 拿到 fileId → 在 `ai_customer.update` 中通过 `metadata.fileIds` 传递
- ❌ 禁止把文档内容提取为纯文字后只通过 `message` 传入

**判断逻辑**（按顺序命中即停）：
1. 用户已提供原始文档文件 → 强制走文档上传
2. 无原始文档但参考资料 >1000 字或含表格/图表 → 建议文档上传
3. 仅简短场景描述（<1000 字）→ 直接用对话文本

### 文档上传步骤

1. **上传文档**: `training.file.upload_document({"fileContent":"<base64>","fileName":"file.pdf"})` → fileId
2. **轮询解析**: `training.file.status({"fileId":456})` → parseStatus=2 完成 / =3 失败（移除该文件）/ =0,1 解析中（数秒后重查，超 20 分钟直接下一步）
3. **建课对话**: `training.ai_customer.update({"courseId":123, "message":"基于上传的产品手册生成课程", "metadata":{"fileIds":[456]}})`

**fileIds 规则**：正整数数组，≤20 个，不可重复。可重复携带同一 fileIds（幂等去重）。

## 二维码 + 链接展示（必须执行，缺一不可）

拿到练习链接后，**必须同时完成两件事**：

### ① 渲染并展示二维码图片

```bash
# 技能包内的路径（相对于技能包根目录）
python3 skills/ai_customer_design/scripts/render_qr.py '<练习链接>'

# 多门课程时指定不同输出文件名，避免覆盖
python3 skills/ai_customer_design/scripts/render_qr.py '<练习链接>' --out course1.png
python3 skills/ai_customer_design/scripts/render_qr.py '<练习链接>' --out course2.png
```

> **路径说明**：`render_qr.py` 位于 `ai_customer_design` 技能目录下（不是 `coach-mcp-connect`）。

### ② 同时附上原始链接文本

```
📱 请用手机扫描下方二维码进入练习：
[二维码图片]

🔗 练习链接（可复制）：https://xxx/yyy/zzz
```

**禁止**：只输出二维码不附链接 / 只输出链接不渲染二维码 / 大模型直接生成二维码。

### QR 降级处理

QR 生成失败（如脚本缺失、依赖未安装、输出路径不可写）时，不要中断流程——直接告知用户"二维码无法生成，请复制下方练习链接在手机浏览器中打开访问"，并附上原始练习链接文本即可。

## 常用工具

| 工具 | 用途 | 参数 |
|------|------|------|
| `training.ai_customer.create` | 创建 AI 客户课程（权限分叉） | `{}` |
| `training.ai_customer.update` | 异步对话（返回 taskId） | `{"courseId":123,"message":"..."}` |
| `training.ai_customer.update_status` | 轮询任务状态 | `{"courseId":123,"taskId":"uuid"}` |
| `training.ai_customer.get` | 读取课程完整配置 | `{"courseId":123}` |
| `training.task.create_open_project` | 生成练习链接 | `{"courseId":123}` |
| `training.course.list` | 课程列表 | `{}` 或 `{"categoryId":0}` |
| `training.task.get_detail_list` | 学员练习明细 | `{"source":1}` |
| `training.file.upload_document` | 上传文档文件 | `{"fileContent":"<base64>","fileName":"file.pdf"}` |
| `training.file.status` | 查询文件解析状态 | `{"fileId":456}` |
| `training.enum.lookup` | 枚举值查询 | 工具名用**点号分隔** |
| `organization.info_get` | 企业信息 | `{}` |

## 已知约定

- **认证透传**：工具调用自动用当前用户的 token 访问后端
- **字段转换**：snake_case 后端字段经 camelCaseKeys 自动转 camelCase
- **响应数据位置**：业务数据在 `result.structuredContent` **顶层**（无 `.data` 信封）

## 错误处理

| 错误 | 原因 | 处理 |
|------|------|------|
| 401 / invalid_token | token 过期 | 调用 `coach-mcp-connect` 技能恢复连接 |
| 43503 课程正在生成中 | 同课程已有任务进行中 | 等待当前任务完成 |
| 50003 会话创建失败 | 冷却期（建课后 ~60s） | 等 60s 后重试，最多 3 次 |
| 42902 频率超限 | 在飞任务超上限（≤3）或 submit 频率超 10/min | 等待后重试 |
| 工具参数无效 | JSON 格式错误或 schema 外字段 | 检查参数 |
| 40404 / 40000 / 40801 | 文件解析错误 | 停止，检查文件状态 |
