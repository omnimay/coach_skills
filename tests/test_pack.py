"""pack.py 测试（RFC-0003）。"""
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PACK = ["python3", str(SCRIPTS / "pack.py")]


def run_pack(repo, *args):
    return subprocess.run(PACK + list(args), cwd=repo, capture_output=True, text=True)


@pytest.fixture
def bundle_repo(tmp_path):
    """创建包含一个 bundle 的最小仓库。"""
    # skills
    skills_dir = tmp_path / "skills" / "test-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("---\nname: test\ndescription: test\n---\nbody")
    (skills_dir / "references").mkdir()
    (skills_dir / "references" / "doc.md").write_text("# Doc")

    # bundle
    bundle_dir = tmp_path / "bundles" / "test-bundle"
    bundle_dir.mkdir(parents=True)

    bundle_data = {
        "schemaVersion": 1,
        "id": "test-bundle",
        "version": "1.0.0",
        "skills": ["test-skill"],
        "presentation": {
            "defaultLocale": "zh-CN",
            "locales": {
                "zh-CN": {
                    "name": "Test Bundle",
                    "description": "Test description",
                    "examples": ["Example 1"],
                },
            },
            "icon": "icon.svg",
        },
        "mcp": {
            "servers": {
                "test-server": {
                    "transport": "streamable-http",
                    "url": "https://mcp.example.com/mcp",
                },
            },
        },
        "targets": {
            "workbuddy": {"source": "test-bundle", "type": "mcp", "minVersion": "4.24.0"},
        },
    }
    (bundle_dir / "bundle.json").write_text(json.dumps(bundle_data, ensure_ascii=False))
    (bundle_dir / "icon.svg").write_text("<svg></svg>")

    # environments.json（pack.py 必需）
    envs = {
        "test": {"MCP_URL": "https://mcp.example.com/mcp"},
        "coach": {"MCP_URL": "https://mcp.coach.example.com/mcp"},
    }
    (tmp_path / "environments.json").write_text(json.dumps(envs))

    return tmp_path


class TestSingleBundle:
    def test_basic_packaging(self, bundle_repo):
        result = run_pack(bundle_repo, "--bundle", "test-bundle")
        assert result.returncode == 0, result.stderr
        zip_path = bundle_repo / "dist" / "workbuddy" / "test-bundle-v1.0.0-test.zip"
        assert zip_path.is_file()

    def test_zip_contents(self, bundle_repo):
        run_pack(bundle_repo, "--bundle", "test-bundle")
        zip_path = bundle_repo / "dist" / "workbuddy" / "test-bundle-v1.0.0-test.zip"
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "connector-meta.json" in names
            assert "mcp.json" in names
            assert "icon.svg" in names
            assert any("skills/test-skill/SKILL.md" in n for n in names)

    def test_connector_meta_contents(self, bundle_repo):
        run_pack(bundle_repo, "--bundle", "test-bundle")
        zip_path = bundle_repo / "dist" / "workbuddy" / "test-bundle-v1.0.0-test.zip"
        with zipfile.ZipFile(zip_path) as zf:
            meta = json.loads(zf.read("connector-meta.json"))
            assert meta["name"] == "Test Bundle"
            assert meta["type"] == "mcp"
            assert meta["source"] == "test-bundle"
            assert meta["version"] == "1.0.0"
            assert meta["minWorkbuddyVersion"] == "4.24.0"


class TestDeterministic:
    def test_sorted_entries(self, bundle_repo):
        run_pack(bundle_repo, "--bundle", "test-bundle")
        zip_path = bundle_repo / "dist" / "workbuddy" / "test-bundle-v1.0.0-test.zip"
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert names == sorted(names)

    def test_fixed_timestamp(self, bundle_repo):
        run_pack(bundle_repo, "--bundle", "test-bundle")
        zip_path = bundle_repo / "dist" / "workbuddy" / "test-bundle-v1.0.0-test.zip"
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                assert info.date_time == (1980, 1, 1, 0, 0, 0)


class TestErrorHandling:
    def test_missing_bundle(self, bundle_repo):
        result = run_pack(bundle_repo, "--bundle", "nonexistent")
        assert result.returncode != 0

    def test_custom_output(self, bundle_repo):
        result = run_pack(bundle_repo, "--bundle", "test-bundle", "--out", "custom-out")
        assert result.returncode == 0
        assert (bundle_repo / "custom-out").is_dir()


class TestPackAll:
    def test_pack_all_bundles(self, bundle_repo):
        result = run_pack(bundle_repo)
        assert result.returncode == 0, result.stderr
        zip_path = bundle_repo / "dist" / "workbuddy" / "test-bundle-v1.0.0-test.zip"
        assert zip_path.is_file()


class TestEnvResolution:
    def test_default_env(self, bundle_repo, tmp_path):
        """默认 test 环境。"""
        envs = tmp_path / "environments.json"
        envs.write_text(json.dumps({"test": {"MCP_URL": "https://test.example.com/mcp"}}))
        # 需要把 environments.json 放到仓库根
        (bundle_repo / "environments.json").write_text(envs.read_text())
        result = run_pack(bundle_repo, "--bundle", "test-bundle")
        assert result.returncode == 0, result.stderr

    def test_env_suffix_in_artifact_name(self, bundle_repo):
        """产物文件名携带环境名。"""
        (bundle_repo / "environments.json").write_text(json.dumps({
            "test": {"MCP_URL": "https://test.example.com/mcp"},
            "coach": {"MCP_URL": "https://coach.example.com/mcp"},
        }))
        run_pack(bundle_repo, "--bundle", "test-bundle", "--env", "coach")
        assert (bundle_repo / "dist" / "workbuddy" / "test-bundle-v1.0.0-coach.zip").is_file()
        assert not (bundle_repo / "dist" / "workbuddy" / "test-bundle-v1.0.0-test.zip").exists()

    def test_explicit_env(self, bundle_repo):
        """指定 coach 环境。"""
        (bundle_repo / "environments.json").write_text(json.dumps({
            "coach": {"MCP_URL": "https://coach.example.com/mcp"},
        }))
        result = run_pack(bundle_repo, "--bundle", "test-bundle", "--env", "coach")
        assert result.returncode == 0, result.stderr

    def test_unknown_env(self, bundle_repo):
        """未知环境报错。"""
        (bundle_repo / "environments.json").write_text(json.dumps({"test": {}}))
        result = run_pack(bundle_repo, "--env", "unknown")
        assert result.returncode != 0

    def test_empty_env_with_placeholders(self, bundle_repo):
        """空环境配置 + 占位符 → 应报错（不生成未解析的产物）。"""
        # 修改 bundle.json 使用占位符
        bundle_json = bundle_repo / "bundles" / "test-bundle" / "bundle.json"
        data = json.loads(bundle_json.read_text())
        data["mcp"]["servers"]["test-server"]["url"] = "${MCP_URL}"
        bundle_json.write_text(json.dumps(data))
        # 环境配置为空
        (bundle_repo / "environments.json").write_text(json.dumps({"test": {}}))
        result = run_pack(bundle_repo, "--bundle", "test-bundle", "--env", "test")
        assert result.returncode != 0
        assert "MCP_URL" in result.stderr
