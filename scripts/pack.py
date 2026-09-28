#!/usr/bin/env python3
"""Bundle 打包脚本（RFC-0003）。

从 bundles/<bundle>/ 配置生成平台特定的 zip 包。

用法：
    python3 scripts/pack.py                                    # 打包所有 bundle（默认 workbuddy）
    python3 scripts/pack.py --bundle flashcard                # 打包指定 bundle
    python3 scripts/pack.py --bundle sales-coach --target workbuddy  # 打包指定 bundle+平台
    python3 scripts/pack.py --out dist/workbuddy               # 指定输出目录
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bundle_builder.bundle import (
    load_bundle,
    validate_bundle,
    validate_bundle_icon,
    resolve_skills,
    write_zip,
    load_environments,
    resolve_placeholders,
)
from bundle_builder.workbuddy import (
    generate_auth_profile,
    generate_connector_meta,
    generate_mcp_json,
    validate_workbuddy,
)

REPO = Path.cwd()
BUNDLES_DIR = REPO / "bundles"
SKILLS_DIR = REPO / "skills"
ENVS_FILE = REPO / "environments.json"


def discover_bundles(filter_names: list[str] | None) -> list[Path]:
    """发现 bundles/ 下的 bundle 目录。"""
    if not BUNDLES_DIR.is_dir():
        print(f"ERROR: bundles 目录不存在：{BUNDLES_DIR}", file=sys.stderr)
        sys.exit(1)

    bundles = []
    for item in sorted(BUNDLES_DIR.iterdir()):
        if item.is_dir() and item.name != "__pycache__" and (item / "bundle.json").is_file():
            if filter_names is None or item.name in filter_names:
                bundles.append(item)

    if filter_names:
        found = {b.name for b in bundles}
        missing = set(filter_names) - found
        if missing:
            print(f"ERROR: 指定的 bundle 不存在：{', '.join(sorted(missing))}", file=sys.stderr)
            sys.exit(1)

    if not bundles:
        print("ERROR: 未发现任何 bundle", file=sys.stderr)
        sys.exit(1)

    return bundles


def pack_bundle(
    bundle_dir: Path,
    target: str,
    out_dir: Path,
    env_vars: dict[str, str] | None = None,
    env_name: str = "",
) -> str:
    """打包单个 bundle 到指定目标平台，返回 zip 文件名。"""
    bundle = load_bundle(bundle_dir)
    validate_bundle(bundle)
    validate_bundle_icon(bundle, bundle_dir)

    # 解析环境变量占位符（缺失变量时 resolve_placeholders 会报错）
    bundle = resolve_placeholders(bundle, env_vars or {})

    skills_files = resolve_skills(bundle, SKILLS_DIR)

    if target == "workbuddy":
        validate_workbuddy(bundle)
        connector_meta = generate_connector_meta(bundle)
        mcp_json = generate_mcp_json(bundle)
    else:
        print(f"ERROR: 不支持的目标平台：{target}", file=sys.stderr)
        sys.exit(1)

    bundle_name = bundle["id"]
    version = bundle["version"]
    # 产物名携带环境名，避免 test/coach 产物混淆
    suffix = f"-{env_name}" if env_name else ""
    zip_name = f"{bundle_name}-v{version}{suffix}.zip"

    entries: dict[Path, bytes] = {}

    # connector-meta.json
    entries[Path("connector-meta.json")] = json.dumps(
        connector_meta, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"

    # mcp.json
    entries[Path("mcp.json")] = json.dumps(
        mcp_json, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"

    # auth-profile.json (RFC-0005)
    auth_profile = generate_auth_profile(env_vars or {})
    entries[Path("auth-profile.json")] = json.dumps(
        auth_profile, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"

    # icon.svg
    icon_path = bundle_dir / bundle["presentation"]["icon"]
    entries[Path("icon.svg")] = icon_path.read_bytes()

    # skills
    for skill_name, rel_files in skills_files.items():
        skill_src = SKILLS_DIR / skill_name
        for rel_path in rel_files:
            archive_path = Path("skills") / skill_name / rel_path
            entries[archive_path] = (skill_src / rel_path).read_bytes()

    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / zip_name
    write_zip(zip_path, entries)

    return zip_name


def main() -> None:
    parser = argparse.ArgumentParser(description="Bundle 打包脚本（RFC-0003）")
    parser.add_argument(
        "--bundle",
        action="append",
        dest="bundles",
        help="指定要打包的 bundle（可多次指定；默认打包所有）",
    )
    parser.add_argument(
        "--target",
        default="workbuddy",
        help="目标平台（默认 workbuddy）",
    )
    parser.add_argument(
        "--env",
        default="test",
        help="目标环境（默认 test），从 environments.json 读取变量",
    )
    parser.add_argument(
        "--out",
        default="dist/workbuddy",
        help="输出目录（默认 dist/workbuddy）",
    )
    args = parser.parse_args()

    # 加载环境配置
    environments = load_environments(ENVS_FILE)
    if args.env not in environments:
        print(f"ERROR: 未知环境 '{args.env}'，可用：{', '.join(environments.keys())}", file=sys.stderr)
        sys.exit(1)
    env_vars = environments[args.env]

    out_dir = REPO / args.out
    bundles = discover_bundles(args.bundles)

    packed = []
    for bundle_dir in bundles:
        zip_name = pack_bundle(bundle_dir, args.target, out_dir, env_vars, args.env)
        packed.append(zip_name)
        print(f"✓ {bundle_dir.name} → {args.out}/{zip_name}")

    print(f"\n打包完成：{len(packed)} 个 bundle → {args.out}/")


if __name__ == "__main__":
    main()
