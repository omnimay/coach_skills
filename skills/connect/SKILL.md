---
name: connect
description: 深维智信·学习闪卡——MCP 连接与鉴权场景。触发：需要接入 MCP 服务器、排查 OAuth/token/会话问题。
---

# 深维智信·学习闪卡 · 平台 MCP 连接

面向接入开发与运维：OAuth 授权、MCP 会话、token 续期与连接排障。

## 连接器端点

| 连接器 | MCP 端点（目标） | resource（目标） |
|--------|----------------------|----------------------|
| 学习闪卡（flashcard） | `https://mcp.test.omnimay.com/coach/mcp` | `https://mcp.test.omnimay.com/coach/mcp` |

> 端点 `…/coach/mcp` 自 2026-09-14 起为统一端点；共享脚本 `mcp_client.py` 经 `MCP_URL` 环境变量指向该端点。旧端点 `/mcp` 仅存量使用。

## 平台 OAuth 端点（issuer = `…/coach`）

| 用途 | URL |
|------|-----|
| OAuth 元数据 | `https://mcp.test.omnimay.com/.well-known/oauth-authorization-server/coach` |
| 授权 | `https://mcp.test.omnimay.com/coach/oauth/authorize` |
| Token | `https://mcp.test.omnimay.com/coach/oauth/token` |
| 客户端注册 | `https://mcp.test.omnimay.com/coach/oauth/register` |

> resource 元数据（RFC 9728）：`/.well-known/oauth-protected-resource/coach/mcp`；`resource` 参数必须恰为 MCP 端点值，否则 401。

> ⚠️ 管理接口用 `mcp.test.omnimay.com`，不是 `mcp.test.mgvai.com`（后者 405）。

## 硬性规则

1. OAuth 使用 **PKCE + DCR**；授权与换 token 必须携带 `resource` 参数。
2. refresh_token 请求**严格 4 字段**：`grant_type` / `refresh_token` / `client_id` / `resource`；多带字段返回 400。
3. 服务端轮换 refresh_token，响应中的新 token 必须立即落盘，旧的即刻失效。
4. `mcp-session-id` 从 initialize **响应头**获取，后续请求必带。
5. token 保存于 `~/.config/coach-mcp-connect/`（0700/0600），禁止打印到对话或日志。

## 按需阅读

| 文档 | 何时读 |
|------|--------|
| `references/oauth-session.md` | 手工实现 OAuth 或 MCP 会话流程 |
| `references/troubleshooting.md` | 连接失败、401、session 失效等排障 |

## 脚本方式（推荐）

端点解析顺序：`--mcp-url` 参数 > `MCP_URL` 环境变量 > 向上查找 `mcp.json`（本技能不携带，推荐环境变量）。

```bash
export MCP_URL=https://mcp.test.omnimay.com/coach/mcp    # 生产：https://mcp.omnimay.com/coach/mcp
python3 <skill-root>/scripts/mcp_client.py auth              # OAuth 授权（PKCE + DCR）
python3 <skill-root>/scripts/mcp_client.py auth --status     # token/会话状态
python3 <skill-root>/scripts/mcp_client.py tools             # 连通性自查（tools/list）
```

> 客户端脚本另有 `call` / `stream` / `registry_get` / `registry_publish` 等命令，供 ops/开发/CI 与非宿主平台渠道（如钉钉云等）使用——不在 bundle 内 SKILL.md 文档化，以保持 bundle 用户的工具调用走宿主平台通道（治理/审计/计费一致）。脚本随连接器一起分发，需要时直接调用即可。
>
> 客户端支持无状态服务器（initialize 不返回 `mcp-session-id` 时自动降级）、通知请求符合 JSON-RPC 2.0（无 id 字段）、建课类长任务默认 660s 超时预算。
