# RFC-0004: 新增 dingtalk 打包环境

> **注**：认证能力声明部分已被 [RFC-0005](RFC-0005-environment-auth-profile.md) 取代——"仅 token"从运行时行为变为打包时 `auth-profile.json` 声明。

| 字段 | 值 |
|------|-----|
| 编号 | RFC-0004 |
| 状态 | Completed（部分取代） |
| 作者 | zoushen |
| 日期 | 2026-09-17 |
| 变体 | minimal |
| 目标版本 | sales-coach v0.1.3 |

## 核心概要

为钉钉部署场景新增 `dingtalk` 打包环境，使 `pack.py --env dingtalk` 可生成指向钉钉 MCP 服务的测试包。

**共识**：

- `environments.json` 仅需新增 `MCP_URL`，与现有环境保持一致的 KV 结构
- `MCP_BEARER_TOKEN` 是运行时配置（用户 `export` 设置），不写入仓库

## 1. 背景与上下文

当前 `environments.json` 有两个环境：

| 环境 | MCP_URL |
|------|---------|
| test | `https://mcp.test.omnimay.com/coach/mcp` |
| coach | `https://mcp.omnimay.com/coach/mcp` |

钉钉部署场景需要独立的 MCP 服务地址：

| 环境 | MCP_URL | 认证方式 |
|------|---------|----------|
| dingtalk | `https://aicoach.eapps.dingtalkcloud.com/omnimay/coach/mcp` | 仅 token（无 OAuth） |

**现状约束**：
- `mcp_client.py` 已支持 `MCP_BEARER_TOKEN` 环境变量直接注入 token（绕过 OAuth）
- 钉钉环境"仅 token"是运行时行为，不影响打包逻辑

## 3. 决策

> 复用现有的环境配置机制，零代码改动。

在 `environments.json` 中新增：

```json
{
  "dingtalk": {
    "MCP_URL": "https://aicoach.eapps.dingtalkcloud.com/omnimay/coach/mcp"
  }
}
```

**复用既有模块**：
- `scripts/pack.py --env dingtalk` 自动读取新环境配置
- `bundle_builder/bundle.py` 的 `load_environments()` / `resolve_placeholders()` 无需改动
- `bundle.json` 中的 `${MCP_URL}` 占位符通用，无需修改

**skill 文档**：不修改。`SKILL.md` 已覆盖"部分环境可能不支持 OAuth"的情况，无需硬编码特定环境名。

## 4. 备选方案与权衡

无重大备选。现有机制已完全满足需求，无需引入额外复杂度。

## 5. 结果与影响

- **正面**：
  - 支持钉钉部署场景的独立打包
  - 零代码改动，仅配置新增
  - 与现有环境命名风格一致（小写、无分隔符）

- **负面**：
  - 无

## 8. 开放问题

- 无（决策已完全对齐）
