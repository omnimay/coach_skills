#!/usr/bin/env python3
"""Bundle 打包脚本（RFC-0003 + RFC-0006）。

从 bundles/<bundle>/ 配置生成平台特定的 zip 包。
构建逻辑共享于 bundle_builder/build.py，供 release_bundle.py 复用。

用法：
    python3 scripts/pack.py                                    # 打包所有 bundle（默认 workbuddy）
    python3 scripts/pack.py --bundle flashcard                # 打包指定 bundle
    python3 scripts/pack.py --bundle ai-customer --target workbuddy  # 打包指定 bundle+平台
    python3 scripts/pack.py --out dist/workbuddy               # 指定输出目录
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bundle_builder.build import build_bundle_zip, write_entries_zip  # pyright: ignore[reportMissingImports]
from bundle_builder.bundle import load_environments  # pyright: ignore[reportMissingImports]

REPO = Path.cwd()
BUNDLES_DIR = REPO / "bundles"
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
        default=None,
        help="输出目录（默认 dist/<target>）",
    )
    args = parser.parse_args()

    # 确定输出目录：如果未指定，则使用 dist/<target>
    out_dir_name = args.out if args.out else f"dist/{args.target}"

    # 加载环境配置
    environments = load_environments(ENVS_FILE)
    if args.env not in environments:
        print(f"ERROR: 未知环境 '{args.env}'，可用：{', '.join(environments.keys())}", file=sys.stderr)
        sys.exit(1)
    env_vars = environments[args.env]

    out_dir = REPO / out_dir_name
    bundles = discover_bundles(args.bundles)
    skills_dir = REPO / "skills"

    packed = []
    for bundle_dir in bundles:
        entries, zip_name = build_bundle_zip(
            bundle_dir, skills_dir, args.target, env_vars, args.env
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        zip_path = out_dir / zip_name
        write_entries_zip(zip_path, entries)
        packed.append(zip_name)
        print(f"✓ {bundle_dir.name} → {out_dir_name}/{zip_name}")

    print(f"\n打包完成：{len(packed)} 个 bundle → {out_dir_name}/")


if __name__ == "__main__":
    main()
