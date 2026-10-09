"""Universal target 测试（TDD RED phase）。"""
import json
import zipfile
from pathlib import Path

import pytest


class TestUniversalTarget:
    """测试 universal target 的构建逻辑。"""

    @pytest.fixture
    def bundle_repo(self, tmp_path):
        """创建包含一个 bundle 的最小仓库。"""
        # skills
        skills_dir = tmp_path / "skills" / "test-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: Test Skill\ndescription: A test skill\n---\n# Test\nBody content"
        )

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

        # environments.json
        envs = {"test": {"MCP_URL": "https://mcp.example.com/mcp"}}
        (tmp_path / "environments.json").write_text(json.dumps(envs))

        return tmp_path

    def test_universal_target_produces_zip(self, bundle_repo):
        """universal target 应该生成 ZIP 文件。"""
        import subprocess
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        pack = ["python3", str(scripts / "pack.py")]

        result = subprocess.run(
            pack + ["--bundle", "test-bundle", "--target", "universal"],
            cwd=bundle_repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

        zip_path = bundle_repo / "dist" / "universal" / "test-bundle-v1.0.0-test.zip"
        assert zip_path.is_file()

    def test_universal_zip_contains_readme(self, bundle_repo):
        """universal ZIP 应该包含 README.md。"""
        import subprocess
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        pack = ["python3", str(scripts / "pack.py")]

        subprocess.run(
            pack + ["--bundle", "test-bundle", "--target", "universal"],
            cwd=bundle_repo,
            capture_output=True,
            check=True,
        )

        zip_path = bundle_repo / "dist" / "universal" / "test-bundle-v1.0.0-test.zip"
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "README.md" in names

    def test_universal_zip_contains_mcp_json(self, bundle_repo):
        """universal ZIP 应该包含 mcp.json（复用 workbuddy 逻辑）。"""
        import subprocess
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        pack = ["python3", str(scripts / "pack.py")]

        subprocess.run(
            pack + ["--bundle", "test-bundle", "--target", "universal"],
            cwd=bundle_repo,
            capture_output=True,
            check=True,
        )

        zip_path = bundle_repo / "dist" / "universal" / "test-bundle-v1.0.0-test.zip"
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "mcp.json" in names

            mcp = json.loads(zf.read("mcp.json"))
            assert "mcpServers" in mcp
            assert "test-server" in mcp["mcpServers"]

    def test_universal_zip_contains_skills(self, bundle_repo):
        """universal ZIP 应该包含 skills 目录。"""
        import subprocess
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        pack = ["python3", str(scripts / "pack.py")]

        subprocess.run(
            pack + ["--bundle", "test-bundle", "--target", "universal"],
            cwd=bundle_repo,
            capture_output=True,
            check=True,
        )

        zip_path = bundle_repo / "dist" / "universal" / "test-bundle-v1.0.0-test.zip"
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert any("skills/test-skill/SKILL.md" in n for n in names)

    def test_universal_zip_excludes_workbuddy_files(self, bundle_repo):
        """universal ZIP 不应该包含 workbuddy 专有文件。"""
        import subprocess
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        pack = ["python3", str(scripts / "pack.py")]

        subprocess.run(
            pack + ["--bundle", "test-bundle", "--target", "universal"],
            cwd=bundle_repo,
            capture_output=True,
            check=True,
        )

        zip_path = bundle_repo / "dist" / "universal" / "test-bundle-v1.0.0-test.zip"
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "connector-meta.json" not in names
            assert "auth-profile.json" not in names
            assert "icon.svg" not in names

    def test_universal_readme_contains_bundle_name(self, bundle_repo):
        """README.md 应该包含 bundle 名称。"""
        import subprocess
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        pack = ["python3", str(scripts / "pack.py")]

        subprocess.run(
            pack + ["--bundle", "test-bundle", "--target", "universal"],
            cwd=bundle_repo,
            capture_output=True,
            check=True,
        )

        zip_path = bundle_repo / "dist" / "universal" / "test-bundle-v1.0.0-test.zip"
        with zipfile.ZipFile(zip_path) as zf:
            readme = zf.read("README.md").decode("utf-8")
            assert "Test Bundle" in readme

    def test_universal_readme_contains_skills_list(self, bundle_repo):
        """README.md 应该包含技能列表。"""
        import subprocess
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        pack = ["python3", str(scripts / "pack.py")]

        subprocess.run(
            pack + ["--bundle", "test-bundle", "--target", "universal"],
            cwd=bundle_repo,
            capture_output=True,
            check=True,
        )

        zip_path = bundle_repo / "dist" / "universal" / "test-bundle-v1.0.0-test.zip"
        with zipfile.ZipFile(zip_path) as zf:
            readme = zf.read("README.md").decode("utf-8")
            assert "test-skill" in readme or "Test Skill" in readme


class TestUniversalDefaultOutput:
    """测试 universal target 的默认输出目录。"""

    @pytest.fixture
    def bundle_repo(self, tmp_path):
        """创建最小仓库。"""
        skills_dir = tmp_path / "skills" / "test-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\nname: test\ndescription: test\n---\nbody")

        bundle_dir = tmp_path / "bundles" / "test-bundle"
        bundle_dir.mkdir(parents=True)

        bundle_data = {
            "schemaVersion": 1,
            "id": "test-bundle",
            "version": "1.0.0",
            "skills": ["test-skill"],
            "presentation": {
                "defaultLocale": "zh-CN",
                "locales": {"zh-CN": {"name": "Test", "description": "Test"}},
                "icon": "icon.svg",
            },
            "mcp": {"servers": {"srv": {"transport": "streamable-http", "url": "https://example.com"}}},
            "targets": {"workbuddy": {"source": "test", "type": "mcp", "minVersion": "4.24.0"}},
        }
        (bundle_dir / "bundle.json").write_text(json.dumps(bundle_data))
        (bundle_dir / "icon.svg").write_text("<svg></svg>")
        (tmp_path / "environments.json").write_text(json.dumps({"test": {}}))

        return tmp_path

    def test_default_output_is_dist_universal(self, bundle_repo):
        """不指定 --out 时，universal target 应该输出到 dist/universal。"""
        import subprocess
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        pack = ["python3", str(scripts / "pack.py")]

        subprocess.run(
            pack + ["--bundle", "test-bundle", "--target", "universal"],
            cwd=bundle_repo,
            capture_output=True,
            check=True,
        )

        assert (bundle_repo / "dist" / "universal").is_dir()
        assert (bundle_repo / "dist" / "universal" / "test-bundle-v1.0.0-test.zip").is_file()


class TestWorkbuddyStillWorks:
    """回归测试：确保 workbuddy target 不受影响。"""

    @pytest.fixture
    def bundle_repo(self, tmp_path):
        """创建最小仓库。"""
        skills_dir = tmp_path / "skills" / "test-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\nname: test\ndescription: test\n---\nbody")

        bundle_dir = tmp_path / "bundles" / "test-bundle"
        bundle_dir.mkdir(parents=True)

        bundle_data = {
            "schemaVersion": 1,
            "id": "test-bundle",
            "version": "1.0.0",
            "skills": ["test-skill"],
            "presentation": {
                "defaultLocale": "zh-CN",
                "locales": {"zh-CN": {"name": "Test", "description": "Test"}},
                "icon": "icon.svg",
            },
            "mcp": {"servers": {"srv": {"transport": "streamable-http", "url": "https://example.com"}}},
            "targets": {"workbuddy": {"source": "test", "type": "mcp", "minVersion": "4.24.0"}},
        }
        (bundle_dir / "bundle.json").write_text(json.dumps(bundle_data))
        (bundle_dir / "icon.svg").write_text("<svg></svg>")
        (tmp_path / "environments.json").write_text(json.dumps({"test": {}}))

        return tmp_path

    def test_workbuddy_target_still_works(self, bundle_repo):
        """workbuddy target 应该继续正常工作。"""
        import subprocess
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        pack = ["python3", str(scripts / "pack.py")]

        result = subprocess.run(
            pack + ["--bundle", "test-bundle", "--target", "workbuddy"],
            cwd=bundle_repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

        zip_path = bundle_repo / "dist" / "workbuddy" / "test-bundle-v1.0.0-test.zip"
        assert zip_path.is_file()

        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "connector-meta.json" in names
            assert "mcp.json" in names
            assert "icon.svg" in names
