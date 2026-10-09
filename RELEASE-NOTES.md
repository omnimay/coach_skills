# Release Notes

> ⚠️ **本文件已冻结为历史导航。** RFC-0006 实施后，各 bundle 独立版本管理，变更记录见 `bundles/<bundle>/CHANGELOG.md`。

## 1.0.1

- flashcard：新增 `coach-mcp-connect` 技能（MCP 连接自助诊断）
- ai-customer：版本号统一至 1.0.1
- 术语统一：50002 错误描述统一为"agent 调用失败"，建课时间统一为 5-10 分钟
- 修复：flashcard 错误码表 `task_id` → `taskId`，50003 补充冷却期说明

## 0.1.0-rc.1（未发布）
- 首个预览版：ai_customer_design 技能迁移 + Codex/WorkBuddy 双平台清单与构建
- 待 P4 验收与 P4.5 灰度后转 0.1.0

---

**各 bundle 最新变更记录**：
- [ai-customer CHANGELOG](bundles/ai-customer/CHANGELOG.md)
- [flashcard CHANGELOG](bundles/flashcard/CHANGELOG.md)
