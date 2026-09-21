---
name: coach-mcp-connect
description: MCP 连接诊断与恢复。当 MCP 工具不可用时，调用此技能恢复连接。
---

# Coach MCP Connect

当 MCP 工具无法使用时，此技能帮助用户恢复 MCP 连接。

## 何时使用

- 首次安装 bundle 后，MCP 工具不可用
- MCP 工具调用返回 401/403 认证错误
- 连接超时或网络错误
- 需要完成初次 MCP 配置

## 核心功能

1. **OAuth 认证**：默认方式，弹出浏览器完成登录
2. **Token 认证**：如果用户提供了 MCP Token（sk_ 开头或 Bearer Token），使用该 Token 完成配置
3. **连接诊断**：检查 MCP 服务器连通性和工具可用性

## 使用方式

执行 `mcp_diagnose.py` 脚本，根据用户情况自动选择认证方式：

```bash
# 检查认证状态
python3 mcp_diagnose.py auth --status

# OAuth 登录（默认）
python3 mcp_diagnose.py auth

# 列出可用工具（诊断）
python3 mcp_diagnose.py tools
```

**认证优先级**：
1. `mcp.json` 中的 `headers.Authorization`（如果已配置）
2. 已保存的 OAuth token
3. 执行 OAuth 流程

## 配置示例

如果用户持有 MCP Token，可在 `mcp.json` 中配置：

```json
{
  "mcpServers": {
    "enterprise-training": {
      "type": "streamableHttp",
      "url": "https://mcp.example.com/coach/mcp",
      "headers": {
        "Authorization": "sk_mcp_xxxxx..."
      }
    }
  }
}
```
