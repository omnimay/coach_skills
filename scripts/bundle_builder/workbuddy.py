"""WorkBuddy 平台字段映射和校验（RFC-0003）。"""
import sys
from typing import Any, NoReturn


def fail(message: str) -> NoReturn:
    """统一错误输出并退出。"""
    sys.exit(f"ERROR: {message}")


def _locale_field(locales: dict, locale: str, field: str) -> Any:
    """从 locales 中获取指定语言的字段的值，不存在时返回 None。空数组返回 []。"""
    entry = locales.get(locale)
    if entry is None:
        return None
    return entry.get(field)


def generate_connector_meta(bundle: dict[str, Any]) -> dict[str, Any]:
    """从 bundle dict 生成 connector-meta.json 内容（返回 dict，不写磁盘）。"""
    pres = bundle["presentation"]
    locales = pres["locales"]
    default_locale = pres["defaultLocale"]
    wb = bundle["targets"]["workbuddy"]

    meta: dict[str, Any] = {}

    # name（无后缀 = defaultLocale）
    meta["name"] = locales[default_locale]["name"]

    # name_zh / name_en
    name_zh = _locale_field(locales, "zh-CN", "name")
    if name_zh is not None:
        meta["name_zh"] = name_zh
    name_en = _locale_field(locales, "en", "name")
    if name_en is not None:
        meta["name_en"] = name_en

    # description（无后缀 = defaultLocale）
    meta["description"] = locales[default_locale]["description"]

    # description_zh / description_en
    desc_zh = _locale_field(locales, "zh-CN", "description")
    if desc_zh is not None:
        meta["description_zh"] = desc_zh
    desc_en = _locale_field(locales, "en", "description")
    if desc_en is not None:
        meta["description_en"] = desc_en

    # examples_zh / examples_en
    ex_zh = _locale_field(locales, "zh-CN", "examples")
    if ex_zh is not None:
        meta["examples_zh"] = ex_zh
    ex_en = _locale_field(locales, "en", "examples")
    if ex_en is not None:
        meta["examples_en"] = ex_en

    # 平台字段
    meta["source"] = wb["source"]
    meta["type"] = wb["type"]
    meta["minWorkbuddyVersion"] = wb["minVersion"]

    # 版本注入
    meta["version"] = bundle["version"]

    return meta


def generate_mcp_json(bundle: dict[str, Any]) -> dict[str, Any]:
    """从 bundle dict 生成 mcp.json 内容（返回 dict，不写磁盘）。"""
    servers = bundle["mcp"]["servers"]
    result: dict[str, Any] = {"mcpServers": {}}
    for name, conf in servers.items():
        result["mcpServers"][name] = {
            "type": _transport_to_type(conf.get("transport", "")),
            "url": conf["url"],
        }
    return result


def _transport_to_type(transport: str) -> str:
    """将通用 transport 名称转换为 WorkBuddy 的 type 字段。"""
    mapping = {
        "streamable-http": "streamableHttp",
        "sse": "sse",
    }
    return mapping.get(transport, transport)


def validate_workbuddy(bundle: dict[str, Any]) -> None:
    """WorkBuddy 平台约束校验。"""
    # 检查 targets.workbuddy 及其必填字段（generate_connector_meta 依赖）
    targets = bundle.get("targets")
    if not isinstance(targets, dict):
        fail("WorkBuddy 校验失败：缺少 'targets' 字段")
    wb = targets.get("workbuddy")
    if not isinstance(wb, dict):
        fail("WorkBuddy 校验失败：缺少 'targets.workbuddy' 字段")
    for field in ("source", "type", "minVersion"):
        if field not in wb:
            fail(f"WorkBuddy 校验失败：'targets.workbuddy.{field}' 缺失")
        if not isinstance(wb[field], str) or not wb[field]:
            fail(f"WorkBuddy 校验失败：'targets.workbuddy.{field}' 必须是非空字符串")

    # MCP server 校验
    servers = bundle.get("mcp", {}).get("servers", {})
    if not isinstance(servers, dict):
        fail("bundle.json 校验失败：'mcp.servers' 必须是对象")
    if len(servers) == 0:
        fail("WorkBuddy 校验失败：mcp.servers 为空")
    if len(servers) > 1:
        fail(
            f"WorkBuddy 校验失败：mcp.servers 只能有一个 server，"
            f"发现 {len(servers)} 个：{', '.join(servers.keys())}"
        )

    name, conf = next(iter(servers.items()))
    if not isinstance(conf, dict):
        fail(f"WorkBuddy 校验失败：mcp.servers.{name} 格式错误")
    url = conf.get("url", "")
    if not isinstance(url, str):
        fail(f"WorkBuddy 校验失败：mcp.servers.{name}.url 必须是字符串")
    # 占位符 ${...} 跳过 HTTPS 检查，打包时解析
    if url.startswith("${") and url.endswith("}"):
        return
    if not url.startswith("https://"):
        fail(f"WorkBuddy 校验失败：mcp.servers.{name}.url 必须是 HTTPS 地址")
