#!/usr/bin/env python3
"""文件收集与校验模块（RFC-0002）。

被 check.py 和 pack.py 共同调用，确保校验对象与最终打包对象完全一致。

核心职责：
- 验证 skill 名称合法性（禁止路径穿越）
- 解析真实路径，确认在技能根目录内
- 拒绝符号链接
- 排除敏感文件和临时文件
"""
from pathlib import Path

# 敏感文件模式（精确匹配或后缀匹配）
SENSITIVE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "credentials",
    "secrets",
    "id_rsa",
    "id_ed25519",
}

SENSITIVE_SUFFIXES = {
    ".key",
    ".pem",
    ".p12",
    ".pfx",
    ".jks",
    ".keystore",
    ".secret",
    ".secrets",
}

# 临时文件和缓存
TEMP_SUFFIXES = {
    ".log",
    ".tmp",
    ".bak",
    ".swp",
    ".swo",
    ".pyc",
    ".pyo",
}

TEMP_DIRS = {
    "__pycache__",
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    ".DS_Store",
}


def validate_skill_name(skill_name: str) -> None:
    """验证 skill 名称是合法目录名。

    Raises:
        ValueError: 如果名称包含路径穿越或非法字符
    """
    if not skill_name:
        raise ValueError("skill 名称不能为空")

    # 禁止路径分隔符
    if "/" in skill_name or "\\" in skill_name:
        raise ValueError(f"skill 名称不能包含路径分隔符：{skill_name}")

    # 禁止绝对路径
    if skill_name.startswith(("/", "\\")) or (len(skill_name) >= 2 and skill_name[1] == ":"):
        raise ValueError(f"skill 名称不能是绝对路径：{skill_name}")

    # 禁止 . 和 ..
    if skill_name in (".", ".."):
        raise ValueError(f"skill 名称不能是 . 或 ..：{skill_name}")

    # 禁止包含 .. 组件
    if ".." in skill_name:
        raise ValueError(f"skill 名称不能包含 ..：{skill_name}")


def is_sensitive_file(path: Path) -> bool:
    """检查文件是否为敏感文件（凭据、密钥等）。"""
    name = path.name.lower()

    # 精确匹配
    if name in SENSITIVE_NAMES:
        return True

    # 后缀匹配
    if path.suffix.lower() in SENSITIVE_SUFFIXES:
        return True

    return False


def is_temp_file(path: Path) -> bool:
    """检查文件是否为临时文件或缓存。"""
    # 后缀匹配
    if path.suffix.lower() in TEMP_SUFFIXES:
        return True

    # 路径组件匹配
    if any(part in TEMP_DIRS for part in path.parts):
        return True

    return False


def collect_skill_files(skill_name: str, skills_dir: Path) -> list[Path]:
    """收集并验证 skill 目录下的所有可分发文件。

    Args:
        skill_name: skill 名称（必须是合法目录名）
        skills_dir: 技能根目录

    Returns:
        验证通过的文件列表（相对于 skill 目录的路径）

    Raises:
        ValueError: 如果验证失败
    """
    # 1. 验证 skill 名称
    validate_skill_name(skill_name)

    skill_src = skills_dir / skill_name

    # 2. 检查目录存在
    if not skill_src.is_dir():
        raise ValueError(f"skill 目录不存在：{skill_src}")

    # 3. 解析真实路径，防止路径穿越
    real_skill_src = skill_src.resolve()
    real_skills_dir = skills_dir.resolve()

    # 确认解析后的路径仍在技能根目录内
    if real_skill_src != real_skills_dir and real_skills_dir not in real_skill_src.parents:
        raise ValueError(f"skill 目录越界（路径穿越）：{skill_name}")

    # 4. 递归收集文件
    files = []
    for item in real_skill_src.rglob("*"):
        if not item.is_file():
            continue

        # 检查符号链接（rglob 已经解析，但再检查原始路径）
        original_item = skill_src / item.relative_to(real_skill_src)
        if original_item.is_symlink():
            raise ValueError(f"skill 目录内不允许符号链接：{original_item}")

        # 检查敏感文件
        if is_sensitive_file(item):
            raise ValueError(f"skill 目录包含敏感文件：{item.relative_to(real_skill_src)}")

        # 跳过临时文件
        if is_temp_file(item):
            continue

        # 计算相对路径
        rel_path = item.relative_to(real_skill_src)
        files.append(rel_path)

    return files


def check_skill_files(skill_name: str, skills_dir: Path) -> list[str]:
    """检查 skill 文件并返回错误列表（不抛出异常）。

    用于 check.py 的静态检查。

    Returns:
        错误消息列表（空列表表示通过）
    """
    errors = []
    try:
        collect_skill_files(skill_name, skills_dir)
    except ValueError as e:
        errors.append(str(e))
    return errors
