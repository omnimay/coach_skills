"""test_bundle.py — bundle.py 测试（RFC-0003 §7）。"""
import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from bundle_builder.bundle import load_bundle, validate_bundle, validate_bundle_icon, resolve_skills, parse_semver, compare_versions, load_environments, resolve_placeholders


@pytest.fixture
def bundle_dir(tmp_path):
    """创建最小有效 bundle。"""
    skills_dir = tmp_path / "skills" / "test-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("---\nname: test\ndescription: test\n---\nbody")

    bp = tmp_path / "bundles" / "test-bundle"
    bp.mkdir(parents=True)
    (bp / "icon.svg").write_text("<svg></svg>")
    return tmp_path


def _write_bundle(tmp_path, data):
    bp = tmp_path / "bundles" / "test-bundle"
    (bp / "bundle.json").write_text(json.dumps(data, ensure_ascii=False))
    return bp


def _valid_bundle():
    return {
        "schemaVersion": 1,
        "id": "test-bundle",
        "version": "1.0.0",
        "skills": ["test-skill"],
        "presentation": {
            "defaultLocale": "zh-CN",
            "locales": {
                "zh-CN": {"name": "Test", "description": "Test desc", "examples": ["ex1"]},
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


class TestSemver:
    def test_valid_basic(self):
        assert parse_semver("1.0.0") == (1, 0, 0, (), ())
        assert parse_semver("0.1.0") == (0, 1, 0, (), ())
        assert parse_semver("10.20.30") == (10, 20, 30, (), ())

    def test_valid_prerelease(self):
        v = parse_semver("1.0.0-rc.1")
        assert v.major == 1 and v.minor == 0 and v.patch == 0
        assert v.prerelease == ("rc", 1)

    def test_valid_build_metadata(self):
        v = parse_semver("1.0.0+build.123")
        assert v.build == ("build", "123")
        v2 = parse_semver("1.0.0-rc.1+build.456")
        assert v2.prerelease == ("rc", 1) and v2.build == ("build", "456")

    def test_invalid(self):
        import pytest
        with pytest.raises(ValueError):
            parse_semver("abc")
        with pytest.raises(ValueError):
            parse_semver("1.0")
        with pytest.raises(ValueError):
            parse_semver("")
        with pytest.raises(ValueError):
            parse_semver("1.0.0-")  # 空 prerelease
        with pytest.raises(ValueError):
            parse_semver("1.0.0+")  # 空 build
        with pytest.raises(ValueError):
            parse_semver("01.0.0")  # 前导零


class TestCompareVersions:
    def test_equal(self):
        assert compare_versions("1.0.0", "1.0.0") == 0

    def test_major(self):
        assert compare_versions("2.0.0", "1.0.0") == 1
        assert compare_versions("1.0.0", "2.0.0") == -1

    def test_minor(self):
        assert compare_versions("1.2.0", "1.1.0") == 1
        assert compare_versions("1.1.0", "1.2.0") == -1

    def test_patch(self):
        assert compare_versions("1.0.2", "1.0.1") == 1

    def test_prerelease_less_than_release(self):
        assert compare_versions("1.0.0", "1.0.0-rc.1") == 1
        assert compare_versions("1.0.0-rc.1", "1.0.0") == -1

    def test_prerelease_comparison(self):
        assert compare_versions("1.0.0-rc.2", "1.0.0-rc.1") == 1
        assert compare_versions("1.0.0-alpha", "1.0.0-beta") == -1

    def test_build_ignored(self):
        """build 元数据不参与版本比较"""
        assert compare_versions("1.0.0+build.1", "1.0.0+build.2") == 0


class TestLoadBundle:
    def test_load_valid(self, bundle_dir):
        bp = _write_bundle(bundle_dir, _valid_bundle())
        bundle = load_bundle(bp)
        assert bundle["id"] == "test-bundle"
        assert bundle["version"] == "1.0.0"

    def test_load_missing(self, tmp_path):
        with pytest.raises(SystemExit):
            load_bundle(tmp_path / "bundles" / "nonexistent")


class TestValidateBundle:
    def test_valid(self, bundle_dir):
        bp = _write_bundle(bundle_dir, _valid_bundle())
        bundle = load_bundle(bp)
        validate_bundle(bundle)

    def test_missing_version(self, bundle_dir):
        data = _valid_bundle()
        del data["version"]
        bp = _write_bundle(bundle_dir, data)
        bundle = load_bundle(bp)
        with pytest.raises(SystemExit, match="version"):
            validate_bundle(bundle)

    def test_invalid_semver(self, bundle_dir):
        data = _valid_bundle()
        data["version"] = "abc"
        bp = _write_bundle(bundle_dir, data)
        bundle = load_bundle(bp)
        with pytest.raises(SystemExit, match="(?i)semver"):
            validate_bundle(bundle)

    def test_missing_default_locale_entry(self, bundle_dir):
        data = _valid_bundle()
        data["presentation"]["defaultLocale"] = "fr"
        bp = _write_bundle(bundle_dir, data)
        bundle = load_bundle(bp)
        with pytest.raises(SystemExit, match="defaultLocale"):
            validate_bundle(bundle)

    def test_invalid_id_path_traversal(self, bundle_dir):
        data = _valid_bundle()
        data["id"] = "../escaped"
        bp = _write_bundle(bundle_dir, data)
        bundle = load_bundle(bp)
        with pytest.raises(SystemExit, match="id"):
            validate_bundle(bundle)

    def test_invalid_id_absolute_path(self, bundle_dir):
        data = _valid_bundle()
        data["id"] = "/etc/passwd"
        bp = _write_bundle(bundle_dir, data)
        bundle = load_bundle(bp)
        with pytest.raises(SystemExit, match="id"):
            validate_bundle(bundle)

    def test_invalid_id_starts_with_dot(self, bundle_dir):
        data = _valid_bundle()
        data["id"] = ".hidden"
        bp = _write_bundle(bundle_dir, data)
        bundle = load_bundle(bp)
        with pytest.raises(SystemExit, match="id"):
            validate_bundle(bundle)

    def test_valid_id_with_hyphens(self, bundle_dir):
        data = _valid_bundle()
        data["id"] = "my-bundle.v2"
        bp = _write_bundle(bundle_dir, data)
        bundle = load_bundle(bp)
        validate_bundle(bundle)  # 合法 ID 不报错


class TestValidateBundleIcon:
    def test_valid(self, bundle_dir):
        bp = _write_bundle(bundle_dir, _valid_bundle())
        bundle = load_bundle(bp)
        validate_bundle_icon(bundle, bp)

    def test_missing_icon(self, bundle_dir):
        bp = _write_bundle(bundle_dir, _valid_bundle())
        (bp / "icon.svg").unlink()
        bundle = load_bundle(bp)
        with pytest.raises(SystemExit, match="icon"):
            validate_bundle_icon(bundle, bp)


class TestResolveSkills:
    def test_valid(self, bundle_dir):
        bp = _write_bundle(bundle_dir, _valid_bundle())
        bundle = load_bundle(bp)
        skills_dir = bundle_dir / "skills"
        files = resolve_skills(bundle, skills_dir)
        assert "test-skill" in files

    def test_missing_skill_dir(self, bundle_dir):
        data = _valid_bundle()
        data["skills"] = ["nonexistent"]
        bp = _write_bundle(bundle_dir, data)
        bundle = load_bundle(bp)
        skills_dir = bundle_dir / "skills"
        with pytest.raises(SystemExit, match="nonexistent"):
            resolve_skills(bundle, skills_dir)


class TestLoadEnvironments:
    def test_valid(self, tmp_path):
        env_file = tmp_path / "environments.json"
        env_file.write_text(json.dumps({
            "test": {"MCP_URL": "https://test.example.com/mcp"},
            "prod": {"MCP_URL": "https://prod.example.com/mcp"},
        }))
        envs = load_environments(env_file)
        assert envs["test"]["MCP_URL"] == "https://test.example.com/mcp"
        assert envs["prod"]["MCP_URL"] == "https://prod.example.com/mcp"

    def test_missing_file(self, tmp_path):
        with pytest.raises(SystemExit):
            load_environments(tmp_path / "nonexistent.json")


class TestResolvePlaceholders:
    def test_basic(self):
        bundle = {"mcp": {"servers": {"s1": {"url": "${MCP_URL}"}}}}
        resolved = resolve_placeholders(bundle, {"MCP_URL": "https://example.com/mcp"})
        assert resolved["mcp"]["servers"]["s1"]["url"] == "https://example.com/mcp"

    def test_nested(self):
        bundle = {"a": {"b": {"c": "${VAR}"}}}
        resolved = resolve_placeholders(bundle, {"VAR": "value"})
        assert resolved["a"]["b"]["c"] == "value"

    def test_list(self):
        bundle = {"items": ["${A}", "${B}"]}
        resolved = resolve_placeholders(bundle, {"A": "x", "B": "y"})
        assert resolved["items"] == ["x", "y"]

    def test_missing_var(self):
        bundle = {"url": "${MISSING}"}
        with pytest.raises(SystemExit, match="MISSING"):
            resolve_placeholders(bundle, {"OTHER": "val"})

    def test_no_placeholders(self):
        bundle = {"url": "https://static.com"}
        resolved = resolve_placeholders(bundle, {"MCP_URL": "val"})
        assert resolved["url"] == "https://static.com"
