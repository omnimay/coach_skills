"""通用 bundle 配置读取、校验和 ZIP 组装（RFC-0003）。"""
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any, NoReturn

# 添加 scripts/ 到路径以便导入 file_validator
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import file_validator  # pyright: ignore[reportMissingImports]

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?$")
BUNDLE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
PLACEHOLDER_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def load_environments(env_file: Path) -> dict[str, dict[str, str]]:
    """读取 environments.json，返回 {env_name: {VAR: value}}。"""
    if not env_file.is_file():
        fail(f"环境配置文件不存在：{env_file}")
    try:
        return json.loads(env_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"环境配置文件格式错误：{e}")


def resolve_placeholders(bundle: dict[str, Any], env_vars: dict[str, str]) -> dict[str, Any]:
    """递归替换 bundle 中的 ${VAR} 占位符。"""
    def _replace(obj: Any) -> Any:
        if isinstance(obj, str):
            def _sub(m: re.Match) -> str:
                var = m.group(1)
                if var not in env_vars:
                    fail(f"环境变量未定义：${{{var}}}（可用：{', '.join(env_vars.keys())}）")
                return env_vars[var]
            return PLACEHOLDER_RE.sub(_sub, obj)
        if isinstance(obj, dict):
            return {k: _replace(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_replace(item) for item in obj]
        return obj
    return _replace(bundle)


def fail(message: str) -> NoReturn:
    """统一错误输出并退出。"""
    sys.exit(f"ERROR: {message}")


def load_bundle(bundle_dir: Path) -> dict[str, Any]:
    """读取并解析 bundle.json 为 dict。"""
    bundle_json = bundle_dir / "bundle.json"
    if not bundle_json.is_file():
        fail(f"bundle.json 不存在：{bundle_json}")
    try:
        return json.loads(bundle_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"bundle.json 格式错误：{e}")


def validate_bundle(bundle: dict[str, Any]) -> None:
    """校验 bundle.json schema（必填字段、类型、semver、locale）。"""
    # 必填字段
    for field in ("id", "version", "skills", "presentation", "mcp"):
        if field not in bundle or bundle[field] is None:
            fail(f"bundle.json 校验失败：缺少必填字段 '{field}'")

    # bundle ID 格式：单段安全名称，防止路径遍历
    bundle_id = bundle["id"]
    if not isinstance(bundle_id, str) or not BUNDLE_ID_RE.match(bundle_id):
        fail(f"bundle.json 校验失败：'id' 只能是字母、数字、连字符、下划线、点，且不能以特殊字符开头：'{bundle_id}'")

    # semver
    version = bundle["version"]
    if not isinstance(version, str) or not SEMVER_RE.match(version):
        fail(f"bundle.json 校验失败：'version' 不是合法 semver：'{version}'")

    # skills 类型
    if not isinstance(bundle["skills"], list):
        fail("bundle.json 校验失败：'skills' 必须是数组")

    # presentation 校验
    pres = bundle.get("presentation", {})
    if not isinstance(pres, dict):
        fail("bundle.json 校验失败：'presentation' 必须是对象")
    default_locale = pres.get("defaultLocale")
    if not default_locale:
        fail("bundle.json 校验失败：缺少 'presentation.defaultLocale'")
    locales = pres.get("locales", {})
    if default_locale not in locales:
        fail(f"bundle.json 校验失败：defaultLocale '{default_locale}' 对应的 locale 条目缺失")

    # icon 字段存在性检查
    icon = pres.get("icon")
    if not icon:
        fail("bundle.json 校验失败：缺少 'presentation.icon'")


def validate_bundle_icon(bundle: dict[str, Any], bundle_dir: Path) -> None:
    """校验 icon 文件存在且非空。"""
    icon = bundle.get("presentation", {}).get("icon", "")
    icon_path = bundle_dir / icon
    if not icon_path.is_file():
        fail(f"bundle.json 校验失败：icon 文件不存在：{icon}")
    if icon_path.stat().st_size == 0:
        fail(f"bundle.json 校验失败：icon 文件为空：{icon}")


def resolve_skills(bundle: dict[str, Any], skills_dir: Path) -> dict[str, list[Path]]:
    """验证每个 skill 目录存在并收集文件。返回 {skill_name: [relative_paths]}。"""
    result: dict[str, list[Path]] = {}
    for name in bundle["skills"]:
        if not isinstance(name, str):
            fail(f"bundle.json 校验失败：skill 条目不是字符串：{name}")
        try:
            file_validator.validate_skill_name(name)
        except ValueError as e:
            fail(f"skill 名称不合法：{e}")
        skill_dir = skills_dir / name
        if not skill_dir.is_dir():
            fail(f"skill 目录不存在：skills/{name}")
        try:
            rel_files = file_validator.collect_skill_files(name, skills_dir)
        except ValueError as e:
            fail(f"skill {name} 文件校验失败：{e}")
        result[name] = rel_files
    return result


def write_zip(zpath: Path, entries: dict[Path, bytes]) -> None:
    """确定性 zip：排序 + 固定时间戳 + 固定权限。原子写入。"""
    tmp_path = zpath.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(entries.keys()):
            info = zipfile.ZipInfo(str(name), date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, entries[name])
    tmp_path.replace(zpath)
