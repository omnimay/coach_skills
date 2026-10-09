"""RFC-0006 测试覆盖：tag 解析 / 哈希核验 / 构建一致性 / 碰撞检测。"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from bundle_builder.build import build_bundle_zip, write_entries_zip  # pyright: ignore[reportMissingImports]
from bundle_builder.bundle import load_environments  # pyright: ignore[reportMissingImports]
from bundle_builder.gitlab_client import sha256_of  # pyright: ignore[reportMissingImports]


# ── Tag 解析 ──────────────────────────────────────────────────────────


class TestTagParsing:
    def test_valid_tag(self):
        from release_bundle import parse_tag
        bundle_id, version = parse_tag("my-bundle-v1.0.0")
        assert bundle_id == "my-bundle"
        assert version == "1.0.0"

    def test_valid_tag_with_prerelease(self):
        from release_bundle import parse_tag
        bundle_id, version = parse_tag("flashcard-v1.0.0-rc.1")
        assert bundle_id == "flashcard"
        assert version == "1.0.0-rc.1"

    def test_invalid_tag_format(self):
        from release_bundle import parse_tag
        with pytest.raises(SystemExit, match="tag 格式不合法"):
            parse_tag("not-a-valid-tag")

    def test_invalid_semver_in_tag(self):
        from release_bundle import parse_tag
        with pytest.raises(SystemExit, match="不是合法 SemVer"):
            parse_tag("bundle-v01.0.0")  # 前导零


# ── 哈希核验 ──────────────────────────────────────────────────────────


class TestHashVerification:
    def test_sha256_of_bytes(self):
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        assert sha256_of(data) == expected

    def test_sha256_consistency(self):
        """同一数据多次哈希结果一致。"""
        data = b"test data for hash"
        assert sha256_of(data) == sha256_of(data)


# ── 构建一致性（确定性构建）──────────────────────────────────────────


class TestBuildConsistency:
    @pytest.fixture
    def repo_root(self):
        return Path(__file__).resolve().parents[1]

    def test_same_input_same_hash(self, repo_root):
        """同输入 → 同哈希（RFC-0006 §5 步骤③）。"""
        envs = load_environments(repo_root / "environments.json")
        bundle_dir = repo_root / "bundles" / "flashcard"
        skills_dir = repo_root / "skills"

        entries1, name1 = build_bundle_zip(
            bundle_dir, skills_dir, "workbuddy", envs["test"], "test"
        )
        entries2, name2 = build_bundle_zip(
            bundle_dir, skills_dir, "workbuddy", envs["test"], "test"
        )

        assert name1 == name2
        # L2 修复：序列化两次构建为 ZIP 并比较实际 SHA-256
        import tempfile
        hashes = []
        for entries in [entries1, entries2]:
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                write_entries_zip(tmp_path, entries)
                hashes.append(hashlib.sha256(tmp_path.read_bytes()).hexdigest())
            finally:
                tmp_path.unlink(missing_ok=True)
        assert hashes[0] == hashes[1], f"两次构建哈希不同：{hashes[0]} vs {hashes[1]}"


# ── 碰撞检测 ──────────────────────────────────────────────────────────


class TestCollisionDetection:
    def test_no_collision_for_different_variants(self):
        """不同变体生成不同的归档文件名（zip_name 不依赖 distributionName）。"""
        from release_bundle import Coordinate
        c1 = Coordinate(
            bundle_id="test", version="1.0.0", target="workbuddy",
            variant="coach", env_vars={}
        )
        c2 = Coordinate(
            bundle_id="test", version="1.0.0", target="workbuddy",
            variant="test", env_vars={}
        )
        # zip_name 是 bundle_id + variant 组成，不依赖文件系统
        assert c1.zip_name != c2.zip_name
        assert "coach" in c1.zip_name
        assert "test" in c2.zip_name

    def test_version_regression_detected(self):
        """版本回退检测（compare_versions < 0 → 拒绝）。"""
        from bundle_builder.bundle import compare_versions
        assert compare_versions("1.0.0", "1.0.1") == -1
        assert compare_versions("1.0.0", "1.0.0") == 0
        assert compare_versions("1.0.1", "1.0.0") == 1


# ── Index.json schema ─────────────────────────────────────────────────


class TestIndexSchema:
    def test_index_schema_fields(self):
        """index.json 字段符合 RFC-0006 §3.3。"""
        index_path = Path(__file__).resolve().parents[1] / "dist" / "workbuddy" / "latest" / "index.json"
        if not index_path.is_file():
            pytest.skip("index.json 不存在（迁移未完成）")
        index = json.loads(index_path.read_text(encoding="utf-8"))
        assert index["schemaVersion"] == 1
        assert isinstance(index["items"], dict)
        for key, item in index["items"].items():
            # 必填字段
            for field in ["bundleId", "version", "target", "variant",
                          "tag", "sourceCommit", "latestFile", "archiveFile", "sha256"]:
                assert field in item, f"{key} 缺少必填字段 {field}"


# ── release_bundle.py plan 子命令 ─────────────────────────────────────


class TestReleasePlan:
    def test_plan_multi_target(self, tmp_path, monkeypatch, capsys):
        """plan 子命令输出 multi-target 坐标。"""
        from release_bundle import cmd_plan
        monkeypatch.setattr("release_bundle.BUNDLES_DIR", tmp_path / "bundles")
        monkeypatch.setattr("release_bundle.ENVS_FILE", tmp_path / "environments.json")

        bundle_dir = tmp_path / "bundles" / "test-bundle"
        bundle_dir.mkdir(parents=True)
        (bundle_dir / "bundle.json").write_text(json.dumps({
            "schemaVersion": 1, "id": "test-bundle", "version": "2.5.0",
            "skills": [], "presentation": {"defaultLocale": "zh-CN", "locales": {"zh-CN": {"name": "Test"}}},
        }))
        (bundle_dir / "release-plan.json").write_text(json.dumps({
            "version": "2.5.0",
            "targets": {"workbuddy": ["coach", "test"], "universal": ["coach"]},
        }))
        (tmp_path / "environments.json").write_text(json.dumps({
            "coach": {}, "test": {},
        }))

        coords = cmd_plan("test-bundle-v2.5.0")
        assert len(coords) == 3
        targets = {(c.target, c.variant) for c in coords}
        assert ("workbuddy", "coach") in targets
        assert ("workbuddy", "test") in targets
        assert ("universal", "coach") in targets

    def test_plan_invalid_tag(self):
        """plan 无效 tag → 非零退出。"""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "release_bundle.py"), "plan", "invalid-tag"],
            capture_output=True, text=True
        )
        assert result.returncode != 0


# ── Release 描述生成 ─────────────────────────────────────────────────


class TestBuildReleaseDescription:
    def test_title_format(self, tmp_path, monkeypatch):
        """标题为 coachskills YYYY-MM-DD。"""
        from release_bundle import _build_release_description
        import re

        monkeypatch.setattr("release_bundle.BUNDLES_DIR", tmp_path / "bundles")
        monkeypatch.setattr("release_bundle.DIST_DIR", tmp_path / "dist")
        monkeypatch.setenv("GITLAB_API_URL", "https://gitlab.example.com/api/v4")
        monkeypatch.setenv("GITLAB_PROJECT_ID", "123")

        bundle_dir = tmp_path / "bundles" / "test-bundle"
        bundle_dir.mkdir(parents=True)
        bundle_json = {
            "presentation": {
                "defaultLocale": "zh-CN",
                "locales": {"zh-CN": {"name": "测试 Bundle"}}
            }
        }
        (bundle_dir / "bundle.json").write_text(json.dumps(bundle_json))

        # 创建 mock index.json
        dist_dir = tmp_path / "dist" / "workbuddy" / "latest"
        dist_dir.mkdir(parents=True)
        index_json = {
            "schemaVersion": 1,
            "items": {
                "test-bundle/coach": {
                    "variant": "coach",
                    "version": "1.0.0",
                    "target": "workbuddy",
                    "archiveFile": "test-bundle-v1.0.0-coach.zip",
                    "sha256": "abc123"
                }
            }
        }
        (dist_dir / "index.json").write_text(json.dumps(index_json))

        results = {
            "test-bundle/coach": {
                "variant": "coach",
                "version": "1.0.0",
                "target": "workbuddy",
                "archiveFile": "test-bundle-v1.0.0-coach.zip",
                "sha256": "abc123"
            }
        }

        description = _build_release_description(results)

        assert description.startswith("# coachskills ")
        assert re.search(r"# coachskills \d{4}-\d{2}-\d{2}", description)
        # 应包含校验和表
        assert "SHA-256" in description
        assert "`abc123`" in description

    def test_groups_by_bundle(self, tmp_path, monkeypatch):
        """多 bundle 在「更新内容」段按名称分组展示。"""
        from release_bundle import _build_release_description

        monkeypatch.setattr("release_bundle.BUNDLES_DIR", tmp_path / "bundles")
        monkeypatch.setattr("release_bundle.DIST_DIR", tmp_path / "dist")
        monkeypatch.setenv("GITLAB_API_URL", "https://gitlab.example.com/api/v4")
        monkeypatch.setenv("GITLAB_PROJECT_ID", "123")

        for bid, name, changelog in [
            ("ai-customer", "AI 销售陪练", "## [1.0.0]\n\n### Features\n- 新功能 A\n"),
            ("flashcard", "学习闪卡", "## [2.0.0]\n\n### Fixes\n- 修复 B\n"),
        ]:
            bundle_dir = tmp_path / "bundles" / bid
            bundle_dir.mkdir(parents=True)
            bundle_json = {
                "presentation": {
                    "defaultLocale": "zh-CN",
                    "locales": {"zh-CN": {"name": name}}
                }
            }
            (bundle_dir / "bundle.json").write_text(json.dumps(bundle_json))
            (bundle_dir / "CHANGELOG.md").write_text(changelog)

        results = {
            "ai-customer/coach": {
                "bundleId": "ai-customer",
                "variant": "coach",
                "version": "1.0.0",
                "target": "workbuddy",
                "archiveFile": "ai-customer-coach.zip",
                "sha256": "abc"
            },
            "flashcard/coach": {
                "bundleId": "flashcard",
                "variant": "coach",
                "version": "2.0.0",
                "target": "workbuddy",
                "archiveFile": "flashcard-coach.zip",
                "sha256": "def"
            }
        }

        description = _build_release_description(results)

        # 更新内容段应包含两个 bundle 名称和变更条目
        assert "## 更新内容" in description
        assert "AI 销售陪练" in description
        assert "学习闪卡" in description
        assert "新功能 A" in description
        assert "修复 B" in description

    def test_empty_results(self, tmp_path, monkeypatch):
        """空 index.json 只生成标题和空校验和表。"""
        from release_bundle import _build_release_description

        monkeypatch.setattr("release_bundle.BUNDLES_DIR", tmp_path / "bundles")
        monkeypatch.setattr("release_bundle.DIST_DIR", tmp_path / "dist")
        monkeypatch.setenv("GITLAB_API_URL", "https://gitlab.example.com/api/v4")
        monkeypatch.setenv("GITLAB_PROJECT_ID", "123")

        # 创建空 index.json
        dist_dir = tmp_path / "dist" / "workbuddy" / "latest"
        dist_dir.mkdir(parents=True)
        index_json = {"schemaVersion": 1, "items": {}}
        (dist_dir / "index.json").write_text(json.dumps(index_json))

        description = _build_release_description({})

        assert description.startswith("# coachskills ")
        # 没有 bundle 分组（因为 index.json 为空）
        lines = description.split("\n")
        bundle_sections = [l for l in lines if l.startswith("## ") and "更新内容" not in l]
        assert len(bundle_sections) == 0
        # 校验和表仍应存在（空表）
        assert "<details>" in description


# ── Coordinate 属性 ───────────────────────────────────────────────────


class TestCoordinateProperties:
    def test_latest_name(self, tmp_path, monkeypatch):
        """latest_name 使用 distributionName。"""
        from release_bundle import Coordinate, BUNDLES_DIR
        monkeypatch.setattr("release_bundle.BUNDLES_DIR", tmp_path / "bundles")
        bundle_dir = tmp_path / "bundles" / "test-bundle"
        bundle_dir.mkdir(parents=True)
        (bundle_dir / "bundle.json").write_text(json.dumps({
            "targets": {"workbuddy": {"distributionName": "ai-customer"}}
        }))
        c = Coordinate("test-bundle", "1.0.0", "workbuddy", "coach", {})
        assert c.latest_name == "ai-customer-coach.zip"

    def test_registry_package_name(self):
        """registry_package_name 格式：coachskills-<bundle>-<target>。"""
        from release_bundle import Coordinate
        c = Coordinate("ai-customer", "1.0.0", "workbuddy", "coach", {})
        assert c.registry_package_name == "coachskills-ai-customer-workbuddy"

    def test_index_key(self, tmp_path, monkeypatch):
        """index_key 使用 distributionName/variant。"""
        monkeypatch.setattr("release_bundle.BUNDLES_DIR", tmp_path / "bundles")
        bundle_dir = tmp_path / "bundles" / "test-bundle"
        bundle_dir.mkdir(parents=True)
        (bundle_dir / "bundle.json").write_text(json.dumps({
            "targets": {"workbuddy": {"distributionName": "custom-name"}}
        }))
        from release_bundle import Coordinate
        c = Coordinate("test-bundle", "1.0.0", "workbuddy", "dingtalk", {})
        assert c.index_key == "custom-name/dingtalk"


# ── load_release_plan ─────────────────────────────────────────────────


class TestLoadReleasePlan:
    def test_version_mismatch_with_bundle(self, tmp_path, monkeypatch):
        """release-plan 与 bundle.json 版本不一致 → 退出。"""
        from release_bundle import load_release_plan
        monkeypatch.setattr("release_bundle.BUNDLES_DIR", tmp_path / "bundles")
        bundle_dir = tmp_path / "bundles" / "test"
        bundle_dir.mkdir(parents=True)
        (bundle_dir / "bundle.json").write_text(json.dumps({"version": "1.0.0"}))
        (bundle_dir / "release-plan.json").write_text(json.dumps({"version": "2.0.0"}))
        with pytest.raises(SystemExit, match="不匹配"):
            load_release_plan("test", "1.0.0")


# ── _check_collision ──────────────────────────────────────────────────


class TestCheckCollision:
    def test_version_regression_blocked(self, tmp_path, monkeypatch):
        """版本回退 → sys.exit。"""
        from release_bundle import Coordinate, _check_collision
        monkeypatch.setattr("release_bundle.BUNDLES_DIR", tmp_path / "bundles")
        bundle_dir = tmp_path / "bundles" / "test"
        bundle_dir.mkdir(parents=True)
        (bundle_dir / "bundle.json").write_text(json.dumps({
            "targets": {"workbuddy": {"distributionName": "test"}}
        }))
        coord = Coordinate("test", "1.0.0", "workbuddy", "coach", {})
        remote = {"items": {"test/coach": {"version": "1.0.1"}}}
        with pytest.raises(SystemExit, match="版本回退"):
            _check_collision([coord], {"items": {}}, remote)

    def test_same_version_allowed(self, tmp_path, monkeypatch):
        """同版本不报错（覆盖）。"""
        from release_bundle import Coordinate, _check_collision
        monkeypatch.setattr("release_bundle.BUNDLES_DIR", tmp_path / "bundles")
        bundle_dir = tmp_path / "bundles" / "test"
        bundle_dir.mkdir(parents=True)
        (bundle_dir / "bundle.json").write_text(json.dumps({
            "targets": {"workbuddy": {"distributionName": "test"}}
        }))
        coord = Coordinate("test", "1.0.0", "workbuddy", "coach", {})
        remote = {"items": {"test/coach": {"version": "1.0.0", "sha256": "abc"}}}
        _check_collision([coord], {"items": {}}, remote)  # 不报错


# ── prerelease 拦截 ───────────────────────────────────────────────────


class TestPromotePrerelease:
    def test_prerelease_blocked(self, tmp_path, monkeypatch):
        """prerelease 版本不得 promote（RFC §4）。"""
        from release_bundle import cmd_promote
        monkeypatch.setattr("release_bundle.BUNDLES_DIR", tmp_path / "bundles")
        monkeypatch.setattr("release_bundle.DIST_DIR", tmp_path / "dist")
        monkeypatch.setattr("release_bundle.ENVS_FILE", tmp_path / "env.json")
        bundle_dir = tmp_path / "bundles" / "test"
        bundle_dir.mkdir(parents=True)
        (bundle_dir / "bundle.json").write_text(json.dumps({"version": "1.0.0-rc.1"}))
        (bundle_dir / "release-plan.json").write_text(json.dumps({
            "version": "1.0.0-rc.1", "targets": {"workbuddy": ["test"]}
        }))
        with pytest.raises(SystemExit, match="prerelease"):
            cmd_promote("test-v1.0.0-rc.1")


# ── registry_package_hash（Package Files API）──────────────────────────


class TestRegistryPackageHash:
    """测试 registry_package_hash 使用 Package Files API 查询元数据。"""

    def _make_client(self):
        from bundle_builder.gitlab_client import GitLabClient
        return GitLabClient("https://gitlab.example.com/api/v4", "123", "test-token")

    def _mock_urlopen(self, monkeypatch, responses):
        """Mock urlopen to return predefined responses in order."""
        from io import BytesIO
        call_count = [0]

        class MockResponse:
            def __init__(self, data, status=200):
                self._data = data if isinstance(data, bytes) else json.dumps(data).encode()
                self.status = status

            def read(self):
                return self._data

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        def mock_urlopen(req):
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(responses):
                resp = responses[idx]
                if isinstance(resp, Exception):
                    raise resp
                return MockResponse(resp)
            raise AssertionError(f"Unexpected urlopen call #{idx + 1}")

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    def test_found_returns_sha256(self, monkeypatch):
        """文件存在 → 返回 file_sha256。"""
        import urllib.error
        self._mock_urlopen(monkeypatch, [
            # ① packages list
            [{"id": 42, "name": "coachskills-ai-customer-workbuddy", "version": "1.0.0"}],
            # ② package_files list
            [
                {"file_name": "ai-customer-coach.zip", "file_sha256": "abc123def456"},
                {"file_name": "other.zip", "file_sha256": "999"},
            ],
        ])
        client = self._make_client()
        result = client.registry_package_hash(
            "coachskills-ai-customer-workbuddy", "1.0.0", "ai-customer-coach.zip"
        )
        assert result == "abc123def456"

    def test_package_not_found(self, monkeypatch):
        """package 不存在 → 返回 None。"""
        self._mock_urlopen(monkeypatch, [[]])  # 空 packages 列表
        client = self._make_client()
        result = client.registry_package_hash(
            "coachskills-ai-customer-workbuddy", "1.0.0", "ai-customer-coach.zip"
        )
        assert result is None

    def test_file_not_found_in_package(self, monkeypatch):
        """package 存在但文件不匹配 → 返回 None。"""
        self._mock_urlopen(monkeypatch, [
            [{"id": 42}],
            [{"file_name": "other-file.zip", "file_sha256": "xxx"}],
        ])
        client = self._make_client()
        result = client.registry_package_hash(
            "coachskills-ai-customer-workbuddy", "1.0.0", "ai-customer-coach.zip"
        )
        assert result is None

    def test_api_404_returns_none(self, monkeypatch):
        """API 返回 404 → 返回 None。"""
        import urllib.error
        self._mock_urlopen(monkeypatch, [
            urllib.error.HTTPError("url", 404, "Not Found", {}, None),
        ])
        client = self._make_client()
        result = client.registry_package_hash(
            "coachskills-ai-customer-workbuddy", "1.0.0", "ai-customer-coach.zip"
        )
        assert result is None
