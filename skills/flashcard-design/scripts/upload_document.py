#!/usr/bin/env python3
"""
文档上传脚本 - 自包含 MCP 客户端

职责：
1. 读取本地文件 → binary
2. base64 编码 → string
3. 调用 MCP 工具 training.file.upload_document
4. 轮询文件解析状态
5. 输出 JSON 结果

约束：
- 不能导入 coach-mcp-connect 的代码（技能隔离）
- 必须自包含，独立实现认证和 MCP 调用
- 配置必须与用户 MCP 环境同步
"""

import sys
import os
import json
import base64
import time
import argparse
import urllib.error
import urllib.request
from typing import Optional
from urllib.parse import urlparse


def _find_bundle_file(filename: str) -> Optional[str]:
    """从脚本位置向上遍历 6 层，查找 bundle 根目录中的文件（RFC-0005）。"""
    script_dir: str = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        candidate: str = os.path.join(script_dir, filename)
        if os.path.exists(candidate):
            return candidate
        script_dir = os.path.dirname(script_dir)
    return None


def _find_mcp_json() -> Optional[str]:
    """从脚本位置向上遍历 6 层，查找 mcp.json"""
    return _find_bundle_file("mcp.json")


def _find_auth_profile() -> Optional[dict]:
    """从 bundle 根目录读取 auth-profile.json（RFC-0005）。"""
    path = _find_bundle_file("auth-profile.json")
    if path:
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _load_mcp_config(mcp_url_override: Optional[str] = None) -> dict:
    """从 mcp.json 加载配置（只读取一次）"""
    mcp_json: Optional[str] = _find_mcp_json()
    if not mcp_json:
        if mcp_url_override:
            print("Error: --mcp-url given but mcp.json not found", file=sys.stderr)
            print("Need mcp.json to provide Authorization. Copy coach-mcp-connect/mcp.json.example", file=sys.stderr)
            sys.exit(1)
        print("Error: mcp.json not found", file=sys.stderr)
        print("Please copy coach-mcp-connect/mcp.json.example to mcp.json (project root or ~/mcp.json)", file=sys.stderr)
        print("and fill in the real key. See README First Configuration step 3.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(mcp_json) as f:
            config: dict = json.load(f)
        servers = config.get("mcpServers", {})
        if not servers:
            raise KeyError("No servers configured in mcp.json")
        # Apply URL override if given
        if mcp_url_override:
            server_config = next(iter(servers.values()))
            server_config["url"] = mcp_url_override
        return config
    except (KeyError, json.JSONDecodeError) as e:
        print(f"Error: Invalid mcp.json format: {e}", file=sys.stderr)
        print("Please check mcp.json structure", file=sys.stderr)
        sys.exit(1)


def _get_mcp_url(config: dict) -> str:
    """从已加载的配置中读取 MCP 服务器 URL"""
    servers = config.get("mcpServers", {})
    server_config = next(iter(servers.values()))
    return server_config["url"]


def _get_env_dir(mcp_url: str) -> str:
    """根据 MCP URL 生成环境隔离目录（跨平台：Windows 用 APPDATA，macOS/Linux 用 ~/.config）"""
    domain: str = urlparse(mcp_url).netloc
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.config")
    env_dir: str = os.path.join(base, "coach-mcp-connect", domain)
    os.makedirs(env_dir, mode=0o700, exist_ok=True)
    return env_dir


def _get_auth_headers(mcp_url: str, config: dict) -> dict:
    """获取认证 headers，按 auth-profile.json 的 supported_auth 顺序尝试（RFC-0005）。"""
    profile = _find_auth_profile()
    supported = profile["supported_auth"] if profile and "supported_auth" in profile else ["token", "oauth"]

    # 从已加载的配置中读取静态 header（供 token 分支使用）
    static_header: Optional[str] = None
    servers = config.get("mcpServers", {})
    if servers:
        server_config = next(iter(servers.values()))
        static_header = server_config.get("headers", {}).get("Authorization")

    for method in supported:
        if method == "token" and static_header:
            # sk_* 原样发送，其他检查是否已有 Bearer 前缀
            if static_header.startswith("sk_"):
                return {"Authorization": static_header}
            # 已有 Bearer 前缀则不重复添加
            if static_header.startswith("Bearer "):
                return {"Authorization": static_header}
            return {"Authorization": f"Bearer {static_header}"}
        elif method == "oauth":
            env_dir: str = _get_env_dir(mcp_url)
            tokens_file: str = os.path.join(env_dir, "tokens.json")
            if os.path.exists(tokens_file):
                try:
                    with open(tokens_file) as f:
                        tokens: dict = json.load(f)
                except (json.JSONDecodeError, OSError) as e:
                    print(f"Error: Failed to read tokens.json: {e}", file=sys.stderr)
                    print("Please re-run OAuth authentication:", file=sys.stderr)
                    print("  python3 <技能安装目录>/coach-mcp-connect/scripts/mcp_diagnose.py auth", file=sys.stderr)
                    sys.exit(1)
                access_token: Optional[str] = tokens.get("access_token")
                if access_token:
                    return {"Authorization": f"Bearer {access_token}"}

    # 认证失败 — 根据 profile 给出针对性提示
    if "token" in supported and "oauth" not in supported:
        print("Error: 当前环境需要静态 API key 认证。", file=sys.stderr)
        print("请在 mcp.json 的 headers.Authorization 中配置 API key（通常以 sk_ 开头）。", file=sys.stderr)
    else:
        print("Error: MCP authentication failed.", file=sys.stderr)
        print("Please run coach-mcp-connect skill to reconnect:", file=sys.stderr)
        print("  python3 <技能安装目录>/coach-mcp-connect/scripts/mcp_diagnose.py auth", file=sys.stderr)
    sys.exit(1)


def _parse_sse(body: str) -> dict:
    """Parse SSE response body, extract the last JSON-RPC message."""
    result = {}
    for line in body.splitlines():
        if line.startswith("data: "):
            data_str = line[6:]
            try:
                result = json.loads(data_str)
            except json.JSONDecodeError:
                continue
    if not result:
        print("Error: No valid data found in SSE response", file=sys.stderr)
        sys.exit(1)
    return result


def mcp_request(method: str, params: dict, mcp_url: str, auth_headers: dict) -> dict:
    """发送 MCP JSON-RPC 请求"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        mcp_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **auth_headers,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            content_type = response.headers.get("Content-Type", "")
            body = response.read().decode("utf-8")

            # Handle SSE response (text/event-stream)
            if "text/event-stream" in content_type:
                result_msg = _parse_sse(body)
            else:
                result_msg = json.loads(body)

            # Check for JSON-RPC protocol errors
            if "error" in result_msg:
                error = result_msg["error"]
                code = error.get("code", -1)
                message = error.get("message", "Unknown error")
                print(f"Error: MCP protocol error {code}: {message}", file=sys.stderr)
                sys.exit(1)
            return result_msg
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"Error: MCP request failed (HTTP {e.code}): {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: MCP request failed (network): {e.reason}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: MCP request failed (invalid JSON): {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: MCP request failed: {e}", file=sys.stderr)
        sys.exit(1)


def upload_document(file_path: str, mcp_url: str, auth_headers: dict) -> dict:
    """上传文档到 MCP 服务器"""

    # Check file size limit (50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024
    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE:
        print(f"Error: File too large ({file_size} bytes). Maximum size is 50MB.", file=sys.stderr)
        sys.exit(1)

    # 读取文件并 base64 编码
    with open(file_path, "rb") as f:
        file_content = base64.b64encode(f.read()).decode("utf-8")

    file_name = os.path.basename(file_path)

    # 调用 MCP 工具
    result = mcp_request(
        "tools/call",
        {
            "name": "training.file.upload_document",
            "arguments": {
                "fileContent": file_content,
                "fileName": file_name,
            },
        },
        mcp_url,
        auth_headers,
    )

    # 解包响应（三层结构）
    tool_result = result.get("result", {})
    if tool_result.get("isError"):
        print(f"Error: MCP tool call failed: {result}", file=sys.stderr)
        sys.exit(1)

    content = tool_result.get("content", [])
    if not content or not isinstance(content[0], dict):
        print("Error: Empty response from MCP tool", file=sys.stderr)
        sys.exit(1)

    try:
        business_data = json.loads(content[0].get("text", "{}"))
    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        print(f"Error: Failed to parse response: {e}", file=sys.stderr)
        sys.exit(1)

    file_id = business_data.get("fileId")
    if not file_id:
        print(f"Error: No fileId in response: {business_data}", file=sys.stderr)
        sys.exit(1)

    return {
        "fileId": file_id,
        "fileName": file_name,
        "size": business_data.get("size"),
        "mimeType": business_data.get("mimeType"),
    }


def poll_parse_status(file_id: int, mcp_url: str, auth_headers: dict, recovery_threshold: int = 1200) -> dict:
    """轮询文件解析状态"""
    start_time = time.time()
    error_count = 0
    max_errors = 3

    while True:
        elapsed = time.time() - start_time

        # 先检查超时（对所有状态生效，避免未知状态无限循环）
        if elapsed > recovery_threshold:
            print(f"Warning: Parse timeout after {int(elapsed)}s (recovery threshold)", file=sys.stderr)
            return {"fileId": file_id, "status": "timeout_recovery", "ready": False}

        result = mcp_request("tools/call", {
            "name": "training.file.status",
            "arguments": {"fileId": file_id}
        }, mcp_url, auth_headers)

        # 解包响应（瞬时错误允许重试）
        tool_result = result.get("result", {})
        if tool_result.get("isError"):
            error_count += 1
            if error_count >= max_errors:
                return {"fileId": file_id, "status": "error", "ready": False}
            time.sleep(5)
            continue

        content = tool_result.get("content", [])
        if not content or not isinstance(content[0], dict):
            error_count += 1
            if error_count >= max_errors:
                return {"fileId": file_id, "status": "error", "ready": False}
            time.sleep(5)
            continue

        try:
            business_data = json.loads(content[0].get("text", "{}"))
        except (json.JSONDecodeError, KeyError, AttributeError):
            error_count += 1
            if error_count >= max_errors:
                return {"fileId": file_id, "status": "error", "ready": False}
            time.sleep(5)
            continue

        # 成功解析，重置错误计数
        error_count = 0
        parse_status = business_data.get("parseStatus")

        if parse_status == 2:  # 解析完成
            return {"fileId": file_id, "status": "ready", "ready": True}

        elif parse_status == 3:  # 解析失败
            print(f"Error: File parsing failed for fileId={file_id}", file=sys.stderr)
            return {"fileId": file_id, "status": "failed", "ready": False}

        else:  # 0=未开始, 1=解析中, 或其他未知状态
            time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description="Upload document to MCP server")
    parser.add_argument("file_path", help="Path to the file to upload")
    parser.add_argument("--mcp-url", help="Override MCP server URL (Authorization still from mcp.json)")
    args = parser.parse_args()

    if os.path.islink(args.file_path):
        print(f"Error: Symlinks are not supported: {args.file_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(args.file_path):
        print(f"Error: Not a file or file not found: {args.file_path}", file=sys.stderr)
        sys.exit(1)

    config = _load_mcp_config(args.mcp_url)
    mcp_url = _get_mcp_url(config)
    auth_headers = _get_auth_headers(mcp_url, config)

    # 上传文件
    upload_result = upload_document(args.file_path, mcp_url, auth_headers)
    file_id = upload_result["fileId"]

    # 轮询解析状态
    poll_result = poll_parse_status(file_id, mcp_url, auth_headers)

    # 输出结果
    output = {**upload_result, "status": poll_result["status"]}
    print(json.dumps(output, ensure_ascii=False))

    # 所有非 ready 状态都退出 1
    if poll_result["status"] != "ready":
        sys.exit(1)


if __name__ == "__main__":
    main()
