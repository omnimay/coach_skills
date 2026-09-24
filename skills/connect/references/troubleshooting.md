# 连接排障

## 自查顺序

1. 元数据可达？`GET /.well-known/oauth-authorization-server/coach` 返回 200
2. 注册成功？`POST /coach/oauth/register` 返回 `client_id`
3. 授权链接可打开？能登录
4. token 换成功？返回 `access_token`
5. initialize 通？响应头含 `mcp-session-id`
6. `tools/list` 通？返回工具列表
7. 任意工具能调？`training.enum.lookup` 无入参，最易验证

## 错误对照

| 现象 | 原因 | 解决 |
|------|------|------|
| Missing session ID | 未初始化 | 先调 `initialize` |
| 401 invalid_token | token 过期 | refresh 续期；refresh 失效则重新授权 |
| 400 invalid_request（refresh） | 多带了 `redirect_uri` 等字段 | 严格只传 4 字段 |
| 405 Method Not Allowed | 管理接口用错域名 | 用 `mcp.test.omnimay.com` |
| 上游服务拒绝了本次请求 | 账号权限被下掉 | 联系管理员恢复权限 |
| 授权链接循环跳登录页 | 登录态丢失 | 重新登录 |
| 工具列表为空 | MCP URL 错误 | 检查服务器 URL |
| 列表正常但查不到数据 | X-Token 鉴权未通 | 先调 `organization.info_get` 验证 |

## 脚本排障

```bash
python3 <skill-root>/scripts/mcp_client.py tools   # 连通性自查（原 ping 命令已并入）
python3 <skill-root>/scripts/mcp_client.py auth --status
```
