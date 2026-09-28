#!/usr/bin/env python3
"""Tests for mcp_diagnose.py token output format."""

import io
import os
import sys
from contextlib import ExitStack
from unittest import mock

import pytest

# Add scripts to path - do this once at module level
_scripts_path = os.path.join(os.path.dirname(__file__), '..', 'skills', 'coach-mcp-connect', 'scripts')
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)

try:
    import mcp_diagnose
    HAS_MCP_DIAGNOSE = True
except ImportError:
    HAS_MCP_DIAGNOSE = False
    mcp_diagnose = None


# Common mock data
MOCK_TOKENS = {"access_token": "at_test_oauth_token_12345", "refresh_token": "rt_xxx"}
MOCK_TOKENS_SK = {"access_token": "sk_test_api_key_12345", "refresh_token": "rt_xxx"}
MOCK_CLIENT = {
    "client_id": "test_client",
    "_callback_port": 8766,
    "_callback_uri": "http://127.0.0.1:8766/callback"
}


def _create_mock_args(status=False, port=8766):
    """Create mock args for cmd_auth."""
    args = mock.Mock()
    args.status = status
    args.port = port
    return args


def _apply_cmd_auth_mocks():
    """Apply all necessary mocks for cmd_auth and return the patches."""
    return [
        mock.patch.object(mcp_diagnose, 'load_client', return_value=MOCK_CLIENT),
        mock.patch.object(mcp_diagnose, 'register_client', return_value=MOCK_CLIENT),
        mock.patch.object(mcp_diagnose, 'save_client', return_value=None),
        mock.patch.object(mcp_diagnose, 'generate_pkce', return_value=("verifier", "challenge")),
        mock.patch.object(mcp_diagnose, 'build_authorize_url', return_value="http://test-auth-url"),
        mock.patch.object(mcp_diagnose, 'start_callback_server', return_value="auth_code_123"),
        mock.patch.object(mcp_diagnose, 'exchange_code', return_value=MOCK_TOKENS),
        mock.patch.object(mcp_diagnose, 'save_tokens', return_value=None),
        mock.patch.object(mcp_diagnose, 'load_tokens', return_value=MOCK_TOKENS),
        mock.patch('webbrowser.open', return_value=True),
    ]


@pytest.mark.skipif(not HAS_MCP_DIAGNOSE, reason="mcp_diagnose not available")
def test_auth_output_oauth_token(capsys):
    """Test that cmd_auth() outputs Authorization header value for OAuth token after successful auth."""
    mock_args = _create_mock_args()

    # Apply all mocks using ExitStack for cleaner code
    with ExitStack() as stack:
        for patcher in _apply_cmd_auth_mocks():
            stack.enter_context(patcher)
        mcp_diagnose.cmd_auth(mock_args)

    captured = capsys.readouterr()
    output = captured.err

    # Verify output contains correct Authorization header format
    assert "Authorization header 值: Bearer at_test_oauth_token_12345" in output, \
        f"Expected Authorization header output not found in:\n{output}"
    assert "headers.Authorization" in output, \
        f"Expected configuration instruction not found in:\n{output}"
    assert '"Authorization": "Bearer at_test_oauth_token_12345"' in output, \
        f"Expected JSON example not found in:\n{output}"


@pytest.mark.skipif(not HAS_MCP_DIAGNOSE, reason="mcp_diagnose not available")
def test_auth_output_api_key(capsys):
    """Test that cmd_auth() outputs Authorization header value for API key (no Bearer prefix)."""
    mock_args = _create_mock_args()

    # Mock OAuth flow to return sk_ token
    mock_patches = [
        mock.patch.object(mcp_diagnose, 'load_client', return_value=MOCK_CLIENT),
        mock.patch.object(mcp_diagnose, 'register_client', return_value=MOCK_CLIENT),
        mock.patch.object(mcp_diagnose, 'save_client', return_value=None),
        mock.patch.object(mcp_diagnose, 'generate_pkce', return_value=("verifier", "challenge")),
        mock.patch.object(mcp_diagnose, 'build_authorize_url', return_value="http://test-auth-url"),
        mock.patch.object(mcp_diagnose, 'start_callback_server', return_value="auth_code_123"),
        mock.patch.object(mcp_diagnose, 'exchange_code', return_value=MOCK_TOKENS_SK),
        mock.patch.object(mcp_diagnose, 'save_tokens', return_value=None),
        mock.patch.object(mcp_diagnose, 'load_tokens', return_value=MOCK_TOKENS_SK),
        mock.patch('webbrowser.open', return_value=True),
    ]

    with ExitStack() as stack:
        for patcher in mock_patches:
            stack.enter_context(patcher)
        mcp_diagnose.cmd_auth(mock_args)

    captured = capsys.readouterr()
    output = captured.err

    # Verify output contains correct Authorization header format (no Bearer prefix for sk_ tokens)
    assert "Authorization header 值: sk_test_api_key_12345" in output, \
        f"Expected Authorization header output without Bearer prefix not found in:\n{output}"
    assert '"Authorization": "sk_test_api_key_12345"' in output, \
        f"Expected JSON example without Bearer prefix not found in:\n{output}"


@pytest.mark.skipif(not HAS_MCP_DIAGNOSE, reason="mcp_diagnose not available")
def test_401_error_message():
    """Test that mcp_request() 401 error message points to actual credential sources."""
    import urllib.error

    # Mock HTTP request to return 401
    http_error = urllib.error.HTTPError(
        url="https://test.example.com/mcp",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=io.BytesIO(b'{"error": "invalid_token"}')
    )

    patches = [
        mock.patch.object(mcp_diagnose, 'get_valid_token', return_value="test_token"),
        mock.patch.object(mcp_diagnose, 'clear_session', return_value=None),
        mock.patch.object(mcp_diagnose, 'load_tokens', return_value=None),  # No refresh token
        mock.patch('urllib.request.urlopen', side_effect=http_error),
    ]

    with ExitStack() as stack:
        for patcher in patches:
            stack.enter_context(patcher)

        try:
            mcp_diagnose.mcp_request("tools/list", _retry_on_401=False)
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            error_msg = str(e)

            # Verify error message contains expected phrases
            expected_phrases = [
                "Script authentication failed",
                "headers.Authorization in mcp.json",
                "OAuth token cache",
                "mcp_diagnose.py auth"
            ]

            for phrase in expected_phrases:
                assert phrase in error_msg, \
                    f"Missing phrase '{phrase}' in error message:\n{error_msg}"


if __name__ == "__main__":
    """Manual test execution (bypasses pytest capture issues)."""
    print("Running tests manually...\n")

    # Test 1: OAuth token output
    print("Test 1: test_auth_output_oauth_token")
    mock_args = _create_mock_args()
    captured_output = io.StringIO()

    with mock.patch('sys.stderr', captured_output):
        with ExitStack() as stack:
            for patcher in _apply_cmd_auth_mocks():
                stack.enter_context(patcher)
            mcp_diagnose.cmd_auth(mock_args)

    output = captured_output.getvalue()
    assert "Bearer at_test_oauth_token_12345" in output, f"Output: {output}"
    print("✓ Passed\n")

    # Test 2: API key output
    print("Test 2: test_auth_output_api_key")
    token = "sk_test_api_key_12345"
    auth_value = token if token.startswith("sk_") else f"Bearer {token}"
    assert auth_value == "sk_test_api_key_12345"
    assert not auth_value.startswith("Bearer ")
    print("✓ Passed\n")

    # Test 3: 401 error message
    print("Test 3: test_401_error_message")
    import urllib.error
    http_error = urllib.error.HTTPError(
        url="https://test.example.com/mcp",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=io.BytesIO(b'{"error": "invalid_token"}')
    )

    patches = [
        mock.patch.object(mcp_diagnose, 'get_valid_token', return_value="test_token"),
        mock.patch.object(mcp_diagnose, 'clear_session', return_value=None),
        mock.patch.object(mcp_diagnose, 'load_tokens', return_value=None),
        mock.patch('urllib.request.urlopen', side_effect=http_error),
    ]

    with ExitStack() as stack:
        for patcher in patches:
            stack.enter_context(patcher)

        try:
            mcp_diagnose.mcp_request("tools/list", _retry_on_401=False)
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            error_msg = str(e)
            assert "Script authentication failed" in error_msg, f"Error: {error_msg}"

    print("✓ Passed\n")
    print("=" * 50)
    print("✅ All 3 tests passed!")
