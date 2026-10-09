#!/usr/bin/env python3
"""Bundle 发布入口（RFC-0006 §5）— 半自动化工具。

⚠️ 本工具仅覆盖发布六步中的 ③④⑤（构建、归档、提升）。
   以下步骤需要人工完成：
   - ① MR 准备（更新 bundle.json/release-plan.json 版本号、编写 CHANGELOG）
   - ② 打 tag（创建 Git tag 并推送）
   - ⑥ 渠道交付（提交 WorkBuddy 等平台）

用法：
    # 预览发布计划（不执行任何操作）
    python3 scripts/release_bundle.py plan <tag> [--dry-run]

    # 构建 + 上传 Registry + 创建 Release（需要 GitLab API 配置）
    python3 scripts/release_bundle.py archive <tag> [--dry-run]

    # 复制 ZIP 到 latest/ + 更新 index.json（需要 GitLab API 配置）
    python3 scripts/release_bundle.py promote <tag> [--dry-run]

    # 执行 plan → archive → promote 全流程
    python3 scripts/release_bundle.py full <tag> [--dry-run]

tag 格式：<bundle-id>-v<SemVer>（如 ai-customer-v1.0.2）

发布六步：
  ① MR 准备（人工）→ ② 打 tag（人工）→ ③ 构建（自动）→ ④ 归档（自动）→ ⑤ 提升（自动）→ ⑥ 渠道交付（人工）

本脚本覆盖 ③④⑤：
  - plan:    解析 tag，加载 release-plan.json，输出待发布坐标清单
  - archive: 调用共用 build_bundle_zip 构建 → 上传 Registry → 下载核验 → 创建 Release
  - promote: 复制 ZIP 到 latest/ → 更新 index.json → 提交推送

不执行任何交互式 git 操作（推送除外,需手动或 CI 自动）。

认证方式（archive/promote 命令需要）：
  1. glab CLI 自动认证（推荐）：如已安装并登录 glab CLI,脚本会自动读取认证信息
     - 检查认证状态: glab auth status
     - 登录: glab auth login --hostname git.mgvai.cn
  2. 环境变量认证:
     - GITLAB_API_URL: GitLab API 地址（如 https://git.mgvai.cn/api/v4）
     - GITLAB_PROJECT_ID: GitLab 项目 ID（如 490）
     - GITLAB_TOKEN: GitLab Personal Access Token（需要 api scope）

完整发布流程见 README.md 的"发布流程"章节。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from bundle_builder.build import build_bundle_zip  # pyright: ignore[reportMissingImports]
from bundle_builder.bundle import (  # pyright: ignore[reportMissingImports]
    load_bundle,
    parse_semver,
    compare_versions,
)
from bundle_builder.gitlab_client import (  # pyright: ignore[reportMissingImports]
    GitLabClient,
    sha256_of,
)

REPO = Path.cwd()
BUNDLES_DIR = REPO / "bundles"
SKILLS_DIR = REPO / "skills"
DIST_DIR = REPO / "dist"
ENVS_FILE = REPO / "environments.json"

TAG_RE = re.compile(r"^(?P<bundle_id>[a-zA-Z0-9][a-zA-Z0-9._-]*)-v(?P<version>\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?(?:\+[0-9A-Za-z.]+)?)$")


# ── 数据模型 ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Coordinate:
    """发布坐标：bundle × version × target × variant。"""

    bundle_id: str
    version: str
    target: str
    variant: str
    env_vars: dict[str, str]

    @property
    def zip_name(self) -> str:
        """带版本号的归档文件名。"""
        return f"{self.bundle_id}-v{self.version}-{self.variant}.zip"

    @property
    def latest_name(self) -> str:
        """latest/ 下的无版本号文件名（用 distributionName）。"""
        return f"{self.distribution_name}-{self.variant}.zip"

    @property
    def distribution_name(self) -> str:
        """latest/ 文件前缀（默认 = bundle_id）。"""
        bundle_dir = BUNDLES_DIR / self.bundle_id
        bundle = load_bundle(bundle_dir)
        return bundle.get("targets", {}).get(self.target, {}).get(
            "distributionName", self.bundle_id
        )

    @property
    def registry_package_name(self) -> str:
        return f"coachskills-{self.bundle_id}-{self.target}"

    @property
    def index_key(self) -> str:
        """index.json 中的键：distributionName/variant。"""
        return f"{self.distribution_name}/{self.variant}"


def parse_tag(tag: str) -> tuple[str, str]:
    """解析 tag → (bundle_id, version)。不符合格式时 sys.exit。"""
    m = TAG_RE.match(tag)
    if not m:
        sys.exit(f"ERROR: tag 格式不合法：{tag}（期望 <bundle-id>-v<SemVer>）")
    bundle_id, version = m.group("bundle_id"), m.group("version")
    try:
        parse_semver(version)
    except ValueError:
        sys.exit(f"ERROR: tag 中版本不是合法 SemVer：{version}")
    return bundle_id, version


def load_release_plan(bundle_id: str, expected_version: str) -> dict[str, Any]:
    """加载并校验 release-plan.json。"""
    plan_path = BUNDLES_DIR / bundle_id / "release-plan.json"
    if not plan_path.is_file():
        sys.exit(f"ERROR: release-plan.json 不存在：{plan_path}")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("version") != expected_version:
        sys.exit(
            f"ERROR: release-plan.json 版本 {plan.get('version')} "
            f"与 tag 版本 {expected_version} 不匹配"
        )
    # 校验 bundle.json 版本同步
    bundle = load_bundle(BUNDLES_DIR / bundle_id)
    if bundle.get("version") != expected_version:
        sys.exit(
            f"ERROR: bundle.json 版本 {bundle.get('version')} "
            f"与 tag 版本 {expected_version} 不匹配"
        )
    return plan


def build_coordinates(bundle_id: str, version: str, plan: dict[str, Any]) -> list[Coordinate]:
    """从 release-plan.json 生成坐标列表。"""
    from bundle_builder.bundle import load_environments  # pyright: ignore[reportMissingImports]
    envs = load_environments(ENVS_FILE)
    coords: list[Coordinate] = []
    for target, variants in plan.get("targets", {}).items():
        for variant in variants:
            if variant not in envs:
                sys.exit(f"ERROR: 环境 '{variant}' 未在 environments.json 中注册")
            coords.append(Coordinate(
                bundle_id=bundle_id,
                version=version,
                target=target,
                variant=variant,
                env_vars=envs[variant],
            ))
    return coords


# ── 子命令：plan ──────────────────────────────────────────────────────


def cmd_plan(tag: str, dry_run: bool = False) -> list[Coordinate]:
    """解析 tag → 输出坐标清单。dry_run 保留以与其他子命令签名一致。"""
    _ = dry_run  # plan 不涉及副作用，保留参数以统一接口
    bundle_id, version = parse_tag(tag)
    plan = load_release_plan(bundle_id, version)
    coords = build_coordinates(bundle_id, version, plan)
    print(f"📋 发布计划：{tag}")
    print(f"   bundle: {bundle_id}  version: {version}")
    for c in coords:
        print(f"   → {c.target}/{c.variant}: {c.zip_name} → {c.latest_name}")
    print(f"\n共 {len(coords)} 个坐标。")
    return coords


# ── 子命令：archive ──────────────────────────────────────────────────


def cmd_archive(tag: str, dry_run: bool = False) -> dict[str, dict[str, Any]]:
    """构建 → 上传 Registry → 下载核验 → 创建 Release。

    返回 {coordinate.index_key: {sha256, archive_url, ...}} 供 promote 使用。
    """
    bundle_id, version = parse_tag(tag)
    plan = load_release_plan(bundle_id, version)
    coords = build_coordinates(bundle_id, version, plan)
    client = GitLabClient.from_env() if not dry_run else None

    results: dict[str, dict[str, Any]] = {}
    for c in coords:
        print(f"\n📦 {c.zip_name}")
        # ① 构建
        bundle_dir = BUNDLES_DIR / c.bundle_id
        entries, _ = build_bundle_zip(bundle_dir, SKILLS_DIR, c.target, c.env_vars, c.variant)
        # 序列化 entries 为 bytes（用于上传）
        import tempfile
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            from bundle_builder.build import write_entries_zip  # pyright: ignore[reportMissingImports]
            write_entries_zip(tmp_path, entries)
            zip_bytes = tmp_path.read_bytes()
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink()
        sha = sha256_of(zip_bytes)
        print(f"   构建完成：{len(zip_bytes)} bytes, SHA-256={sha[:16]}...")

        if dry_run:
            print("   [dry-run] 跳过上传")
            results[c.index_key] = {
                "bundleId": c.bundle_id, "version": c.version,
                "target": c.target, "variant": c.variant,
                "sha256": sha, "latestFile": c.latest_name,
                "archiveFile": c.zip_name,
            }
            continue

        # ② 上传（P1 修复：先检查已存在包，同哈希跳过，不同哈希阻断）
        pkg_name = c.registry_package_name
        assert client is not None
        existing_hash = client.registry_package_hash(pkg_name, c.version, c.zip_name)
        if existing_hash is not None:
            if existing_hash == sha:
                print(f"   ℹ️ Registry 已存在同内容包（SHA-256 匹配），跳过上传")
            else:
                sys.exit(
                    f"   ✗ Registry 已存在同坐标但不同内容的包！\n"
                    f"      已归档 SHA-256={existing_hash[:16]}...\n"
                    f"      本次构建 SHA-256={sha[:16]}...\n"
                    f"      同版本不可变（RFC-0006 §4），请升级版本号后重试"
                )
        else:
            upload_sha = client.upload_package(pkg_name, c.version, c.zip_name, zip_bytes)
            print(f"   上传完成：SHA-256={upload_sha[:16]}...")
            if upload_sha != sha:
                sys.exit(f"   ✗ 上传后哈希不一致！本地={sha} 远端={upload_sha}")

            # ③ 元数据核验（通过 Package Files API 查询服务端 SHA-256，不下载文件）
            verify_sha = client.registry_package_hash(pkg_name, c.version, c.zip_name)
            if verify_sha is None:
                sys.exit(f"   ✗ 上传后在 Registry 中未找到文件！")
            if verify_sha != sha:
                sys.exit(f"   ✗ 元数据核验失败！本地={sha[:16]}... 服务端={verify_sha[:16]}...")
            print("   ✓ 元数据核验通过（Package Files API）")

        results[c.index_key] = {
            "bundleId": c.bundle_id, "version": c.version,
            "target": c.target, "variant": c.variant,
            "tag": tag, "sha256": sha,
            "latestFile": c.latest_name, "archiveFile": c.zip_name,
            "registryPath": f"generic/{pkg_name}/{c.version}/{c.zip_name}",
        }

    # ④ 创建 Release
    if not dry_run and results:
        description = _build_release_description(results)
        assert client is not None
        client.create_release(tag, tag, description)
        print(f"\n📝 Release 已创建/更新：{tag}")

    return results



def _resolve_bundle_name(bid: str) -> str:
    """从 bundle.json 读取显示名称；加载失败则回退到 bundle_id。"""
    try:
        bundle = load_bundle(BUNDLES_DIR / bid)
        locale = bundle.get("presentation", {}).get("defaultLocale", "zh-CN")
        return (
            bundle.get("presentation", {}).get("locales", {})
            .get(locale, {}).get("name", bid)
        )
    except (SystemExit, FileNotFoundError, KeyError, json.JSONDecodeError, OSError):
        return bid


def _build_release_description(
    results: dict[str, dict[str, Any]],
) -> str:
    """构造 Release 描述（日期标题 + 更新内容 + SHA-256）。

    格式：
    - 标题：coachskills YYYY-MM-DD
    - 更新内容：从 CHANGELOG.md 读取，按 bundle 分组
    - 校验和：SHA-256 折叠展示（仅本次发布的包，从 results 读取）

    注：下载链接不在 Release 描述中展示（冗余），用户通过 OSS / Registry 直接取包。
    """
    from datetime import datetime

    # 1. 生成标题（项目名 + 日期）
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [f"# coachskills {date_str}", ""]

    # 2. 更新内容（从 CHANGELOG.md 读取，按 bundle 分组）
    # 收集所有涉及的 bundle（从 results 提取，含全部 variant）
    bundle_ids: set[str] = set()
    for info in results.values():
        bid = info.get("bundleId", "")
        if bid:
            bundle_ids.add(bid)

    changelog_sections: list[str] = []
    for bid in sorted(bundle_ids):
        changelog_path = BUNDLES_DIR / bid / "CHANGELOG.md"
        if not changelog_path.is_file():
            continue
        try:
            content = changelog_path.read_text(encoding="utf-8")
            name = _resolve_bundle_name(bid)

            # 解析 CHANGELOG.md，提取最新版本（第一个 ## [x.y.z] 段落）的条目
            lines_changelog = content.split("\n")
            in_current_version = False
            current_entries: dict[str, list[str]] = {}  # {section: [entries]}
            current_section = ""

            for line in lines_changelog:
                if line.startswith("## ["):
                    if in_current_version:
                        break  # 遇到下一个版本段落，停止
                    in_current_version = True
                elif in_current_version and line.startswith("### "):
                    current_section = line[4:].strip()
                    current_entries.setdefault(current_section, [])
                elif in_current_version and line.startswith("- ") and current_section:
                    current_entries[current_section].append(line[2:])

            if current_entries:
                changelog_sections.append(f"### {name}")
                changelog_sections.append("")
                for section in ["Features", "Changes", "Fixes"]:
                    if section in current_entries and current_entries[section]:
                        changelog_sections.append(f"**{section}**")
                        for entry in current_entries[section]:
                            changelog_sections.append(f"- {entry}")
                        changelog_sections.append("")
        except OSError:
            pass

    if changelog_sections:
        lines.append("## 更新内容")
        lines.append("")
        lines.extend(changelog_sections)

    # 5. 校验和（折叠）— 包含所有 variant（含 test）
    lines.append("<details>")
    lines.append("<summary>SHA-256</summary>")
    lines.append("")
    lines.append("| 文件 | SHA-256 |")
    lines.append("|------|---------|")
    for info in sorted(results.values(), key=lambda x: x.get("archiveFile", "")):
        archive_file = info.get("archiveFile", "")
        sha256 = info.get("sha256", "")
        lines.append(f"| {archive_file} | `{sha256}` |")
    lines.append("")
    lines.append("</details>")

    return "\n".join(lines)


# ── 子命令：promote ─────────────────────────────────────────────────


def cmd_promote(tag: str, dry_run: bool = False) -> None:
    """复制 ZIP 到 latest/ → 更新 index.json。

    前置条件：archive 已成功完成（通过 Registry 下载获取 SHA-256）。
    RFC §4：prerelease 不进 latest/。
    RFC §5 步骤⑤：全有或全无——先下载到暂存目录，全部成功后再原子替换。

    支持多 target：按 target 分组，每个 target 独立碰撞检测 + 独立 index.json。
    """
    bundle_id, version = parse_tag(tag)

    # H1 修复：prerelease 拦截（RFC §4）
    sv = parse_semver(version)
    if sv.prerelease:
        sys.exit(f"ERROR: prerelease {version} 不得 promote 到 latest/（RFC §4）")

    plan = load_release_plan(bundle_id, version)
    coords = build_coordinates(bundle_id, version, plan)

    # 按 target 分组
    coords_by_target: dict[str, list[Coordinate]] = {}
    for c in coords:
        coords_by_target.setdefault(c.target, []).append(c)

    # H3 修复：校验 tag 指向当前 HEAD（RFC §3.3 防 tag 漂移）
    try:
        tag_commit = subprocess.check_output(
            ["git", "rev-parse", f"{tag}^{{commit}}"], text=True, stderr=subprocess.DEVNULL,
            timeout=30,
        ).strip()
        head_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True,
            timeout=30,
        ).strip()
        if tag_commit != head_commit:
            sys.exit(
                f"ERROR: tag {tag} 指向 {tag_commit[:12]}，"
                f"但 HEAD 是 {head_commit[:12]}（tag 已漂移，请重建 tag）"
            )
    except subprocess.CalledProcessError:
        pass  # tag 不是本地 git ref（如 CI 浅克隆），跳过校验

    # 碰撞检测：按 target 分组，每个 target 独立检测
    if not dry_run:
        for target, target_coords in coords_by_target.items():
            target_latest_dir = DIST_DIR / target / "latest"
            existing_index = _load_existing_index(target_latest_dir)
            remote_index: dict[str, Any] = {"items": {}}
            try:
                client_pre = GitLabClient.from_env()
                remote_raw = client_pre.read_repo_file(f"dist/{target}/latest/index.json")
                if remote_raw:
                    remote_index = json.loads(remote_raw)
            except SystemExit:
                raise
            except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError) as e:
                print(f"⚠️ 无法读取远端 {target}/latest/index.json（{type(e).__name__}），跳过碰撞检测")
            _check_collision(target_coords, existing_index, remote_index)

    # H2 修复：全部下载成功后原子替换到 latest/（RFC §5 全有或全无）
    downloaded: dict[str, tuple[Coordinate, bytes]] = {}
    client = GitLabClient.from_env() if not dry_run else None
    try:
        for c in coords:
            if dry_run:
                print(f"[dry-run] 将下载 {c.zip_name} → {c.latest_name} (target={c.target})")
                continue
            assert client is not None  # dry_run 已跳过，client 必非 None
            data = client.download_package(c.registry_package_name, c.version, c.zip_name)
            verify = sha256_of(data)
            print(f"  ↓ {c.latest_name}（SHA-256={verify[:16]}...）")

            # P2 修复：同版本时校验下载哈希与已记录哈希，不同则阻断
            target_latest_dir = DIST_DIR / c.target / "latest"
            existing_index = _load_existing_index(target_latest_dir)
            key = c.index_key
            existing_item = existing_index.get("items", {}).get(key)
            if (existing_item
                    and existing_item.get("version") == c.version
                    and existing_item.get("sha256")
                    and existing_item["sha256"] != verify):
                sys.exit(
                    f"ERROR: 坐标 {key} 版本相同但哈希不同！\n"
                    f"       已记录 SHA-256={existing_item['sha256'][:16]}...\n"
                    f"       Registry 返回 SHA-256={verify[:16]}...\n"
                    f"       同版本不可变，Registry 内容可能被篡改"
                )

            downloaded[f"{c.target}/{c.index_key}"] = (c, data)

        if not dry_run:
            for _, (c, data) in downloaded.items():
                target_dir = DIST_DIR / c.target / "latest"
                target_dir.mkdir(parents=True, exist_ok=True)
                latest_path = target_dir / c.latest_name
                # 先写临时文件再原子替换，避免半写
                tmp_path = latest_path.with_suffix(".zip.tmp")
                tmp_path.write_bytes(data)
                tmp_path.replace(latest_path)
                print(f"✓ {c.target}/{c.latest_name}")
    except Exception:
        raise

    # 按 target 分组更新 index.json
    for target, target_coords in coords_by_target.items():
        target_latest_dir = DIST_DIR / target / "latest"
        _update_index(target_latest_dir, target_coords, tag, dry_run)
    print(f"\n📂 latest/ 已更新：{len(coords)} 个坐标（{', '.join(coords_by_target.keys())}）")


def _load_existing_index(latest_dir: Path) -> dict[str, Any]:
    """加载本地 index.json；不存在返回空。"""
    index_path = latest_dir / "index.json"
    if not index_path.is_file():
        return {"schemaVersion": 1, "items": {}}
    return json.loads(index_path.read_text(encoding="utf-8"))


def _check_collision(
    coords: list[Coordinate],
    local_index: dict[str, Any],
    remote_index: dict[str, Any],
) -> None:
    """碰撞检测：同一键下的版本不得回退。"""
    for c in coords:
        key = c.index_key
        remote_item = remote_index.get("items", {}).get(key)
        local_item = local_index.get("items", {}).get(key)
        existing = remote_item or local_item
        if existing and existing.get("version"):
            cmp = compare_versions(c.version, existing["version"])
            if cmp < 0:
                sys.exit(
                    f"ERROR: 坐标 {key} 版本回退：{c.version} < 已有 {existing['version']}"
                )
            if cmp == 0 and existing.get("sha256"):
                print(f"  ℹ️ {key} 版本相同，将覆盖（需确认哈希一致）")


def _update_index(
    latest_dir: Path,
    coords: list[Coordinate],
    tag: str,
    dry_run: bool,
) -> None:
    """更新 index.json（RFC-0006 §3.3）。"""
    index_path = latest_dir / "index.json"
    index = _load_existing_index(latest_dir)

    # 获取 source commit（当前 HEAD）
    try:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True,
            timeout=30,
        ).strip()
    except subprocess.CalledProcessError:
        source_commit = "<unknown>"

    # 计算 releaseUrl（M4 修复：避免永久空串，RFC §3.3「避免 GitLab 迁移时断链」）
    api_url = os.environ.get("GITLAB_API_URL", "")
    project_id = os.environ.get("GITLAB_PROJECT_ID", "")
    if api_url and project_id:
        # 将 API URL 转换为 Web URL（去掉 /api/v4 后缀）
        web_url = re.sub(r"/api/v\d+/?$", "", api_url)
        release_url = f"{web_url}/-/releases/{tag}"
    else:
        release_url = ""

    for c in coords:
        # 从已写入的 latest 文件计算 SHA-256
        latest_path = latest_dir / c.latest_name
        sha = sha256_of(latest_path.read_bytes()) if latest_path.is_file() else ""
        index["items"][c.index_key] = {
            "bundleId": c.bundle_id,
            "version": c.version,
            "target": c.target,
            "variant": c.variant,
            "tag": tag,
            "sourceCommit": source_commit,
            "latestFile": c.latest_name,
            "archiveFile": c.zip_name,
            "sha256": sha,
            "releaseUrl": release_url,
        }

    if dry_run:
        print(f"[dry-run] 将更新 {index_path}")
        print(json.dumps(index, ensure_ascii=False, indent=2))
        return

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# ── 子命令：full（全流程） ───────────────────────────────────────────


def cmd_full(tag: str, dry_run: bool = False) -> None:
    """执行 plan → archive → promote 全流程。"""
    cmd_plan(tag, dry_run)
    print("\n" + "=" * 60)
    cmd_archive(tag, dry_run)
    print("\n" + "=" * 60)
    cmd_promote(tag, dry_run)
    print("\n✅ 全流程完成")


# ── 入口 ──────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Bundle 发布脚本（RFC-0006）")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, fn in [("plan", cmd_plan), ("archive", cmd_archive),
                     ("promote", cmd_promote), ("full", cmd_full)]:
        p = sub.add_parser(name, help=fn.__doc__ or "")
        p.add_argument("tag", help="发布 tag（如 ai-customer-v1.0.2）")
        p.add_argument("--dry-run", action="store_true", help="只输出计划，不实际执行")

    args = parser.parse_args()
    fn = {"plan": cmd_plan, "archive": cmd_archive,
          "promote": cmd_promote, "full": cmd_full}[args.command]
    fn(args.tag, args.dry_run)


if __name__ == "__main__":
    main()
