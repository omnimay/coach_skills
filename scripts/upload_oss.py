#!/usr/bin/env python3
"""OSS 通用包上传（docs/oss-upload-automation.md）— 发布六步 ⑥-b 渠道交付。

将 promote 产物 dist/universal/latest/*.zip 上传到阿里云 OSS：
    https://<bucket>.<endpoint>/mcpskills/coach/<bundle_id>/<bundle-id>-<variant>.zip

其中 `<bundle_id>` 为 bundleId 中的连字符替换为下划线（如 ai_customer），`<bundle-id>` 保持原格式（如 ai-customer）。

设计要点：
  - 映射由 index.json 驱动（bundleId + latestFile），不解析文件名——
    即使 bundle 的 distributionName 与 bundle-id 分歧，OSS 路径仍然正确
  - 上传前校验本地 SHA-256 与 index.json 记录一致（防截断/过期产物）
  - 暂态网络失败指数退避重试；上传后用 HEAD 核验大小与 SHA-256 元数据
  - 同名覆盖（latest 语义）；历史版本可追溯 GitLab Generic Package Registry
  - oss2 惰性 import：--dry-run 无需安装 oss2、无需配置凭据

用法：
    # 预览上传计划（本地校验 + 打印，不触碰 OSS）
    python3 scripts/upload_oss.py --dry-run [latest_dir]

    # 实际上传（默认目录 dist/universal/latest/）
    python3 scripts/upload_oss.py [latest_dir]

环境变量（GitLab CI/CD Variables 或本地 export）：
    OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET  — 子账号凭证（需 PutObject + HEAD/GetObject 核验权限）
    OSS_ENDPOINT  — 区域 endpoint（oss-cn-zhangjiakou.aliyuncs.com，不含 bucket 名）
    OSS_BUCKET    — bucket 名（megaview）
    OSS_SECURITY_TOKEN — 可选，使用 RAM/STS 临时凭证时填写
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DEFAULT_LATEST_DIR = REPO / "dist" / "universal" / "latest"
OSS_KEY_PREFIX = "mcpskills/coach"
# latest 对象会被覆盖，禁止 CDN 长时间复用旧内容；版本历史保存在 Registry。
UPLOAD_HEADERS = {
    "Content-Type": "application/zip",
    "Cache-Control": "no-cache, max-age=0, must-revalidate",
    "x-oss-object-acl": "public-read",  # 每个对象单独设为公开可读（bucket 为 private 模式）
}
REQUIRED_ENV = ("OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET", "OSS_ENDPOINT", "OSS_BUCKET")
DEFAULT_RETRIES = 3
DEFAULT_RETRY_BACKOFF = 1.0
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def fail(message: str) -> None:
    sys.exit(f"ERROR: {message}")


def sha256_file(path: Path) -> str:
    """流式计算文件 SHA-256。"""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_oss_config() -> dict[str, str]:
    """读取 4 个 OSS_* 环境变量；缺失任一则列出缺失项并退出。"""
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name, "").strip()]
    if missing:
        fail(
            f"缺少 OSS 配置：{', '.join(missing)}。"
            "请在 GitLab CI/CD Variables 或本地环境变量中设置："
            + " / ".join(REQUIRED_ENV)
        )
    config = {name: os.environ[name].strip() for name in REQUIRED_ENV}
    if os.environ.get("OSS_SECURITY_TOKEN"):
        config["OSS_SECURITY_TOKEN"] = os.environ["OSS_SECURITY_TOKEN"].strip()
    return config


def _safe_segment(value: Any, field: str, coordinate: str) -> str:
    if not isinstance(value, str) or not value or not SAFE_SEGMENT.fullmatch(value):
        fail(f"index 条目 {coordinate} 的 {field} 不合法：{value!r}")
    return value


def _safe_latest_file(value: Any, coordinate: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or Path(value).name != value
        or "\\" in value
        or not value.endswith(".zip")
        or not SAFE_SEGMENT.fullmatch(Path(value).stem)
    ):
        fail(f"index 条目 {coordinate} 的 latestFile 不合法：{value!r}")
    return value


def _load_index(index_path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"无法读取或解析 {index_path}：{exc}")
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), dict):
        fail(f"{index_path} 缺少合法的 items 对象")
    if not raw["items"]:
        fail(f"{index_path} 中 items 为空，无可上传内容")
    return raw


def build_upload_plan(latest_dir: Path) -> list[dict]:
    """由 index.json 构建上传计划，并完成全部本地校验。

    每项：{"zip_path", "oss_key", "bundle_id", "variant", "version", "sha256"}
    校验（任一失败 sys.exit）：
      - index.json 存在且 items 非空
      - 每个 latestFile 在目录中存在
      - 本地 SHA-256 与 index 记录一致
      - 目录中不存在 index 未收录的孤儿 zip
    """
    index_path = latest_dir / "index.json"
    if not index_path.is_file():
        fail(f"未找到 {index_path}（promote 产物缺失，请先运行 release_bundle.py promote）")
    latest_root = latest_dir.resolve()
    items = _load_index(index_path)["items"]

    plan: list[dict] = []
    seen_files: set[str] = set()
    seen_keys: set[str] = set()
    for key, item in sorted(items.items()):
        if not isinstance(key, str) or not isinstance(item, dict):
            fail(f"index 条目格式不合法：{key!r}")
        latest_file = _safe_latest_file(item.get("latestFile"), key)
        bundle_id = _safe_segment(item.get("bundleId"), "bundleId", key)
        variant = _safe_segment(item.get("variant"), "variant", key)
        version = item.get("version")
        if not isinstance(version, str) or not version.strip():
            fail(f"index 条目 {key} 的 version 不合法：{version!r}")
        expected_sha = item.get("sha256")
        if not isinstance(expected_sha, str) or not SHA256_RE.fullmatch(expected_sha.lower()):
            fail(f"index 条目 {key} 的 sha256 不合法")
        if latest_file in seen_files:
            fail(f"index 中 latestFile 重复：{latest_file}")
        # OSS 文件夹名使用下划线格式（bundle_id 中的连字符转为下划线）
        # bundle_id 已在上方通过 _safe_segment 校验，replace("-", "_") 不会引入非法字符
        oss_folder = bundle_id.replace("-", "_")
        oss_key = f"{OSS_KEY_PREFIX}/{oss_folder}/{latest_file}"
        if oss_key in seen_keys:
            fail(f"index 中 OSS 路径重复：{oss_key}")
        seen_files.add(latest_file)
        seen_keys.add(oss_key)
        zip_path = latest_dir / latest_file
        try:
            resolved_zip = zip_path.resolve(strict=True)
            resolved_zip.relative_to(latest_root)
        except (OSError, ValueError):
            fail(f"index 条目 {key} 对应的文件缺失或不在 latest 目录内：{zip_path}")
        if not resolved_zip.is_file():
            fail(f"index 条目 {key} 对应的文件缺失：{zip_path}")
        local_sha = sha256_file(resolved_zip)
        if local_sha != expected_sha.lower():
            fail(
                f"SHA-256 不一致，疑似截断或过期产物：{latest_file}\n"
                f"  index 记录: {expected_sha}\n  本地实际: {local_sha}"
            )
        plan.append(
            {
                "zip_path": resolved_zip,
                "oss_key": oss_key,
                "bundle_id": bundle_id,
                "variant": variant,
                "version": version,
                "sha256": expected_sha.lower(),
            }
        )

    # 孤儿 zip 检查：目录里的 zip 必须都被 index 收录（防止漏传某个变体）
    indexed = {entry["zip_path"].name for entry in plan}
    orphans = sorted(
        p.name
        for p in latest_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".zip" and p.name not in indexed
    )
    if orphans:
        fail(f"目录中存在 index.json 未收录的 zip（不会上传）：{', '.join(orphans)}")
    return plan


def make_bucket():
    """构造 oss2.Bucket；先校验凭证，再惰性 import oss2（未安装时给出安装提示）。"""
    config = load_oss_config()
    try:
        import oss2
    except ImportError:
        fail("未安装 oss2 SDK，请执行：pip install oss2==2.19.1")
    if config.get("OSS_SECURITY_TOKEN"):
        # oss2.Auth 2.19.1 只接受 AK/SK；STS 临时凭证使用 StsAuth。
        auth = oss2.StsAuth(
            config["OSS_ACCESS_KEY_ID"],
            config["OSS_ACCESS_KEY_SECRET"],
            config["OSS_SECURITY_TOKEN"],
        )
    else:
        auth = oss2.Auth(config["OSS_ACCESS_KEY_ID"], config["OSS_ACCESS_KEY_SECRET"])
    return oss2.Bucket(auth, config["OSS_ENDPOINT"], config["OSS_BUCKET"])


def _is_retryable_exception(exc: Exception) -> bool:
    status = getattr(exc, "status", None) or getattr(exc, "code", None)
    if isinstance(status, int):
        return status in RETRYABLE_STATUS
    # oss2.RequestError 代表连接、超时等暂态错误；避免对鉴权/参数错误盲目重试。
    return exc.__class__.__name__ in {"RequestError", "TimeoutError", "ConnectionError"}


def _verify_remote(bucket, zip_path: Path, oss_key: str, expected_sha: str) -> None:
    """用 HEAD 核验对象大小及上传时写入的 SHA-256 元数据。"""
    try:
        head = bucket.head_object(oss_key)
    except Exception as exc:
        fail(f"上传后核验请求失败（{type(exc).__name__}）：{oss_key}：{exc}")
    status = getattr(head, "status", 200)
    if status != 200:
        fail(f"上传后核验失败（HTTP {status}）：{oss_key}")
    content_length = getattr(head, "content_length", None)
    if content_length is not None and content_length != zip_path.stat().st_size:
        fail(
            f"上传后大小核验失败：{oss_key}（本地={zip_path.stat().st_size}，远端={content_length}）"
        )
    headers = getattr(head, "headers", {}) or {}
    remote_sha = next(
        (value for name, value in headers.items() if name.lower() == "x-oss-meta-sha256"),
        None,
    )
    if remote_sha is None or str(remote_sha).lower() != expected_sha:
        fail(f"上传后 SHA-256 元数据核验失败：{oss_key}")


def upload_one(
    bucket,
    zip_path: Path,
    oss_key: str,
    bucket_name: str,
    expected_sha: str = "",
    retries: int = DEFAULT_RETRIES,
    retry_backoff: float = DEFAULT_RETRY_BACKOFF,
    verify_remote: bool = True,
) -> None:
    """上传单个 zip，暂态失败重试，并在 SDK 支持 HEAD 时核验远端对象。"""
    expected_sha = expected_sha.lower()
    headers = {**UPLOAD_HEADERS}
    if expected_sha:
        headers["x-oss-meta-sha256"] = expected_sha
    attempts = retries + 1
    for attempt in range(1, attempts + 1):
        try:
            if expected_sha and sha256_file(zip_path) != expected_sha:
                fail(f"上传前文件已变化，拒绝上传：{zip_path}")
            resp = bucket.put_object_from_file(oss_key, str(zip_path), headers=headers)
            status = getattr(resp, "status", 0)
            if status == 200:
                break
            if status not in RETRYABLE_STATUS or attempt == attempts:
                fail(f"上传失败（HTTP {status}）：{oss_key}")
            print(f"⚠️ 上传暂态失败（HTTP {status}），{attempt}/{attempts}，准备重试：{oss_key}")
        except Exception as exc:
            if not _is_retryable_exception(exc) or attempt == attempts:
                fail(f"上传异常（{type(exc).__name__}）：{oss_key}：{exc}")
            print(f"⚠️ 上传网络异常，{attempt}/{attempts}，准备重试：{oss_key}：{exc}")
        time.sleep(max(0.0, retry_backoff) * (2 ** (attempt - 1)))

    if verify_remote and expected_sha and hasattr(bucket, "head_object"):
        _verify_remote(bucket, zip_path, oss_key, expected_sha)
    etag = getattr(resp, "etag", "")
    print(f"✓ oss://{bucket_name}/{oss_key}（ETag={etag}）")


def main() -> None:
    parser = argparse.ArgumentParser(description="上传通用包到阿里云 OSS（latest 语义，覆盖写入）")
    parser.add_argument(
        "latest_dir",
        nargs="?",
        default=str(DEFAULT_LATEST_DIR),
        help=f"promote 产物目录（默认 {DEFAULT_LATEST_DIR}）",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅本地校验并打印计划，不实际上传")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help="暂态失败重试次数（默认 3）")
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=DEFAULT_RETRY_BACKOFF,
        help="重试退避基数秒数（默认 1）",
    )
    parser.add_argument("--skip-remote-verify", action="store_true", help="跳过上传后的 HEAD 核验")
    args = parser.parse_args()

    if args.retries < 0 or args.retry_backoff < 0:
        fail("--retries 和 --retry-backoff 必须是非负数")

    latest_dir = Path(args.latest_dir)
    if not latest_dir.is_dir():
        fail(f"目录不存在：{latest_dir}")

    plan = build_upload_plan(latest_dir)
    bucket_name = os.environ.get("OSS_BUCKET", "").strip() or "megaview"
    print(f"上传计划（{len(plan)} 项，源目录 {latest_dir}）：")
    for entry in plan:
        print(
            f"  {entry['zip_path'].name}（{entry['bundle_id']} {entry['version']} / {entry['variant']}）"
            f" → oss://{bucket_name}/{entry['oss_key']}"
        )

    if args.dry_run:
        print("dry-run：SHA-256 全部核验通过，未实际上传")
        return

    bucket = make_bucket()
    for entry in plan:
        upload_one(
            bucket,
            entry["zip_path"],
            entry["oss_key"],
            bucket_name,
            expected_sha=entry["sha256"],
            retries=args.retries,
            retry_backoff=args.retry_backoff,
            verify_remote=not args.skip_remote_verify,
        )
    print(f"完成：{len(plan)} 个通用包已上传 OSS（latest 语义，覆盖写入）")


if __name__ == "__main__":
    main()
