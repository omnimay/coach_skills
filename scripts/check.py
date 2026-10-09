#!/usr/bin/env python3
"""静态检查（RFC-0002）：技能通用化基线 + plugin manifest 校验。

用法：
    python3 scripts/check.py                     # 全量
    python3 scripts/check.py --only host-terms   # 只跑所选检查

退出码：0 全部通过；1 任一失败；2 用法错误。
不执行任何 git 写操作。
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

# 添加脚本目录到路径，以便导入 file_validator
sys.path.insert(0, str(Path(__file__).parent))
import file_validator  # pyright: ignore[reportMissingImports]
from bundle_builder.bundle import load_bundle, validate_bundle, validate_bundle_icon, parse_semver, load_environments  # pyright: ignore[reportMissingImports]
from bundle_builder.workbuddy import validate_workbuddy  # pyright: ignore[reportMissingImports]

REPO = Path.cwd()  # 从仓库根运行
SKILLS_DIR = REPO / "skills"
README = REPO / "README.md"
MIGRATION_DOC = REPO / "docs/migration/ai_customer_design.md"
BUNDLES_DIR = REPO / "bundles"

CHECKS = ("frontmatter", "host-terms", "trigger-phrases", "mechanism-terms",
          "references", "readme", "migration", "manifests", "qr-fallback",
          "oauth-copy", "file-boundary", "release-plan", "distribution")

# distributionName 只允许安全文件名（字母、数字、连字符、下划线、点）
DISTRIBUTION_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
# 已知 target 名称（可扩展）
KNOWN_TARGETS = {"workbuddy", "universal"}

FRONTMATTER_REQUIRED = ("name", "description")
FRONTMATTER_ALLOWED = {"name", "description", "license", "metadata", "allowed-tools"}

TRIGGER_PHRASES = ("Use when", "Only use", "<when_to_use>", "Use this skill when")
HOST_NAMES = ("Claude Code", "Anthropic", "Codex", "WorkBuddy", "Cursor",
              "Aider", "Continue.dev")
PRIVATE_DIRS = ("~/.claude/", "~/.codex/", "~/.workbuddy/", "~/.cursor/",
                "~/.aider/", "~/.continue/")
PRIVATE_MECHANISMS = ("SessionStart", "StatusLine", "Hook", "thinking",
                      "tool_use", "subagent", "Task 工具", "_meta.progressToken")

EXEMPT_RE = re.compile(r"<!-- host-term-note -->.*?<!-- /host-term-note -->", re.S)
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
README_TEMPLATE_KEYS = ("Getting started with GitLab", "Add your files", "Test and Deploy")
MIGRATION_SECTIONS = ("M01", "M03", "M10", "P1.5")
OAUTH_HOST_SETTING_RE = re.compile(
    r"(?:Claude Code|Anthropic|Codex|WorkBuddy|Cursor|Aider|Continue\.dev|Claude|Continue) 设置")

ERRORS: list = []  # [(category, location, message)]


def fail(category, location, message):
    ERRORS.append((category, location, message))


def discover_skills():
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(d for d in SKILLS_DIR.iterdir() if (d / "SKILL.md").is_file())


def skill_markdown(skill):
    """只扫 SKILL.md + references/*.md；vendor/、scripts/ 不在扫描范围。"""
    files = [skill / "SKILL.md"]
    refs = skill / "references"
    if refs.is_dir():
        files += sorted(p for p in refs.glob("*.md") if p.is_file())
    return [f for f in files if f.is_file()]


def load_frontmatter(path):
    """共享解析契约（与 build.py 同一 PyYAML/UTF-8/LF/`---` 边界约定）。

    返回 (meta, body_text, fm_end_line)：meta 解析失败时为 None；
    body_text 为关闭 `---` 之后的全部内容（保留原始行号，从 fm_end_line+1 起）。
    """
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text, 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            block = "\n".join(lines[1:i])
            try:
                meta = yaml.safe_load(block) or {}
            except yaml.YAMLError:
                meta = None
            return meta, "\n".join(lines[i + 1:]), i + 1
    return None, text, 0  # 无关闭边界


def strip_exemptions(text):
    """剥离 host-term-note 豁免段，保留行数以维持行号。"""
    return EXEMPT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def check_frontmatter(skills):
    for skill in skills:
        path = skill / "SKILL.md"
        meta, _, fm_end = load_frontmatter(path)
        if meta is None:
            fail("FRONTMATTER", f"{path}:1", "frontmatter 解析失败（YAML/`---` 边界）")
            continue
        if not isinstance(meta, dict):
            fail("FRONTMATTER", f"{path}:1", "frontmatter 必须是键值映射")
            meta = {}
        for field in FRONTMATTER_REQUIRED:
            if not meta.get(field):
                fail("FRONTMATTER", f"{path}:1", f"必填字段缺失或为空：{field}")
        fm_lines = path.read_text(encoding="utf-8").split("\n")[:fm_end]
        for n, line in enumerate(fm_lines, 1):
            key = line.split(":", 1)[0].strip() if ":" in line else ""
            if not key or line.startswith((" ", "-", "#")):
                continue
            if key == "allowed-tools":
                fail("FRONTMATTER", f"{path}:{n}", "allowed-tools 出现即 fail（首期一律不写）")
            elif key not in FRONTMATTER_ALLOWED:
                fail("FRONTMATTER", f"{path}:{n}", f"白名单外字段：{key}")


def check_banned_terms(skills, category, terms):
    for skill in skills:
        for path in skill_markdown(skill):
            text = strip_exemptions(path.read_text(encoding="utf-8"))
            for n, line in enumerate(text.split("\n"), 1):
                for term in terms:
                    if term in line:  # 大小写敏感精确子串（§3.6.1）
                        fail(category, f"{path}:{n}", f"禁用词「{term}」")


def _link_targets(path):
    text = strip_exemptions(path.read_text(encoding="utf-8"))
    for n, line in enumerate(text.split("\n"), 1):
        for _, target in LINK_RE.findall(line):
            if not re.match(r"^[a-z][a-z0-9+.-]*:", target) and not target.startswith("#"):
                # 剥离锚点部分（如 file.md#anchor → file.md）
                target_without_anchor = target.split("#")[0] if "#" in target else target
                yield n, target_without_anchor


def check_references(skills):
    for skill in skills:
        root = skill.resolve()
        for path in skill_markdown(skill):
            for n, target in _link_targets(path):
                resolved = (path.parent / target).resolve()
                if not resolved.exists():
                    fail("REFERENCES", f"{path}:{n}", f"链接目标不存在：{target}")
                elif root != resolved and root not in resolved.parents:
                    fail("REFERENCES", f"{path}:{n}", f"链接越界（超出技能目录）：{target}")
        for dirpath, dirnames, filenames in os.walk(skill, followlinks=False):
            for name in dirnames + filenames:
                entry = Path(dirpath) / name
                if entry.is_symlink():
                    fail("REFERENCES", f"{entry}", "symlink 不允许出现在技能目录内（T05）")


def check_readme():
    if not README.is_file():
        return  # README 属 Task 11 交付，缺失按"无内容可查"处理
    text = README.read_text(encoding="utf-8")
    for key in README_TEMPLATE_KEYS:
        if key in text:
            fail("README", f"{README}", f"GitLab 模板残留关键字：{key}")


def check_migration():
    if not MIGRATION_DOC.is_file():
        return  # 无内容可查
    text = MIGRATION_DOC.read_text(encoding="utf-8")
    for section in MIGRATION_SECTIONS:
        if section not in text:
            fail("MIGRATION", f"{MIGRATION_DOC}", f"迁移记录缺少小节：{section}")


def check_manifests(full):
    """校验 bundles/ 下每个 bundle 的 bundle.json。"""
    if not BUNDLES_DIR.is_dir():
        if full:
            fail("MANIFESTS", str(BUNDLES_DIR), "bundles 目录缺失")
        return

    bundles = [
        d for d in BUNDLES_DIR.iterdir()
        if d.is_dir() and d.name != "__pycache__" and (d / "bundle.json").is_file()
    ]
    if not bundles:
        if full:
            fail("MANIFESTS", str(BUNDLES_DIR), "未发现任何 bundle")
        return

    for bundle_dir in bundles:
        try:
            bundle = load_bundle(bundle_dir)
        except SystemExit:
            fail("MANIFESTS", str(bundle_dir / "bundle.json"), "bundle.json 加载失败")
            continue
        try:
            validate_bundle(bundle)
            validate_bundle_icon(bundle, bundle_dir)
            validate_workbuddy(bundle)
        except SystemExit:
            fail("MANIFESTS", str(bundle_dir / "bundle.json"), "bundle 校验失败")


def check_qr_fallback(skills):
    for skill in skills:
        # 只对 ai_customer_design 技能要求 QR 降级指引（其他技能不涉及练习链接）
        if skill.name != "ai_customer_design":
            continue
        path = skill / "SKILL.md"
        _, body, _ = load_frontmatter(path)
        body = strip_exemptions(body or "")
        if "QR 生成失败" not in body or "练习链接" not in body:
            fail("QR-FALLBACK", f"{path}", "缺少 QR 降级指引（需含「QR 生成失败」与「练习链接」，E_base04）")


def check_oauth_copy(skills):
    for skill in skills:
        for path in skill_markdown(skill):
            _, body, offset = load_frontmatter(path)
            body = strip_exemptions(body or "")
            for n, line in enumerate(body.split("\n"), offset + 1):
                if OAUTH_HOST_SETTING_RE.search(line):
                    fail("OAUTH-COPY", f"{path}:{n}",
                         "OAuth 文案点名宿主设置（应使用中性表述「由宿主 MCP 设置重新连接」，E_base05）")


def check_file_boundary():
    """校验所有 skill 的文件边界（敏感文件、路径穿越等）。"""
    if not SKILLS_DIR.is_dir():
        return

    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir() or skill_dir.name == "__pycache__":
            continue
        skill_name = skill_dir.name
        errors = file_validator.check_skill_files(skill_name, SKILLS_DIR)
        for error in errors:
            fail("FILE-BOUNDARY", f"skills/{skill_name}", error)


def discover_bundles() -> list[Path]:
    """列出 bundles/ 下所有有效 bundle 目录。"""
    if not BUNDLES_DIR.is_dir():
        return []
    return sorted(
        d for d in BUNDLES_DIR.iterdir()
        if d.is_dir() and d.name != "__pycache__" and (d / "bundle.json").is_file()
    )


def check_release_plan():
    """校验每个 bundle 的 release-plan.json（RFC-0006 §5）。"""
    # 加载 environments.json 用于变体名校验
    envs_file = REPO / "environments.json"
    try:
        envs = load_environments(envs_file)
    except (SystemExit, OSError):
        envs = {}

    for bundle_dir in discover_bundles():
        plan_path = bundle_dir / "release-plan.json"
        if not plan_path.is_file():
            fail("RELEASE-PLAN", str(plan_path), "release-plan.json 缺失")
            continue
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            fail("RELEASE-PLAN", str(plan_path), f"JSON 解析失败：{e}")
            continue

        if not isinstance(plan, dict):
            fail("RELEASE-PLAN", str(plan_path), "顶层必须是对象")
            continue

        # version 必须存在且为合法 SemVer
        version = plan.get("version")
        if not isinstance(version, str):
            fail("RELEASE-PLAN", f"{plan_path}:version", "version 必须是字符串")
            continue
        try:
            parse_semver(version)
        except ValueError:
            fail("RELEASE-PLAN", f"{plan_path}:version", f"不是合法 SemVer：{version}")
            continue

        # 必须与 bundle.json 的 version 匹配
        try:
            bundle = load_bundle(bundle_dir)
        except SystemExit:
            fail("RELEASE-PLAN", str(plan_path), "bundle.json 加载失败")
            continue
        if version != bundle.get("version"):
            fail(
                "RELEASE-PLAN", f"{plan_path}:version",
                f"与 bundle.json 版本不一致：{version} ≠ {bundle.get('version')}"
            )

        # targets 必须是非空对象
        targets = plan.get("targets")
        if not isinstance(targets, dict) or not targets:
            fail("RELEASE-PLAN", f"{plan_path}:targets", "targets 必须是非空对象")
            continue

        for target_name, variants in targets.items():
            if target_name not in KNOWN_TARGETS:
                fail("RELEASE-PLAN", f"{plan_path}:targets.{target_name}", f"未知 target：{target_name}")
            if not isinstance(variants, list) or not variants:
                fail("RELEASE-PLAN", f"{plan_path}:targets.{target_name}", "variants 必须是非空数组")
                continue
            # 变体名必须是字符串且无重复
            for v in variants:
                if not isinstance(v, str) or not v:
                    fail("RELEASE-PLAN", f"{plan_path}:targets.{target_name}", f"变体必须是字符串：{v!r}")
            if len(set(variants)) != len(variants):
                fail("RELEASE-PLAN", f"{plan_path}:targets.{target_name}", "variants 有重复项")
            # 变体名必须在 environments.json 中注册
            for v in variants:
                if isinstance(v, str) and v not in envs:
                    fail("RELEASE-PLAN", f"{plan_path}:targets.{target_name}",
                         f"变体 {v!r} 未在 environments.json 中注册")


def check_distribution():
    """校验每个 bundle 的 distributionName（RFC-0006 §3.1）+ 跨 bundle 文件名碰撞。"""
    # 收集所有坐标键：{target/distributionName/variant: bundle_dir}
    seen_keys: dict[str, Path] = {}

    for bundle_dir in discover_bundles():
        try:
            bundle = load_bundle(bundle_dir)
        except SystemExit:
            continue
        bundle_id = bundle.get("id", bundle_dir.name)

        # release-plan.json 驱动校验
        plan_path = bundle_dir / "release-plan.json"
        if not plan_path.is_file():
            continue
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            fail("DISTRIBUTION", str(plan_path), f"JSON 解析失败：{e}")
            continue
        except OSError as e:
            fail("DISTRIBUTION", str(plan_path), f"读取失败：{e}")
            continue

        for target, variants in plan.get("targets", {}).items():
            if not isinstance(variants, list):
                continue

            # 按 target 读取 distributionName（与 Coordinate.distribution_name 一致）
            target_cfg = bundle.get("targets", {}).get(target, {})
            dist_name = target_cfg.get("distributionName") or bundle_id

            # 单个 bundle 的 distributionName 格式校验
            if target_cfg.get("distributionName") is not None:
                if not isinstance(dist_name, str) or not DISTRIBUTION_NAME_RE.match(dist_name):
                    fail(
                        "DISTRIBUTION", f"{bundle_dir}/bundle.json:targets.{target}.distributionName",
                        f"只能是字母、数字、连字符、下划线、点：{dist_name!r}"
                    )

            for variant in variants:
                key = f"{target}/{dist_name}/{variant}"
                if key in seen_keys:
                    fail(
                        "DISTRIBUTION", f"{bundle_dir}/release-plan.json",
                        f"坐标 {key} 与 {seen_keys[key].name} 冲突（同文件名）"
                    )
                else:
                    seen_keys[key] = bundle_dir


def main():
    parser = argparse.ArgumentParser(description="技能仓库静态检查（RFC-0002）")
    parser.add_argument("--only", nargs="+", choices=CHECKS, metavar="CHECK",
                        help="只运行所选检查（不传则全量）")
    args = parser.parse_args()
    full = not args.only
    selected = set(args.only) if args.only else set(CHECKS)

    skills = discover_skills()
    if full and not skills:
        fail("STRUCT", str(SKILLS_DIR), "skills/ 下未发现任何 SKILL.md")

    if "frontmatter" in selected:
        check_frontmatter(skills)
    if "host-terms" in selected:
        check_banned_terms(skills, "HOST-TERMS", HOST_NAMES + PRIVATE_DIRS)
    if "trigger-phrases" in selected:
        check_banned_terms(skills, "TRIGGER", TRIGGER_PHRASES)
    if "mechanism-terms" in selected:
        check_banned_terms(skills, "MECHANISM", PRIVATE_MECHANISMS)
    if "references" in selected:
        check_references(skills)
    if "readme" in selected:
        check_readme()
    if "migration" in selected:
        check_migration()
    if "manifests" in selected:
        check_manifests(full)
    if "qr-fallback" in selected:
        check_qr_fallback(skills)
    if "oauth-copy" in selected:
        check_oauth_copy(skills)
    if "file-boundary" in selected:
        check_file_boundary()
    if "release-plan" in selected:
        check_release_plan()
    if "distribution" in selected:
        check_distribution()

    for category, location, message in ERRORS:
        print(f"E-MAINT-{category}: {location} {message}", file=sys.stderr)
    if ERRORS:
        sys.exit(1)
    print(f"check.py: OK（{'/'.join(sorted(selected))}）")


if __name__ == "__main__":
    main()
