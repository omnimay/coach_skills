# OAuth 授权流程稳健化设计

**日期**: 2026-09-16  
**状态**: Draft  
**作者**: Claude Code  
**审核**: TBD

## 背景与问题

`coach-mcp-connect` 技能的 OAuth 授权流程存在两个独立的 bug，导致授权链接无法正常工作：

### Bug 1: OAuth 端点路径丢失（invalid_target 错误）

**位置**: `skills/coach-mcp-connect/scripts/mcp_client.py:98-99`

**问题**:
```python
parsed = urllib.parse.urlparse(mcp_url)
base = f"{parsed.scheme}://{parsed.netloc}"  # 丢弃了 /coach 前缀
```

当 `mcp_url = "https://example.com/coach/mcp"` 时，生成的 `base = "https://example.com"`，丢失了 `/coach` 路径前缀。导致所有 OAuth 端点都指向错误的根域名：
- 错误: `https://example.com/oauth/register`
- 正确: `https://example.com/coach/oauth/register`

**影响**: 授权服务器返回 `{"error":"invalid_target"}`，浏览器无法打开授权页面。

### Bug 2: 授权码未换取 token（Not authenticated 错误）

**位置**: `skills/coach-mcp-connect/scripts/mcp_client.py:903-918`

**问题**:
```python
server_thread = threading.Thread(
    target=lambda: start_callback_server(port, state),
    daemon=True
)
server_thread.start()
webbrowser.open(auth_url)
server_thread.join(timeout=600)

if not server_thread.is_alive():
    print("Authorization completed. Check tokens file.")
```

Lambda 函数丢弃了 `start_callback_server()` 的返回值（授权码），且 `cmd_auth()` 从未调用 `exchange_code()` 换取 token。

**影响**: 即使授权页面成功打开并完成授权，token 也不会保存到 `tokens.json`，导致后续调用显示 `Not authenticated`。

### 根本原因

1. **URL 派生逻辑隐晦**: 没有明确说明为什么要丢弃路径，也没有验证派生结果是否正确
2. **OAuth 流程状态不透明**: 无法判断「授权成功但 token 未保存」和「授权失败」的区别
3. **错误处理不足**: 失败时信息不明确，难以诊断问题

## 目标

**主要目标**: 保证 OAuth 授权流程能够流畅实现，不再出现类似问题。

**次要目标**:
- 提高 OAuth 流程的可诊断性（清晰的日志和错误信息）
- 保持代码简洁，不引入不必要的复杂度
- 向后兼容（不影响已有的 `mcp.json` 配置）

## 非目标

- 不实现 OAuth 元数据自动发现（`.well-known/oauth-authorization-server`）
- 不支持多个 MCP 服务器配置切换
- 不改变现有的 token 刷新逻辑

## 设计方案

采用**稳健化重构**方案：修复两个 bug 的同时，改进 URL 派生逻辑的明确性和 OAuth 流程的状态管理。

### 1. URL 派生逻辑修复

**改动位置**: `mcp_client.py:71-107` (`_load_urls()` 函数)

**修改内容**:
```python
def _load_urls():
    """从 mcp.json 加载 MCP URL 并派生 OAuth 端点。"""
    global _override_mcp_url

    mcp_url = _override_mcp_url or os.environ.get("MCP_URL")

    if not mcp_url:
        mcp_json_path = _find_mcp_json()
        if mcp_json_path:
            with open(mcp_json_path, encoding="utf-8") as f:
                mcp_config = json.load(f)
            servers = mcp_config.get("mcpServers", {})
            if servers:
                first_server = next(iter(servers.values()))
                mcp_url = first_server.get("url")

    if not mcp_url:
        print(
            "ERROR: 无法确定 MCP URL。\n"
            "请通过以下方式之一指定：\n"
            "  1. 确保 mcp.json 在包根目录\n"
            "  2. 设置 MCP_URL 环境变量\n"
            "  3. 使用 --mcp-url 参数",
            file=sys.stderr,
        )
        sys.exit(1)

    parsed = urllib.parse.urlparse(mcp_url)
    
    # 剥离尾部 /mcp 端点段，保留路径前缀（如 /coach）
    path = parsed.path.rstrip('/')
    if path.endswith('/mcp'):
        path = path[:-4]  # 去掉 /mcp
    elif path.endswith('/mcp/'):
        path = path[:-5]  # 去掉 /mcp/
    
    base = f"{parsed.scheme}://{parsed.netloc}{path}"
    
    urls = {
        "mcp_url": mcp_url,
        "register_url": f"{base}/oauth/register",
        "token_url": f"{base}/oauth/token",
        "authorize_url": f"{base}/oauth/authorize",
        "resource": mcp_url,
    }
    
    # 启动时打印实际使用的端点（调试用）
    if os.environ.get("MCP_VERBOSE"):
        print(f"MCP URL: {mcp_url}", file=sys.stderr)
        print(f"OAuth base: {base}", file=sys.stderr)
        for key in ["register_url", "token_url", "authorize_url"]:
            print(f"  {key}: {urls[key]}", file=sys.stderr)
    
    return urls
```

**验证**:
- 单元测试: 输入 `https://example.com/coach/mcp` → 期望 base=`https://example.com/coach`
- 单元测试: 输入 `https://example.com/mcp` → 期望 base=`https://example.com`
- 单元测试: 输入 `https://example.com/prefix/mcp/` → 期望 base=`https://example.com/prefix`
- 手动验证: `MCP_VERBOSE=1 python3 mcp_client.py auth --status` 打印实际端点

### 2. OAuth 流程状态管理

**改动位置**: `mcp_client.py:849-923` (`cmd_auth()` 函数)

**修改内容**:
```python
def cmd_auth(args):
    """Handle auth command."""
    if args.status:
        tokens = load_tokens()
        client = load_client()
        if tokens and client:
            print(f"✓ Authenticated (client: {client.get('client_id', 'unknown')})")
            print(f"  Config dir: {CONFIG_DIR}")
        else:
            print("✗ Not authenticated")
        return

    # 端口检测
    port = args.port or DEFAULT_CALLBACK_PORT
    try:
        port, port_changed = _find_available_port(port)
        if port_changed:
            print(f"Port {args.port} in use, using {port} instead", file=sys.stderr)
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # 注册客户端
    client = load_client()
    if not client:
        print("Registering new client...", file=sys.stderr)
        client = register_client(port)
    else:
        client["_callback_port"] = port
        client["_callback_uri"] = f"http://127.0.0.1:{port}/callback"
        save_client(client)

    # 生成 PKCE
    code_verifier, code_challenge = generate_pkce()
    state = secrets.token_urlsafe(16)
    client["_code_verifier"] = code_verifier
    save_client(client)

    # 构建授权 URL
    auth_url = build_authorize_url(
        client["client_id"],
        code_challenge,
        state,
        client["_callback_uri"]
    )

    print(f"\nOpening browser for authorization...", file=sys.stderr)
    print(f"If browser doesn't open, visit:\n{auth_url}\n", file=sys.stderr)

    # 使用共享状态捕获授权码
    auth_result = {"code": None, "error": None}
    
    def callback_wrapper():
        try:
            code = start_callback_server(port, state)
            auth_result["code"] = code
        except Exception as e:
            auth_result["error"] = str(e)

    server_thread = threading.Thread(target=callback_wrapper, daemon=True)
    server_thread.start()

    webbrowser.open(auth_url)

    print("Waiting for authorization callback...", file=sys.stderr)
    server_thread.join(timeout=600)

    # 检查结果
    if auth_result["error"]:
        print(f"Authorization failed: {auth_result['error']}", file=sys.stderr)
        sys.exit(1)
    
    if not auth_result["code"]:
        print("Timeout waiting for callback.", file=sys.stderr)
        print("You can manually complete authorization:", file=sys.stderr)
        print(f"1. Visit: {auth_url}", file=sys.stderr)
        print(f"2. After redirect, copy the 'code' parameter from the URL", file=sys.stderr)
        print(f"3. (Manual code entry not implemented in this version)", file=sys.stderr)
        sys.exit(1)

    # 换取 token
    print("Exchanging authorization code for tokens...", file=sys.stderr)
    try:
        tokens = exchange_code(
            auth_result["code"],
            client["client_id"],
            code_verifier,
            client["_callback_uri"]
        )
        print(f"✓ Authentication successful!", file=sys.stderr)
        print(f"  Tokens saved to {TOKENS_FILE}", file=sys.stderr)
    except Exception as e:
        print(f"Failed to exchange code for tokens: {e}", file=sys.stderr)
        sys.exit(1)
```

**关键改进**:
1. **明确的步骤日志**: 每个阶段都打印状态（注册、打开浏览器、等待回调、换取 token）
2. **线程安全的状态捕获**: 使用 `auth_result` 字典存储结果
3. **错误处理**: 区分「回调出错」「超时」「token 交换失败」
4. **成功确认**: 明确打印 token 保存路径

### 3. 错误处理与用户反馈

**改进点**:
1. **分阶段日志**: 每个关键步骤都输出到 stderr（不影响 stdout 的业务数据）
2. **明确的错误信息**: 区分「网络错误」「授权被拒绝」「token 交换失败」「超时」
3. **verbose 模式**: `MCP_VERBOSE=1` 环境变量启用调试输出（URL、端点、响应详情）

**错误场景处理**:

| 场景 | 当前行为 | 改进后 |
|------|----------|--------|
| OAuth 端点 404 | 抛出 `urllib.error.HTTPError`，信息不明确 | 捕获并提示「OAuth 端点不可达，请检查 mcp.json 配置」 |
| 授权被拒绝 | 回调收到 `error=access_denied`，抛异常 | 明确显示「授权被用户拒绝」 |
| token 交换失败 | 抛出异常，信息不完整 | 显示服务器返回的详细错误 |
| 回调超时 | 打印手动操作指南 | 保留，但增加「是否继续等待」的提示 |
| 端口冲突 | 自动尝试相邻端口 | 保留，打印实际使用的端口 |

**日志输出示例**:
```
$ python3 mcp_client.py auth
Registering new client...
Opening browser for authorization...
If browser doesn't open, visit:
https://example.com/coach/oauth/authorize?response_type=code&...

Waiting for authorization callback...
Listening on http://127.0.0.1:8766/callback ...
✓ Authorization code received
Exchanging authorization code for tokens...
✓ Authentication successful!
  Tokens saved to ~/.config/coach-mcp-connect/tokens.json
```

### 4. 测试策略

**单元测试**:
1. **URL 派生逻辑**:
   - 输入 `https://example.com/coach/mcp` → 期望 base=`https://example.com/coach`
   - 输入 `https://example.com/mcp` → 期望 base=`https://example.com`
   - 输入 `https://example.com/prefix/mcp/` → 期望 base=`https://example.com/prefix`

2. **OAuth 流程状态**:
   - 模拟回调服务器返回 code
   - 验证 `exchange_code()` 被正确调用
   - 验证 token 保存到文件

**手动验证**:
```bash
# 清理旧配置
rm -rf ~/.config/coach-mcp-connect/

# 执行授权
python3 scripts/mcp_client.py auth

# 验证 token 文件存在
ls -l ~/.config/coach-mcp-connect/tokens.json

# 验证授权状态
python3 scripts/mcp_client.py auth --status

# 测试工具调用
python3 scripts/mcp_client.py tools
```

**成功标准**:
- [ ] 授权流程从头到尾走通，token 成功落盘
- [ ] `auth --status` 显示 `✓ Authenticated`
- [ ] 能够成功调用 `tools` 命令
- [ ] URL 派生逻辑正确处理各种路径格式

## 风险与缓解

**风险 1**: URL 派生逻辑改变可能影响现有配置  
**缓解**: 保持向后兼容，只修复明显的 bug（丢失路径前缀）

**风险 2**: 线程状态捕获可能引入竞态条件  
**缓解**: 使用简单的字典共享状态，Python 的 GIL 保证字典操作的原子性

**风险 3**: 日志输出可能影响现有脚本的输出解析  
**缓解**: 所有日志输出到 stderr，不影响 stdout 的业务数据

## 实施计划

1. **修复 URL 派生逻辑** (`_load_urls()` 函数)
2. **修复 OAuth 流程状态管理** (`cmd_auth()` 函数)
3. **添加 verbose 模式支持**
4. **编写单元测试**
5. **手动验证端到端流程**

## 附录

### 相关 RFC
- RFC 6749: OAuth 2.0 Authorization Framework
- RFC 7636: Proof Key for Code Exchange (PKCE)
- RFC 7591: OAuth 2.0 Dynamic Client Registration Protocol
- RFC 8707: Resource Indicators for OAuth 2.0

### 参考代码
- `start_callback_server()`: 已实现，返回授权码
- `exchange_code()`: 已实现，换取 token 并保存
- `refresh_token()`: 已实现，自动刷新 token
