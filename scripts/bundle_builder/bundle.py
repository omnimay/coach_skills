"""通用 bundle 配置读取、校验和 ZIP 组装（RFC-0003 + RFC-0006）。"""
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any, NamedTuple, NoReturn

# 添加 scripts/ 到路径以便导入 file_validator
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import file_validator  # pyright: ignore[reportMissingImports]

# 严格 SemVer 2.0.0（RFC-0006 §4）：
#   MAJOR.MINOR.PATCH[-prerelease][+build]
#   prerelease: 点分隔标识符，每个为非空 [0-9A-Za-z-]；纯数字标识符不得有前导零
#   build: 点分隔标识符，每个为非空 [0-9A-Za-z-]
_ID = r"[0-9A-Za-z-]+"
_PRERELEASE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = _ID
_STRICT_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>" + _PRERELEASE_ID + r"(?:\." + _PRERELEASE_ID + r")*))?"
    r"(?:\+(?P<build>" + _BUILD_ID + r"(?:\." + _BUILD_ID + r")*))?$"
)
# 宽松正则用于 bundle id / 其他不需严格校验的场景
BUNDLE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
PLACEHOLDER_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


class SemVer(NamedTuple):
    """解析后的语义化版本号。build 不参与比较。"""

    major: int
    minor: int
    patch: int
    prerelease: tuple[str | int, ...]  # 纯数字标识符存为 int（排序用）
    build: tuple[str, ...]


def parse_semver(version: str) -> SemVer:
    """解析严格 SemVer 字符串；不符合规范时抛出 ValueError。"""
    m = _STRICT_SEMVER_RE.match(version)
    if not m:
        raise ValueError(f"不是合法 SemVer 2.0.0：{version!r}")
    major, minor, patch = int(m.group("major")), int(m.group("minor")), int(m.group("patch"))
    prerelease_raw = m.group("prerelease") or ""
    prerelease: list[str | int] = []
    if prerelease_raw:
        for seg in prerelease_raw.split("."):
            if seg.isdigit():
                prerelease.append(int(seg))
            else:
                prerelease.append(seg)
    build_raw = m.group("build") or ""
    build = tuple(build_raw.split(".")) if build_raw else ()
    return SemVer(major, minor, patch, tuple(prerelease), build)


def compare_versions(a: str, b: str) -> int:
    """比较两个 SemVer 字符串（build 不参与比较）。

    返回: -1 (a < b), 0 (a == b), 1 (a > b)。
    不符合规范时抛出 ValueError。
    """
    va, vb = parse_semver(a), parse_semver(b)
    # major.minor.patch
    for x, y in [(va.major, vb.major), (va.minor, vb.minor), (va.patch, vb.patch)]:
        if x < y:
            return -1
        if x > y:
            return 1
    # prerelease：无 prerelease > 有 prerelease（正式版 > 预发布）
    pa, pb = va.prerelease, vb.prerelease
    if not pa and not pb:
        return 0
    if not pa:
        return 1
    if not pb:
        return -1
    # 按标识符逐个比较
    for i in range(min(len(pa), len(pb))):
        sa, sb_ = pa[i], pb[i]
        if sa == sb_:
            continue
        # 类型不同：int < str（SemVer 规范 §11.4.3）
        if isinstance(sa, int) and isinstance(sb_, str):
            return -1
        if isinstance(sa, str) and isinstance(sb_, int):
            return 1
        # 同类型直接比较
        if isinstance(sa, int) and isinstance(sb_, int):
            return -1 if sa < sb_ else 1
        # 此时 sa 和 sb_ 都是 str
        return -1 if sa < sb_ else 1  # pyright: ignore[reportOperatorIssue]
    # 所有公共标识符相同，较长者更大
    if len(pa) < len(pb):
        return -1
    if len(pa) > len(pb):
        return 1
    return 0


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

    # semver（严格 SemVer 2.0.0，含 prerelease 段校验）
    version = bundle["version"]
    if not isinstance(version, str):
        fail("bundle.json 校验失败：'version' 必须是字符串")
    try:
        parse_semver(version)
    except ValueError:
        fail(f"bundle.json 校验失败：'version' 不是合法 SemVer 2.0.0：'{version}'")

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
    icon_path = (bundle_dir / icon).resolve()
    # 防止路径穿越：确保 icon 路径在 bundle_dir 内
    try:
        icon_path.relative_to(bundle_dir.resolve())
    except ValueError:
        fail(f"bundle.json 校验失败：icon 路径非法（包含路径穿越）：{icon}")
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
