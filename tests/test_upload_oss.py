"""OSS 通用包上传测试覆盖：index 驱动映射 / SHA-256 核验 / 凭证配置 / dry-run / mock oss2 上传。

oss2 通过 monkeypatch.setitem(sys.modules, "oss2", fake) 注入，
未安装真实 oss2 也能跑、不触碰网络。
"""
import hashlib
import json
import sys
import types
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import upload_oss  # pyright: ignore[reportMissingImports]


# 防止开发者本地 OSS_* 凭证泄漏进测试
@pytest.fixture(autouse=True)
def clean_oss_env(monkeypatch):
    for name in upload_oss.REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)


def write_latest_dir(tmp_path: Path, items: dict[str, dict], extra_zips: list[str] = ()) -> Path:
    """构造一个 latest 目录：index.json + 与条目 sha256 一致的真实 zip。"""
    latest_dir = tmp_path / "latest"
    latest_dir.mkdir()
    for key, item in items.items():
        content = f"zip-of-{key}".encode()
        (latest_dir / item["latestFile"]).write_bytes(content)
        item["sha256"] = hashlib.sha256(content).hexdigest()
    for name in extra_zips:
        (latest_dir / name).write_bytes(f"orphan-{name}".encode())
    (latest_dir / "index.json").write_text(
        json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return latest_dir


def make_item(bundle_id: str, variant: str, latest_file: str, version: str = "1.0.0") -> dict:
    return {
        "bundleId": bundle_id,
        "variant": variant,
        "version": version,
        "latestFile": latest_file,
        "sha256": "0" * 64,  # 由 write_latest_dir 覆写为真实值
    }


# ── 上传计划构建 ──────────────────────────────────────────────────────


class TestBuildUploadPlan:
    def test_key_mapping_from_index(self, tmp_path):
        items = {
            "ai-customer/coach": make_item("ai-customer", "coach", "ai-customer-coach.zip", "1.0.4"),
            # distributionName 与 bundleId 分歧的用例：latestFile 前缀不是 bundleId，
            # 证明 OSS 路径由 bundleId 驱动而非解析文件名
            "custom-name/dingtalk": make_item("test-bundle", "dingtalk", "custom-name-dingtalk.zip"),
        }
        latest_dir = write_latest_dir(tmp_path, items)
        plan = upload_oss.build_upload_plan(latest_dir)
        keys = {entry["oss_key"] for entry in plan}
        assert keys == {
            "mcpskills/coach/ai-customer/ai-customer-coach.zip",
            "mcpskills/coach/test-bundle/custom-name-dingtalk.zip",
        }

    def test_plan_carries_metadata(self, tmp_path):
        items = {"ai-customer/coach": make_item("ai-customer", "coach", "ai-customer-coach.zip", "1.0.4")}
        plan = upload_oss.build_upload_plan(write_latest_dir(tmp_path, items))
        assert plan[0]["bundle_id"] == "ai-customer"
        assert plan[0]["variant"] == "coach"
        assert plan[0]["version"] == "1.0.4"
        assert plan[0]["zip_path"].name == "ai-customer-coach.zip"

    def test_index_json_not_uploaded(self, tmp_path):
        items = {"ai-customer/coach": make_item("ai-customer", "coach", "ai-customer-coach.zip")}
        plan = upload_oss.build_upload_plan(write_latest_dir(tmp_path, items))
        assert all("index.json" not in entry["oss_key"] for entry in plan)
        assert len(plan) == 1

    def test_index_entry_without_zip_errors(self, tmp_path):
        latest_dir = write_latest_dir(tmp_path, {"ai-customer/coach": make_item("ai-customer", "coach", "ai-customer-coach.zip")})
        (latest_dir / "ai-customer-coach.zip").unlink()
        with pytest.raises(SystemExit, match="缺失"):
            upload_oss.build_upload_plan(latest_dir)

    def test_zip_without_index_entry_errors(self, tmp_path):
        items = {"ai-customer/coach": make_item("ai-customer", "coach", "ai-customer-coach.zip")}
        latest_dir = write_latest_dir(tmp_path, items, extra_zips=["orphan-bundle-coach.zip"])
        with pytest.raises(SystemExit, match="未收录"):
            upload_oss.build_upload_plan(latest_dir)

    def test_sha256_mismatch_errors(self, tmp_path):
        latest_dir = write_latest_dir(tmp_path, {"ai-customer/coach": make_item("ai-customer", "coach", "ai-customer-coach.zip")})
        # 篡改 zip 内容但保留 index 记录的旧哈希
        (latest_dir / "ai-customer-coach.zip").write_bytes(b"corrupted")
        with pytest.raises(SystemExit, match="SHA-256"):
            upload_oss.build_upload_plan(latest_dir)

    def test_missing_index_errors(self, tmp_path):
        with pytest.raises(SystemExit, match="index.json"):
            upload_oss.build_upload_plan(tmp_path)

    def test_empty_index_errors(self, tmp_path):
        latest_dir = tmp_path / "latest"
        latest_dir.mkdir()
        (latest_dir / "index.json").write_text(json.dumps({"items": {}}), encoding="utf-8")
        with pytest.raises(SystemExit, match="items 为空"):
            upload_oss.build_upload_plan(latest_dir)


# ── OSS 凭证配置 ──────────────────────────────────────────────────────


class TestLoadOssConfig:
    def test_missing_env_vars_exit(self):
        with pytest.raises(SystemExit, match="OSS_"):
            upload_oss.load_oss_config()

    def test_partial_env_vars_exit(self, monkeypatch):
        monkeypatch.setenv("OSS_ACCESS_KEY_ID", "ak")
        with pytest.raises(SystemExit, match="OSS_ACCESS_KEY_SECRET"):
            upload_oss.load_oss_config()

    def test_config_returns_all_values(self, monkeypatch):
        for name in upload_oss.REQUIRED_ENV:
            monkeypatch.setenv(name, f"value-{name}")
        config = upload_oss.load_oss_config()
        assert config == {name: f"value-{name}" for name in upload_oss.REQUIRED_ENV}


# ── 上传执行（mock oss2）──────────────────────────────────────────────


class FakeResponse:
    def __init__(self, status=200, etag="\"etag-fake\""):
        self.status = status
        self.etag = etag


class FakeBucket:
    def __init__(self, failures: dict[str, int] | None = None):
        self.calls: list[tuple[str, str, dict]] = []
        self.failures = failures or {}

    def put_object_from_file(self, key, path, headers=None):
        self.calls.append((key, path, dict(headers or {})))
        status = self.failures.get(key, 200)
        return FakeResponse(status=status)


def install_fake_oss2(monkeypatch, bucket: FakeBucket):
    """把 fake oss2 模块塞进 sys.modules，make_bucket() 惰性 import 时即拿到假件。"""
    fake = types.SimpleNamespace(
        Auth=lambda ak, sk: ("auth", ak, sk),
        Bucket=lambda auth, endpoint, bucket_name: bucket,
    )
    monkeypatch.setitem(sys.modules, "oss2", fake)


class TestUpload:
    def test_upload_calls_put_object_from_file(self, tmp_path, monkeypatch, capsys):
        items = {
            "ai-customer/coach": make_item("ai-customer", "coach", "ai-customer-coach.zip"),
            "flashcard/test": make_item("flashcard", "test", "flashcard-test.zip"),
        }
        latest_dir = write_latest_dir(tmp_path, items)
        for name in upload_oss.REQUIRED_ENV:
            monkeypatch.setenv(name, f"value-{name}")
        monkeypatch.setattr("sys.argv", ["upload_oss.py", str(latest_dir)])
        fake_bucket = FakeBucket()
        install_fake_oss2(monkeypatch, fake_bucket)

        upload_oss.main()

        assert len(fake_bucket.calls) == 2
        keys = [call[0] for call in fake_bucket.calls]
        assert "mcpskills/coach/ai-customer/ai-customer-coach.zip" in keys
        assert "mcpskills/coach/flashcard/flashcard-test.zip" in keys
        for _, path, headers in fake_bucket.calls:
            assert headers["Content-Type"] == "application/zip"
            assert headers["Cache-Control"] == "no-cache, max-age=0, must-revalidate"
            assert len(headers["x-oss-meta-sha256"]) == 64
            assert Path(path).is_file()
        out = capsys.readouterr().out
        assert "完成：2 个通用包已上传" in out

    def test_upload_non_200_exits(self, tmp_path, monkeypatch):
        items = {"ai-customer/coach": make_item("ai-customer", "coach", "ai-customer-coach.zip")}
        latest_dir = write_latest_dir(tmp_path, items)
        for name in upload_oss.REQUIRED_ENV:
            monkeypatch.setenv(name, f"value-{name}")
        monkeypatch.setattr(
            "sys.argv", ["upload_oss.py", "--retries", "1", "--retry-backoff", "0", str(latest_dir)]
        )
        key = "mcpskills/coach/ai-customer/ai-customer-coach.zip"
        install_fake_oss2(monkeypatch, FakeBucket(failures={key: 500}))

        with pytest.raises(SystemExit, match="500"):
            upload_oss.main()

    def test_missing_creds_exits_before_upload(self, tmp_path, monkeypatch):
        items = {"ai-customer/coach": make_item("ai-customer", "coach", "ai-customer-coach.zip")}
        latest_dir = write_latest_dir(tmp_path, items)
        monkeypatch.setattr("sys.argv", ["upload_oss.py", str(latest_dir)])
        # 环境变量全缺（autouse fixture 已清空）→ 在构造 bucket 前退出
        with pytest.raises(SystemExit, match="OSS_"):
            upload_oss.main()

    def test_oss2_import_error_message(self, tmp_path, monkeypatch):
        items = {"ai-customer/coach": make_item("ai-customer", "coach", "ai-customer-coach.zip")}
        latest_dir = write_latest_dir(tmp_path, items)
        for name in upload_oss.REQUIRED_ENV:
            monkeypatch.setenv(name, f"value-{name}")
        monkeypatch.setattr("sys.argv", ["upload_oss.py", str(latest_dir)])
        # None 占位使 `import oss2` 抛 ImportError
        monkeypatch.setitem(sys.modules, "oss2", None)

        with pytest.raises(SystemExit, match="oss2"):
            upload_oss.main()


# ── dry-run ───────────────────────────────────────────────────────────


class TestMainDryRun:
    def test_dry_run_prints_plan_without_creds(self, tmp_path, monkeypatch, capsys):
        items = {"ai-customer/coach": make_item("ai-customer", "coach", "ai-customer-coach.zip")}
        latest_dir = write_latest_dir(tmp_path, items)
        monkeypatch.setattr("sys.argv", ["upload_oss.py", "--dry-run", str(latest_dir)])

        upload_oss.main()  # 无任何 OSS_* 凭证也应成功

        out = capsys.readouterr().out
        assert "oss://megaview/mcpskills/coach/ai-customer/ai-customer-coach.zip" in out
        assert "dry-run" in out

    def test_dry_run_never_constructs_bucket(self, tmp_path, monkeypatch):
        items = {"ai-customer/coach": make_item("ai-customer", "coach", "ai-customer-coach.zip")}
        latest_dir = write_latest_dir(tmp_path, items)
        monkeypatch.setattr("sys.argv", ["upload_oss.py", "--dry-run", str(latest_dir)])

        def explode():
            raise AssertionError("dry-run 不应构造 oss2.Bucket")

        monkeypatch.setattr(upload_oss, "make_bucket", explode)
        upload_oss.main()  # 不应触发 AssertionError

    def test_missing_dir_exits(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["upload_oss.py", "--dry-run", "/nonexistent/latest"])
        with pytest.raises(SystemExit, match="目录不存在"):
            upload_oss.main()


class TestUploadValidationAndRetry:
    def test_path_traversal_in_index_is_rejected(self, tmp_path):
        latest_dir = tmp_path / "latest"
        latest_dir.mkdir()
        item = make_item("ai-customer", "coach", "../outside.zip")
        (latest_dir / "index.json").write_text(
            json.dumps({"items": {"ai-customer/coach": item}}), encoding="utf-8"
        )
        with pytest.raises(SystemExit, match="latestFile 不合法"):
            upload_oss.build_upload_plan(latest_dir)

    def test_remote_head_is_verified(self, tmp_path):
        content = b"zip-content"
        zip_path = tmp_path / "package.zip"
        zip_path.write_bytes(content)
        sha = hashlib.sha256(content).hexdigest()

        class HeadResponse:
            status = 200
            content_length = len(content)
            headers = {"x-oss-meta-sha256": sha}

        class HeadBucket:
            def __init__(self):
                self.uploads = 0
                self.heads = 0

            def put_object_from_file(self, key, path, headers=None):
                self.uploads += 1
                assert headers["x-oss-meta-sha256"] == sha
                return FakeResponse()

            def head_object(self, key):
                self.heads += 1
                return HeadResponse()

        bucket = HeadBucket()
        upload_oss.upload_one(bucket, zip_path, "key", "bucket", expected_sha=sha, retry_backoff=0)
        assert bucket.uploads == 1
        assert bucket.heads == 1

    def test_transient_status_is_retried(self, tmp_path):
        zip_path = tmp_path / "package.zip"
        zip_path.write_bytes(b"zip-content")

        class SequenceBucket:
            def __init__(self):
                self.statuses = [503, 200]
                self.calls = 0

            def put_object_from_file(self, key, path, headers=None):
                self.calls += 1
                return FakeResponse(status=self.statuses.pop(0))

        bucket = SequenceBucket()
        upload_oss.upload_one(bucket, zip_path, "key", "bucket", retries=1, retry_backoff=0)
        assert bucket.calls == 2
