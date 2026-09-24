# 连接器定义 · 深维智信·学习闪卡（flashcard）

## 定位

闪卡类能力的**市场分发单元**：一个市场条目、一个 MCP 端点、一套技能、一份独立 catalog。覆盖知识点闪卡的创建（双发布模式）、修改与学习入口。

## 状态：已接入

闪卡工具已注册并通过 MCP Gateway 可调用（2026-09-11）。工具域为 `training.flashcard.*`。

## MCP 端点

| 用途 | 值 |
|------|-----|
| MCP 通信 | `https://mcp.test.omnimay.com/coach/mcp` |
| OAuth resource | `https://mcp.test.omnimay.com/coach/mcp` |

## 工具域

```
training.flashcard.create
training.flashcard.update
training.flashcard.update_status
training.flashcard.get
```

共享工具（跨连接器复用）：

```
training.file.upload_document
training.file.status
```

AI 客户课程类工具（`training.course.create_ai_customer` 等）**不在**本连接器范围内。

## 角色路由

| 角色 | 模式 | 课程 useTo | 默认交付物 |
|------|------|-----------|------------|
| B 端管理员（有课程管理功能权限） | 编辑链接 | 0 | editUrl + manageUrl |
| B 端学员 / C 端学员（无权限） | 自动练习 | 4 | seriesCourseId + learnUrl |

发布模式由 `training.flashcard.create` 自动根据 mgvauth 功能权限路由，agent 不需要手动指定。

## 技能集（随连接器分发）

| 场景 | 入口 |
|------|------|
| 学习闪卡（创建/编辑，双发布模式） | `skills/flashcard_design/SKILL.md` |
| 自动练习模式（学员默认） | `skills/flashcard_design/references/create-auto.md` |
| 编辑链接模式（管理员默认） | `skills/flashcard_design/references/create-manual.md` |
