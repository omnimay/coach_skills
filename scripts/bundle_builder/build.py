"""共用构建函数（RFC-0006 §5）。

pack.py 与 release_bundle.py 共享的构建路径，保证「同输入 → 同哈希」。
"""
import json
import sys
from pathlib import Path

from bundle_builder.bundle import (
    load_bundle,
    resolve_placeholders,
    resolve_skills,
    validate_bundle,
    validate_bundle_icon,
    write_zip,
)
from bundle_builder.targets import TargetBuilder, UniversalTarget, WorkbuddyTarget
from bundle_builder.workbuddy import generate_mcp_json


def build_bundle_zip(
    bundle_dir: Path,
    skills_dir: Path,
    target: str,
    env_vars: dict[str, str] | None = None,
    env_name: str = "",
) -> tuple[dict[Path, bytes], str]:
    """构建 bundle 的全部 zip 条目。

    参数：
        bundle_dir:  bundle 目录路径
        skills_dir:  skills/ 目录路径
        target:      目标平台（'workbuddy' 或 'universal'）
        env_vars:    环境变量（用于 ${VAR} 占位符替换）
        env_name:    环境名（用于产物名后缀，避免 test/coach 混淆）

    返回：
        (entries, zip_name)
        - entries: {archive_path: bytes}  所有 zip 内条目（已排序、确定性）
        - zip_name: 产物文件名（如 'flashcard-v1.0.1-coach.zip'）

    异常：
        调用 sys.exit 退出（与 bundle.py 的 fail 行为一致）
    """
    bundle = load_bundle(bundle_dir)
    validate_bundle(bundle)
    validate_bundle_icon(bundle, bundle_dir)
    bundle = resolve_placeholders(bundle, env_vars or {})
    skills_files = resolve_skills(bundle, skills_dir)

    # 选择 target builder
    target_builder: TargetBuilder
    if target == "workbuddy":
        target_builder = WorkbuddyTarget(bundle_dir)
    elif target == "universal":
        target_builder = UniversalTarget(bundle_dir)
    else:
        sys.exit(f"ERROR: 不支持的目标平台：{target}")

    # 验证 bundle
    target_builder.validate(bundle)

    bundle_name = bundle["id"]
    version = bundle["version"]
    suffix = f"-{env_name}" if env_name else ""
    zip_name = f"{bundle_name}-v{version}{suffix}.zip"

    entries: dict[Path, bytes] = {}

    # ── 通用文件（所有 target 共享）──────────────────────────────

    # mcp.json
    mcp_json = generate_mcp_json(bundle)
    entries[Path("mcp.json")] = (
        json.dumps(mcp_json, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    )

    # skills
    for skill_name, rel_files in skills_files.items():
        skill_src = skills_dir / skill_name
        for rel_path in rel_files:
            archive_path = Path("skills") / skill_name / rel_path
            entries[archive_path] = (skill_src / rel_path).read_bytes()

    # ── Target 特定文件 ──────────────────────────────────────────

    target_entries = target_builder.build_entries(bundle, env_vars or {})
    entries.update(target_entries)

    return entries, zip_name


def write_entries_zip(zpath: Path, entries: dict[Path, bytes]) -> None:
    """将 entries 写入 zip 文件（原子写入）。供 pack.py 等调用方使用。"""
    write_zip(zpath, entries)
