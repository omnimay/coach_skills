#!/usr/bin/env python3
"""
mcp_client.py — Portable MCP client for enterprise training server.

Pure Python stdlib (no pip dependencies). Handles:
- OAuth 2.0 PKCE + Dynamic Client Registration (RFC 7591)
- MCP session management (initialize → tools/call)
- SSE response parsing
- Token persistence and auto-refresh

Usage:
    python3 mcp_client.py auth [--port PORT]
    python3 mcp_client.py auth --status
    python3 mcp_client.py tools
    python3 mcp_client.py registry_get
    python3 mcp_client.py registry_publish <catalog_json>

Note: This is a diagnostic tool. For business tool calls, use the host MCP client.
"""

import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

# ============================================================================
# UTF-8 Encoding — prevent garbled output on Windows
# ============================================================================

# Force UTF-8 for stdout/stderr to handle Chinese characters correctly
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    import io
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============================================================================
# Configuration — 运行时从包内 mcp.json 读取，适配不同环境
# ============================================================================

# 可通过 --mcp-url CLI 参数或 MCP_URL 环境变量覆盖
_override_mcp_url = None


def _find_mcp_json():
    """从脚本位置向上查找 mcp.json（在 ZIP 包根目录或开发目录根）。"""
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        candidate = os.path.join(current, "mcp.json")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


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


# 延迟初始化：首次调用 get_url() 时加载
_urls = None


def _init_urls():
    global _urls
    if _urls is None:
        _urls = _load_urls()
    return _urls


def get_mcp_url():
    return _init_urls()["mcp_url"]


def get_register_url():
    return _init_urls()["register_url"]


def get_token_url():
    return _init_urls()["token_url"]


def get_authorize_url():
    return _init_urls()["authorize_url"]


def get_resource():
    return _init_urls()["resource"]

MCP_VERSION = "2025-03-26"
REQUEST_TIMEOUT = 660  # 11 min — streaming chat rounds take 5-6 min

CONFIG_DIR = os.path.expanduser("~/.config/coach-mcp-connect")
CLIENT_FILE = os.path.join(CONFIG_DIR, "client.json")
TOKENS_FILE = os.path.join(CONFIG_DIR, "tokens.json")
SESSION_FILE = os.path.join(CONFIG_DIR, "session.json")

DEFAULT_CALLBACK_PORT = 8766  # Different from mcp-training's 8765
CLIENT_NAME = "coach-mcp-connect-skill"


# ============================================================================
# Secure Storage
# ============================================================================


def _ensure_config_dir():
    """Create config directory with 0700 permissions."""
    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)


def _write_secure(path, data):
    """Write JSON with 0600 permissions. Atomic via temp-then-rename."""
    _ensure_config_dir()
    tmp_path = path + ".tmp"
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"))
    finally:
        os.close(fd)
    os.replace(tmp_path, path)
    os.chmod(path, 0o600)


def _read_secure(path):
    """Read JSON from file. Returns None if not found."""
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_client():
    return _read_secure(CLIENT_FILE)


def save_client(data):
    _write_secure(CLIENT_FILE, data)


def load_tokens():
    return _read_secure(TOKENS_FILE)


def save_tokens(data):
    _write_secure(TOKENS_FILE, data)


def load_session():
    return _read_secure(SESSION_FILE)


def save_session(data):
    _write_secure(SESSION_FILE, data)


def clear_session():
    try:
        os.remove(SESSION_FILE)
    except FileNotFoundError:
        pass


# ============================================================================
# OAuth Module
# ============================================================================


def register_client(callback_port):
    """POST /oauth/register — RFC 7591 Dynamic Client Registration."""
    callback_uri = f"http://127.0.0.1:{callback_port}/callback"
    body = json.dumps({
        "client_name": CLIENT_NAME,
        "redirect_uris": [callback_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none"
    }).encode("utf-8")

    req = urllib.request.Request(get_register_url(), data=body, method="POST")
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    if "client_id" not in result:
        raise RuntimeError(f"Registration failed: {result}")

    result["_callback_port"] = callback_port
    result["_callback_uri"] = callback_uri
    save_client(result)
    return result


def generate_pkce():
    """Generate PKCE pair using S256. Returns (verifier, challenge)."""
    code_verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def build_authorize_url(client_id, code_challenge, state, callback_uri):
    """Build authorization URL. resource parameter is MANDATORY."""
    params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": callback_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "resource": get_resource(),
    })
    return f"{get_authorize_url()}?{params}"


def _find_available_port(start_port, max_attempts=5):
    """Find an available port starting from start_port. Returns (port, is_changed)."""
    for offset in range(max_attempts):
        port = start_port + offset
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", port))
            sock.close()
            return port, offset > 0
        except OSError:
            sock.close()
    raise OSError(f"No available port found in range {start_port}-{start_port + max_attempts - 1}")


def start_callback_server(port, expected_state, timeout=600):
    """Start HTTP server to capture OAuth callback. Returns auth code."""
    state = {"code": "", "error": ""}
    done = threading.Event()

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)

            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return

            if "error" in query:
                state["error"] = query["error"][0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"<h1>Error: {query['error'][0]}</h1>".encode())
                done.set()
                return

            if "code" not in query:
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>No code parameter</h1>")
                return

            received_state = query.get("state", [None])[0]
            if received_state != expected_state:
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>State mismatch</h1>")
                return

            state["code"] = query["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = "<html><body><h1>Authorization successful!</h1><p>You can close this window.</p></body></html>"
            self.wfile.write(msg.encode("utf-8"))
            done.set()

        def log_message(self, format, *args):  # noqa: N802  # pyright: ignore[reportIncompatibleMethodOverride]
            pass  # Suppress default logging

    server = http.server.HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = 1

    print(f"Listening on http://127.0.0.1:{port}/callback ...", file=sys.stderr)

    start_time = time.time()
    while not done.is_set() and (time.time() - start_time) < timeout:
        server.handle_request()

    server.server_close()

    if state["error"]:
        raise RuntimeError(f"OAuth error: {state['error']}")

    if not state["code"]:
        return None

    return state["code"]


def exchange_code(code, client_id, code_verifier, callback_uri):
    """POST /oauth/token with authorization_code grant."""
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "redirect_uri": callback_uri,
        "code_verifier": code_verifier,
        "resource": get_resource(),
    }).encode("utf-8")

    req = urllib.request.Request(get_token_url(), data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    if "access_token" not in result:
        raise RuntimeError(f"Token exchange failed: {result}")

    save_tokens(result)
    return result


def refresh_token(client_id, refresh_token_value):
    """POST /oauth/token with refresh_token grant. Strict 4 fields only."""
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token_value,
        "client_id": client_id,
        "resource": get_resource(),
    }).encode("utf-8")

    req = urllib.request.Request(get_token_url(), data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Token refresh failed: {e.code} {error_body}")

    if "access_token" not in result:
        raise RuntimeError(f"Token refresh failed: {result}")

    save_tokens(result)
    return result


def get_valid_token():
    """Get a valid access token, refreshing if needed."""
    tokens = load_tokens()
    client = load_client()

    if not tokens or not client:
        return None

    # Try to use current token (no expiry check for simplicity)
    access_token = tokens.get("access_token")
    if access_token:
        return access_token

    # Try to refresh
    refresh_token_value = tokens.get("refresh_token")
    client_id = client.get("client_id")

    if refresh_token_value and client_id:
        try:
            new_tokens = refresh_token(client_id, refresh_token_value)
            return new_tokens.get("access_token")
        except Exception as e:
            print(f"Token refresh failed: {e}", file=sys.stderr)
            return None

    return None


# ============================================================================
# SSE Streaming — real-time progress notification processing
# ============================================================================


def _process_streaming_response(resp, notifications_out=None, progress_file=None):
    """Process SSE streaming response in real-time.

    Reads line by line, displays progress events immediately,
    returns the final result when complete/error event is received.

    notifications_out: optional list; when given, every notifications/progress
        event is appended as {"ts", "progressToken", "progress", "message"}.
    progress_file: file object for progress display (default sys.stderr).
        Pass sys.stdout so agents (Bash tool) can capture progress inline.

    Display rule: [message] -prefixed messages are AI-speech deltas (live
    preview); anything else is a stage title. The numeric progress field is
    intentionally NOT shown as a percentage — the backend sends 0/absent for
    most stages (only auto_testing carries real 0-100), so a derived percent
    misleads more than it informs.
    """
    if progress_file is None:
        progress_file = sys.stderr
    result_msg = None
    current_data = []
    start = time.time()

    for line_bytes in resp:
        line = line_bytes.decode("utf-8", "replace").rstrip("\n\r")

        # Empty line = end of event
        if not line:
            if current_data:
                data_str = "\n".join(current_data)
                try:
                    msg = json.loads(data_str)

                    # Check if this is a progress notification
                    if msg.get("method") == "notifications/progress":
                        params = msg.get("params", {})
                        message = params.get("message", "")
                        if notifications_out is not None:
                            notifications_out.append({
                                "ts": round(time.time() - start, 1),
                                "progressToken": params.get("progressToken"),
                                "progress": params.get("progress"),
                                "message": message,
                            })

                        # Display progress to user
                        if isinstance(message, str) and message.startswith("[message] "):
                            print(f"💬 {message[len('[message] '):]}", file=progress_file, flush=True)
                        elif message:
                            print(f"📊 {message}", file=progress_file, flush=True)

                    # Check if this is the final result
                    elif "result" in msg:
                        result_msg = msg

                    # Check for error
                    elif "error" in msg:
                        result_msg = msg
                        break

                except json.JSONDecodeError:
                    pass

            # Reset for next event
            current_data = []
            continue

        # Parse SSE fields
        if line.startswith("data:"):
            current_data.append(line[5:].strip())
        # event: and : (comment/heartbeat) fields are intentionally ignored

    # If no result was found in streaming, raise error
    if result_msg is None:
        raise RuntimeError("Stream ended without receiving a result")

    return result_msg


# ============================================================================
# MCP Session Module
# ============================================================================


def mcp_request(method, params=None, session_id=None,
                progress_token=True, notifications_out=None, progress_file=None):
    """Make a JSON-RPC request to MCP server.

    progress_token: inject _meta.progressToken into tools/call params (default
        True) — the server only pushes notifications/progress to requests that
        carry a token; without it no intermediate notifications arrive.
        Pass None/False to disable, or an explicit string to use a fixed token.
    notifications_out: optional list forwarded to _process_streaming_response;
        every notifications/progress event is appended as a dict.
    progress_file: file object for progress display (default sys.stderr).
        Pass sys.stdout so agents (Bash tool) can capture progress inline.
    """
    is_notification = method.startswith("notifications/")
    payload: dict = {"jsonrpc": "2.0", "method": method}
    # JSON-RPC 2.0: notifications MUST NOT include "id" (RFC 8780 §4.1)
    if not is_notification:
        payload["id"] = int(time.time() * 1000) % 1000000
    if params is not None:
        payload["params"] = params

    # MCP 规范：携带 progressToken 才会收到 notifications/progress
    if progress_token and method == "tools/call" and params is not None:
        if "_meta" not in params:
            params["_meta"] = {}
        meta = params["_meta"]
        if not meta.get("progressToken"):
            meta["progressToken"] = f"ntf-{payload['id']}"
        payload["params"] = params

    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(get_mcp_url(), data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")

    token = get_valid_token()
    if not token:
        raise RuntimeError("Not authenticated. Run 'auth' first.")
    req.add_header("Authorization", f"Bearer {token}")

    if session_id:
        req.add_header("mcp-session-id", session_id)

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            # Extract session ID from response headers if present
            new_session_id = resp.headers.get("mcp-session-id")

            content_type = resp.headers.get("Content-Type", "")
            is_streaming = "text/event-stream" in content_type

            if is_streaming:
                # True streaming: read line by line, process SSE events in real-time
                result_msg = _process_streaming_response(
                    resp, notifications_out=notifications_out, progress_file=progress_file)
            else:
                # Non-streaming: read entire response and parse
                response_body = resp.read().decode("utf-8")
                if "text/event-stream" in content_type:
                    result_msg = _parse_sse_response(response_body)
                elif not response_body.strip():
                    # Empty body: server accepted notification (202) with no response
                    result_msg = None
                else:
                    result_msg = json.loads(response_body)

            if result_msg is None:
                return None, new_session_id

            if "error" in result_msg:
                error = result_msg["error"]
                code = error.get("code", -1)
                message = error.get("message", "Unknown error")
                raise RuntimeError(f"MCP error {code}: {message}")

            return result_msg.get("result", result_msg), new_session_id

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")

        # Handle 401: auth expired - clear session, refresh token, retry
        if e.code == 401:
            clear_session()
            tokens = load_tokens()
            client = load_client()
            if tokens and tokens.get("refresh_token") and client:
                try:
                    refresh_token(client["client_id"], tokens["refresh_token"])
                    return mcp_request(
                        method, params, session_id=session_id,
                        progress_token=progress_token,
                        notifications_out=notifications_out,
                        progress_file=progress_file)
                except Exception:
                    pass
            raise RuntimeError("Authentication failed. Run 'auth' first.")

        # Handle 404 with "Session not found": MCP session expired
        if "Session not found" in error_body and session_id:
            clear_session()
            return mcp_request(
                method, params, session_id=None,
                progress_token=progress_token,
                notifications_out=notifications_out,
                progress_file=progress_file)

        raise RuntimeError(f"MCP request failed: {e.code} {error_body}")


def _parse_sse_response(response_body):
    """Parse SSE response and return the last data JSON."""
    last_data = None
    for line in response_body.split("\n"):
        if line.startswith("data:"):
            data_str = line[5:].strip()
            if data_str:
                try:
                    last_data = json.loads(data_str)
                except json.JSONDecodeError:
                    pass
    return last_data


def initialize_session() -> str | None:
    """Initialize MCP session.

    Supports both stateful and stateless server modes:
    - Stateful: server returns mcp-session-id, cached and sent with every request
    - Stateless: server omits mcp-session-id, each request is independent (no header)

    Returns session ID (str) for stateful mode, None for stateless mode.
    """
    _, session_id = mcp_request("initialize", {
        "protocolVersion": MCP_VERSION,
        "capabilities": {},
        "clientInfo": {"name": CLIENT_NAME, "version": "1.0"}
    })

    if not session_id:
        # Stateless mode: server doesn't maintain sessions
        print("Server running in stateless mode (no session ID)", file=sys.stderr)
        save_session({"stateless": True})
    else:
        save_session({"session_id": session_id})

    # MCP spec: always send initialized notification after initialize response
    mcp_request("notifications/initialized", session_id=session_id)
    return session_id


def get_session_id() -> str | None:
    """Get current session ID, initializing if needed.

    Returns session ID for stateful servers, None for stateless servers.
    """
    session = load_session()
    if session:
        # Check for explicit stateless sentinel
        if session.get("stateless"):
            return None
        sid = session.get("session_id")
        if sid:
            return sid
    return initialize_session()


# ============================================================================
# Tool Calling
# ============================================================================


def list_tools():
    """List available MCP tools."""
    session_id = get_session_id()
    result, _ = mcp_request("tools/list", session_id=session_id)
    return result.get("tools", []) if result else []


# ============================================================================
# Tool Calling — public API
# ============================================================================


def call_tool(tool_name: str, arguments: dict = None):  # type: ignore[assignment]
    """Call an MCP tool. Returns the parsed result dict.

    Parses content[0].text as JSON; on JSONDecodeError returns {"text": <raw>}.
    On isError, returns the parsed error dict (caller should check isError field).
    """
    session_id = get_session_id()

    params: dict = {"name": tool_name}
    if arguments is not None:
        params["arguments"] = arguments

    result, _ = mcp_request("tools/call", params, session_id=session_id)

    if result is None:
        raise RuntimeError("Tool call returned no result")

    # Extract content
    content = result.get("content", [])
    if content and isinstance(content[0], dict):
        text = content[0].get("text", "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}

    return result


MESSAGE_PREFIX = "[message] "


def stream_call(tool_name: str, tool_args: dict = None,  # type: ignore[assignment]
                progress_token: str = None, timeout: int = None,  # type: ignore[assignment]
                progress_file=None):
    """Streaming tools/call that COLLECTS intermediate notifications.

    Unlike call_tool (final result only), this returns every
    notifications/progress event alongside the final result:

        notifications, final = stream_call(
            "training.course.edit_ai_customer_chat",
            {"courseId": 123, "message": "确认，开始生成", "stream": True})

    Notification messages follow two shapes:
      - startswith("[message] ") → AI-speech delta (lossy live preview;
        the authoritative text is final structuredContent.response)
      - anything else            → stage title (e.g., "自动测试 5%")

    Args:
        tool_name: MCP tool name
        tool_args: tool arguments dict (default {})
        progress_token: explicit progressToken string (default auto-generated)
        timeout: seconds (default REQUEST_TIMEOUT)
        progress_file: file object for progress display (default sys.stderr).
            Pass sys.stdout so agents (Bash tool) can capture progress inline.

    Returns:
        (notifications, final):
          notifications: [{"ts", "progressToken", "progress", "message"}]
          final: parsed final result dict (same shape as call_tool's return)
    """
    if tool_args is None:
        tool_args = {}

    saved_timeout = globals()["REQUEST_TIMEOUT"]
    if timeout is not None:
        globals()["REQUEST_TIMEOUT"] = timeout

    notifications = []

    try:
        session_id = get_session_id()

        request_id = int(time.time() * 1000) % 1000000
        params = {
            "name": tool_name,
            "arguments": tool_args,
            "_meta": {"progressToken": progress_token or f"ntf-{request_id}"},
        }

        result, _ = mcp_request(
            "tools/call", params, session_id=session_id,
            progress_token=False,  # we injected _meta ourselves
            notifications_out=notifications,
            progress_file=progress_file)
    finally:
        globals()["REQUEST_TIMEOUT"] = saved_timeout

    if result is None:
        return notifications, {}

    content = result.get("content", []) if isinstance(result, dict) else []
    parsed = result
    if content:
        for item in content:
            if item.get("type") == "text":
                try:
                    parsed = json.loads(item["text"])
                    break
                except json.JSONDecodeError:
                    parsed = {"text": item["text"]}
    return notifications, parsed


def _parse_json_args(json_str=None) -> dict:
    """Parse tool arguments from JSON string, stdin (-), or key=value pairs."""
    if json_str is None:
        return {}

    # JSON string
    json_str = json_str.strip()
    if json_str == "-":
        json_str = sys.stdin.read().strip()

    # Try JSON first
    if json_str.startswith("{") or json_str.startswith("["):
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            sys.exit(f"Invalid JSON arguments: {e}")

    # Try key=value,key2=value2
    if "=" in json_str:
        result = {}
        for pair in json_str.split(","):
            key, _, value = pair.partition("=")
            key = key.strip()
            value = value.strip()
            # Try to convert to int/float
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass  # Keep as string
            result[key] = value
        if result:
            return result

    sys.exit(f"Invalid arguments: expected JSON, stdin (-), or key=value pairs. Got: {json_str[:100]}")


# ============================================================================
# Catalog Management
# ============================================================================


def registry_get():
    """Get current tool catalog from registry."""
    return call_tool("admin.registry_get", {})


def registry_publish(catalog, expected_version):
    """Publish updated tool catalog."""
    return call_tool("admin.registry_publish", {
        "catalog": catalog,
        "expectedVersion": expected_version
    })


# ============================================================================
# CLI Commands
# ============================================================================


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

    # Start OAuth flow
    port = args.port or DEFAULT_CALLBACK_PORT
    try:
        port, port_changed = _find_available_port(port)
        if port_changed:
            print(f"Port {args.port} in use, using {port} instead", file=sys.stderr)
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Register client if needed
    client = load_client()
    if not client:
        print("Registering new client...", file=sys.stderr)
        client = register_client(port)
    else:
        # Update callback URI if port changed
        client["_callback_port"] = port
        client["_callback_uri"] = f"http://127.0.0.1:{port}/callback"
        save_client(client)

    # Generate PKCE
    code_verifier, code_challenge = generate_pkce()
    state = secrets.token_urlsafe(16)

    # Save code_verifier for later use in token exchange
    if client:
        client["_code_verifier"] = code_verifier
        save_client(client)

    # Build authorize URL
    auth_url = build_authorize_url(
        client["client_id"],
        code_challenge,
        state,
        client["_callback_uri"]
    )

    print(f"\nOpening browser for authorization...", file=sys.stderr)
    print(f"If browser doesn't open, visit:\n{auth_url}\n", file=sys.stderr)

    # 使用共享状态捕获授权码
    auth_result: dict[str, str | None] = {"code": None, "error": None}

    def callback_wrapper() -> None:
        try:
            code = start_callback_server(port, state)
            auth_result["code"] = code
        except Exception as e:
            auth_result["error"] = str(e)

    # Start callback server
    server_thread = threading.Thread(target=callback_wrapper, daemon=True)
    server_thread.start()

    # Open browser
    webbrowser.open(auth_url)

    # Wait for callback
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
    print("✓ Authorization code received", file=sys.stderr)
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


def cmd_tools():
    """Handle tools command."""
    tools = list_tools()
    for tool in tools:
        print(f"- {tool['name']}: {tool.get('description', 'No description')}")


def cmd_registry_get():
    """Handle registry_get command."""
    result = registry_get()
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_registry_publish(args):
    """Handle registry_publish command."""
    catalog = json.loads(args.catalog)
    expected_version = args.expected_version
    result = registry_publish(catalog, expected_version)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_call(args):
    """Call an MCP tool (non-streaming, with optional progress display)."""
    tool_name = args.tool
    tool_args = _parse_json_args(args.json_args)

    progress_file = sys.stdout if getattr(args, "progress_stdout", False) else sys.stderr
    print(f"Calling {tool_name}...", file=sys.stderr)

    session_id = get_session_id()
    result, _ = mcp_request(
        "tools/call",
        {"name": tool_name, "arguments": tool_args},
        session_id=session_id,
        progress_file=progress_file)

    if result is None:
        print("No result returned.", file=sys.stderr)
        return

    content = result.get("content", [])
    if content:
        for item in content:
            if item.get("type") == "text":
                print(item["text"])
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    # Business errors arrive as isError: true — surface via exit code
    if result.get("isError"):
        sys.exit(1)


def cmd_stream(args):
    """Streaming call with notification capture."""
    tool_name = args.tool
    tool_args = _parse_json_args(args.json_args)

    progress_file = sys.stdout if getattr(args, "progress_stdout", False) else sys.stderr
    print(f"Streaming {tool_name}...", file=sys.stderr)
    notifications, final = stream_call(
        tool_name, tool_args, timeout=args.timeout, progress_file=progress_file)

    summary = {
        "tool": tool_name,
        "notifications": len(notifications),
        "message_deltas": sum(
            1 for n in notifications
            if isinstance(n.get("message"), str)
            and n["message"].startswith(MESSAGE_PREFIX)),
        "first_notification_ts": notifications[0]["ts"] if notifications else None,
    }
    print(f"\n=== SUMMARY ===", file=sys.stderr)
    print(json.dumps(summary, ensure_ascii=False, indent=2), file=sys.stderr)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            for n in notifications:
                f.write(json.dumps(n, ensure_ascii=False) + "\n")
        print(f"notifications jsonl: {args.out}", file=sys.stderr)
    print(json.dumps(final, ensure_ascii=False, indent=2))


def main():
    global _override_mcp_url

    parser = argparse.ArgumentParser(description="MCP Client for Enterprise Training")
    parser.add_argument("--mcp-url", help="Override MCP server URL (overrides mcp.json)")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # auth command
    auth_parser = subparsers.add_parser("auth", help="OAuth authentication")
    auth_parser.add_argument("--status", action="store_true", help="Show auth status")
    auth_parser.add_argument("--port", type=int, help="Callback port")

    # call command — non-streaming tool call with progress display
    call_parser = subparsers.add_parser("call", help="Call an MCP tool")
    call_parser.add_argument("tool", help="Tool name (e.g., training.course.create_ai_customer)")
    call_parser.add_argument("json_args", nargs="?", default=None,
                             help="Tool arguments: JSON string, '-' for stdin, or key=value pairs")
    call_parser.add_argument("--progress-stdout", action="store_true", default=False,
                             help="Print progress to stdout (for agents/Bash tool) instead of stderr")

    # stream command — streaming call with notification capture
    stream_parser = subparsers.add_parser(
        "stream", help="Streaming call with notifications/progress capture")
    stream_parser.add_argument("tool", help="Tool name")
    stream_parser.add_argument("json_args", nargs="?", default=None,
                               help="Tool arguments: JSON string, '-' for stdin, or key=value pairs")
    stream_parser.add_argument("--timeout", type=int, default=None,
                               help=f"Seconds (default: {REQUEST_TIMEOUT})")
    stream_parser.add_argument("--out", default=None,
                               help="Write notifications as JSONL to this path")
    stream_parser.add_argument("--progress-stdout", action="store_true", default=False,
                               help="Print progress to stdout (for agents/Bash tool) instead of stderr")

    # tools command
    subparsers.add_parser("tools", help="List available tools")

    # registry_get command
    subparsers.add_parser("registry_get", help="Get tool catalog")

    # registry_publish command
    publish_parser = subparsers.add_parser("registry_publish", help="Publish tool catalog")
    publish_parser.add_argument("catalog", help="Catalog JSON")
    publish_parser.add_argument("expected_version", type=int, help="Expected version")

    args = parser.parse_args()

    # 设置 URL 覆盖（在首次 URL 解析前）
    if args.mcp_url:
        _override_mcp_url = args.mcp_url

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "auth":
            cmd_auth(args)
        elif args.command == "call":
            cmd_call(args)
        elif args.command == "stream":
            cmd_stream(args)
        elif args.command == "tools":
            cmd_tools()
        elif args.command == "registry_get":
            cmd_registry_get()
        elif args.command == "registry_publish":
            cmd_registry_publish(args)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
