# {bundle_name}

> {bundle_description}

## 概述

{bundle_name} 是一个 MCP 技能包，包含以下技能：

{skills_list}

> ⚠️ **注意**：请勿直接点进 `skills/` 目录操作。请按照下方安装指南完成配置后，通过 MCP 客户端使用技能。

## 安装指南

### 1. 配置 MCP Server

首先查看当前宿主 MCP 客户端的正确配置方式，然后在宿主机的 MCP server 中添加以下配置：

```json
{mcp_json_example}
```

### 2. 安装技能

将包内的各个技能分别安装到宿主机的宿主 agent 中。

### 3. 验证

查看技能列表，确认技能已正确加载，然后使用 `mcp-connect` 技能开展后续工作。

## 技能列表

{skills_details}

## 故障排查

### MCP 工具不可用

如果 MCP 工具无法使用，请检查：

1. **配置文件语法**：确保 JSON 格式正确
2. **MCP Server URL**：确认 URL 可访问
3. **认证信息**：如果需要 token，确保已正确配置

### 技能未加载

如果技能未出现在客户端中：

1. 检查 `mcp.json` 是否已正确合并到客户端配置
2. 重启 MCP 客户端
3. 查看客户端日志，确认无错误信息

### 连接诊断

使用 `mcp-connect` 技能进行连接诊断（如果包中包含此技能）。
