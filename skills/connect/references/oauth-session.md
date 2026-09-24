# OAuth 与 MCP 会话流程

## OAuth 2.0（PKCE + DCR）

1. **读取元数据**：`GET /.well-known/oauth-authorization-server/coach`（issuer 为 `https://mcp.test.omnimay.com/coach`，各端点以元数据返回为准）
2. **动态注册客户端**（RFC 7591，无 client_secret）：
   - `client_name`、`redirect_uris=["http://127.0.0.1:8765/callback"]`
   - `grant_types=["authorization_code","refresh_token"]`、`token_endpoint_auth_method="none"`
3. **生成 PKCE**：`code_verifier = secrets.token_urlsafe(32)`，`code_challenge = base64url(sha256(verifier))` 去填充
4. **拼授权 URL**（浏览器打开）：`response_type=code` + `client_id` + `redirect_uri` + `code_challenge` + `code_challenge_method=S256` + `state` + **`resource=https://mcp.test.omnimay.com/coach/mcp`**
5. **code 换 token**：POST `/coach/oauth/token`，字段为 authorization_code 五元组 + `resource`
6. **续期**：POST `/coach/oauth/token`，**严格 4 字段** `grant_type=refresh_token` / `refresh_token` / `client_id` / `resource`；禁止携带 `redirect_uri`、`code`、`code_verifier`

回调接收两种方式：
- 启动本地监听（推荐，`<skill-root>/scripts/mcp_client.py auth` 已实现）
- 无监听时请用户复制回调 URL，从中提取 `code`（页面报错可忽略）

## MCP 会话

```
1. initialize → 从响应头取 mcp-session-id
2. notifications/initialized（无 id）
3. tools/list
4. tools/call
```

每个请求头：
```
Authorization: Bearer <access_token>
mcp-session-id: <session_id>
Content-Type: application/json
Accept: application/json, text/event-stream
```

- 协议版本：`2025-03-26`（Streamable HTTP，SSE 响应）
- Token 有效期以响应 `expires_in` 为准（`/coach` AS 实测 15 天），脚本内置 auto-refresh
- 404 Session not found → 清除本地会话并重试一次
