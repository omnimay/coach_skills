# 深维智讯·学习闪卡 · MCP 安装指南

## 1. 在客户端市场添加连接器

| 连接器 | MCP 端点（目标） | 状态 |
|--------|------------------|------|
| 深维智讯·学习闪卡（flashcard） | `https://mcp.test.omnimay.com/coach/mcp` | 已上线 |

首次连接时 agent 会提示 OAuth 登录，token 自动管理。

## 2. 解压技能仓库

```bash
tar xzf coachskills-*.tar.gz -C ~/.claude/skills/
```

解压后目录记为 `<repo_root>`（示例：`~/.claude/skills/coachskills`）。各 skill 自包含（脚本与依赖内嵌于技能目录），按需加载即可。

## 3. 按场景加载技能

| 场景 | 加载入口 |
|------|----------|
| 学习闪卡 · 建卡/改卡/验题 | `skills/flashcard_design/SKILL.md` |
| 连接 / OAuth / 会话排障 | `skills/coach-mcp-connect/SKILL.md` |

---

## 关键配置细节

> 完整连接与排障见 `skills/coach-mcp-connect/`。以下为速查。

### OAuth

- **PKCE + 动态客户端注册（RFC 7591）**：无 client_secret
- **resource 参数必须带**：值 = 统一端点 `https://mcp.test.omnimay.com/coach/mcp`（生产 `https://mcp.omnimay.com/coach/mcp`）
- **refresh_token 严格 4 字段**：`grant_type` / `refresh_token` / `client_id` / `resource`
- **服务端轮换 refresh_token**：新 token 必须立即更新本地存储

### 协议特征

- Streamable HTTP，POST + JSON，响应 `text/event-stream`
- `mcp-session-id` 从 initialize 响应头获取，后续请求必带
- MCP 协议版本：`2025-03-26`
- Token 默认有效期 3600 秒，提前用 refresh_token 续期

### 自查流程

1. 元数据可达？`GET /.well-known/oauth-authorization-server/coach` 返回 200
2. 注册成功？`POST /coach/oauth/register` 返回 client_id
3. 授权链接可打开？能登录
4. token 换成功？返回 access_token
5. initialize 通？响应头含 `mcp-session-id`
6. `tools/list` 通？返回该连接的 `training.flashcard.*` 工具列表

---

## 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| 工具列表混入其他连接器工具 | 连接器端点/catalog 配置错误 | 检查端点与该连接器 catalog |
| Missing session ID | 未初始化 MCP 会话 | 先调 `initialize` |
| 401 / invalid_token | token 过期 | refresh 续期；refresh 失效则重新授权 |
| 405 Method Not Allowed | 管理接口用错域名 | 用 `mcp.test.omnimay.com` |
| 上游服务拒绝了本次请求 | 账号权限被撤 | 联系管理员恢复权限 |

**最关键一条**：报错原文一字不动贴回给 agent，99% 它能自查解决。
