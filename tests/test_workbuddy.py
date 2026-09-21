"""test_workbuddy.py — workbuddy.py 测试（RFC-0003 §7）。"""
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from bundle_builder.workbuddy import generate_connector_meta, generate_mcp_json, validate_workbuddy, _locale_field


def _valid_bundle(**overrides):
    data = {
        "schemaVersion": 1,
        "id": "test-bundle",
        "version": "1.0.0",
        "skills": ["test-skill"],
        "presentation": {
            "defaultLocale": "zh-CN",
            "locales": {
                "zh-CN": {"name": "测试包", "description": "测试描述", "examples": ["示例1"]},
                "en": {"name": "Test Bundle", "description": "Test desc", "examples": ["Ex1"]},
            },
            "icon": "icon.svg",
        },
        "mcp": {
            "servers": {
                "test-server": {"transport": "streamable-http", "url": "https://mcp.example.com/mcp"},
            },
        },
        "targets": {"workbuddy": {"source": "test-bundle", "type": "mcp", "minVersion": "4.24.0"}},
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and k in data and isinstance(data[k], dict):
            data[k].update(v)
        else:
            data[k] = v
    return data


class TestLocaleField:
    def test_existing(self):
        assert _locale_field({"zh-CN": {"name": "中文"}}, "zh-CN", "name") == "中文"

    def test_missing_locale(self):
        assert _locale_field({"zh-CN": {"name": "中文"}}, "en", "name") is None

    def test_missing_field(self):
        assert _locale_field({"zh-CN": {}}, "zh-CN", "name") is None

    def test_empty_list(self):
        assert _locale_field({"zh-CN": {"examples": []}}, "zh-CN", "examples") == []


class TestGenerateConnectorMeta:
    def test_basic(self):
        meta = generate_connector_meta(_valid_bundle())
        assert meta["name"] == "测试包"
        assert meta["name_zh"] == "测试包"
        assert meta["name_en"] == "Test Bundle"
        assert meta["type"] == "mcp"
        assert meta["source"] == "test-bundle"
        assert meta["minWorkbuddyVersion"] == "4.24.0"
        assert meta["version"] == "1.0.0"

    def test_missing_en(self):
        bundle = _valid_bundle(presentation={
            "defaultLocale": "zh-CN",
            "locales": {"zh-CN": {"name": "中文", "description": "描述", "examples": []}},
            "icon": "icon.svg",
        })
        meta = generate_connector_meta(bundle)
        assert meta["name"] == "中文"
        assert "name_en" not in meta
        assert "description_en" not in meta

    def test_empty_examples_preserved(self):
        bundle = _valid_bundle(presentation={
            "defaultLocale": "zh-CN",
            "locales": {
                "zh-CN": {"name": "中文", "description": "描述", "examples": []},
                "en": {"name": "English", "description": "Desc", "examples": []},
            },
            "icon": "icon.svg",
        })
        meta = generate_connector_meta(bundle)
        assert meta["examples_zh"] == []
        assert meta["examples_en"] == []


class TestGenerateMcpJson:
    def test_basic(self):
        mcp = generate_mcp_json(_valid_bundle())
        s = mcp["mcpServers"]["test-server"]
        assert s["type"] == "streamableHttp"
        assert s["url"] == "https://mcp.example.com/mcp"


class TestValidateWorkbuddy:
    def test_valid(self):
        validate_workbuddy(_valid_bundle())

    def test_placeholder_url(self):
        bundle = _valid_bundle(mcp={"servers": {
            "s1": {"transport": "streamable-http", "url": "${MCP_URL}"},
        }})
        validate_workbuddy(bundle)  # 占位符跳过 HTTPS 检查

    def test_multiple_servers(self):
        bundle = _valid_bundle(mcp={"servers": {
            "s1": {"transport": "streamable-http", "url": "https://a.com/mcp"},
            "s2": {"transport": "streamable-http", "url": "https://b.com/mcp"},
        }})
        with pytest.raises(SystemExit, match="一个"):
            validate_workbuddy(bundle)

    def test_non_https(self):
        bundle = _valid_bundle(mcp={"servers": {
            "s1": {"transport": "streamable-http", "url": "http://a.com/mcp"},
        }})
        with pytest.raises(SystemExit, match="HTTPS"):
            validate_workbuddy(bundle)

    def test_no_servers(self):
        bundle = _valid_bundle(mcp={"servers": {}})
        with pytest.raises(SystemExit, match="为空"):
            validate_workbuddy(bundle)

    def test_missing_targets(self):
        bundle = _valid_bundle()
        del bundle["targets"]
        with pytest.raises(SystemExit, match="targets"):
            validate_workbuddy(bundle)

    def test_missing_workbuddy_target(self):
        bundle = _valid_bundle()
        del bundle["targets"]["workbuddy"]
        with pytest.raises(SystemExit, match="targets.workbuddy"):
            validate_workbuddy(bundle)

    def test_missing_source_field(self):
        bundle = _valid_bundle()
        del bundle["targets"]["workbuddy"]["source"]
        with pytest.raises(SystemExit, match="source"):
            validate_workbuddy(bundle)

    def test_missing_type_field(self):
        bundle = _valid_bundle()
        del bundle["targets"]["workbuddy"]["type"]
        with pytest.raises(SystemExit, match="type"):
            validate_workbuddy(bundle)

    def test_missing_minVersion_field(self):
        bundle = _valid_bundle()
        del bundle["targets"]["workbuddy"]["minVersion"]
        with pytest.raises(SystemExit, match="minVersion"):
            validate_workbuddy(bundle)
