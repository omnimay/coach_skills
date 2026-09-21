#!/usr/bin/env python3
"""E_base 静态检查入口（RFC §7.2.1）：调用 scripts/check.py 的对应检查项，
输出 E_base01/02/04/05 四项判定表。真实 MCP 调用不在本脚手架范围（E_base03
已移入 X 矩阵）。"""
import subprocess
import sys
from pathlib import Path

CHECKS = {
    "E_base01": ["frontmatter"],
    "E_base02": ["references"],
    "E_base04": ["qr-fallback"],
    "E_base05": ["oauth-copy"],
}


def main():
    repo_root = Path(__file__).resolve().parents[2]
    check = str(repo_root / "scripts" / "check.py")
    failed = []
    for eid, flags in CHECKS.items():
        r = subprocess.run([sys.executable, check, "--only", *flags],
                           capture_output=True, text=True, cwd=repo_root)
        status = "PASS" if r.returncode == 0 else "FAIL"
        print(f"{eid}: {status}")
        if status == "FAIL":
            failed.append(eid)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
