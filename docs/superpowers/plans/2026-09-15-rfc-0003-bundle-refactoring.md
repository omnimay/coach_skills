# RFC-0003: 技能包 Bundle 化重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将技能包配置从平台绑定的 `.workbuddy-plugin/` 目录结构迁移到平台无关的 `bundles/` 目录，引入 `bundle.json` 作为通用定义，平台原生文件由构建生成。

**Architecture:** 三层解耦——Skill 是能力（`skills/`），Bundle 是交付组合（`bundles/<name>/bundle.json`），Target 是平台格式（`scripts/packaging/<platform>.py`）。`bundle.json` 是单一权威来源，`pack.py` 和 `check.py` 共享 `packaging/` 模块的校验逻辑。

**Tech Stack:** Python 3, pytest, zipfile

**CRITICAL: 不执行任何 git 写操作（不 add/commit/push）。**

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `bundles/sales-coach/bundle.json` | 创建 | 通用 bundle 定义（组合、版本、展示、连接、平台目标） |
| `bundles/sales-coach/icon.svg` | 复制 | 从 `.workbuddy-plugin/sales-coach/icon.svg` 复制 |
| `scripts/packaging/__init__.py` | 创建 | 空文件，使 packaging 成为常规包 |
| `scripts/packaging/bundle.py` | 创建 | 通用层：load_bundle, validate_bundle, resolve_skills, write_zip, SEMVER_RE |
| `scripts/packaging/workbuddy.py` | 创建 | 平台层：generate_connector_meta, generate_mcp_json, validate_workbuddy |
| `scripts/pack.py` | 重写 | 调用 packaging 模块，新 CLI（--bundle, --target） |
| `scripts/check.py` | 修改 | check_manifests 改为读 bundles/，导入 bundle.py 的 SEMVER_RE |
| `tests/test_bundle.py` | 创建 | bundle.json schema 校验测试 |
| `tests/test_workbuddy.py` | 创建 | 字段映射和平台校验测试 |
| `tests/test_pack.py` | 重写 | fixture 从 plugin_repo 改为 bundle_repo |
| `.mcp.json` | 删除 | 冗余配置 |
| `assets/icon.svg` | 删除 | 旧版本图标 |
| `.workbuddy-plugin/` | 删除 | 旧平台目录 |

---

### Task 1: 创建 bundle 结构和 bundle.json

**Files:**
- Create: `bundles/sales-coach/bundle.json`
- Create: `bundles/sales-coach/icon.svg`（从现有文件复制）
- Delete: `.mcp.json`
- Delete: `assets/icon.svg`

- [ ] **Step 1: 创建 bundles 目录和 bundle.json**

```bash
mkdir -p bundles/sales-coach
```

创建 `bundles/sales-coach/bundle.json`：

```json
{
  "schemaVersion": 1,
  "id": "sales-coach",
  "version": "0.1.0",
  "skills": [
    "ai_customer_design",
    "coach-mcp-connect"
  ],
  "presentation": {
    "defaultLocale": "zh-CN",
    "locales": {
      "zh-CN": {
        "name": "深维智讯・销售陪练",
        "description": "AI 销售陪练与智能评测，支持场景化角色扮演、实时对话练习与能力分析，帮助销售快速提升实战沟通能力。",
        "examples": [
          "创建一个销售沟通训练课程",
          "模拟客户进行角色扮演练习"
        ]
      },
      "en": {
        "name": "Sales Coach",
        "description": "AI sales sparring and intelligent assessment with scenario-based role play, real-time dialogue practice and capability analysis.",
        "examples": [
          "Create a sales conversation training course",
          "Practice role play with a simulated customer"
        ]
      }
    },
    "icon": "icon.svg"
  },
  "mcp": {
    "servers": {
      "enterprise-training": {
        "transport": "streamable-http",
        "url": "https://mcp.test.omnimay.com/coach/mcp"
      }
    }
  },
  "targets": {
    "workbuddy": {
      "source": "sales-coach",
      "type": "mcp",
      "minVersion": "4.24.0"
    }
  }
}
```

注意：`description` 字段的值来自现有 `connector-meta.json` 的 `description_zh`（中文）和 `description_en`（英文），而非 `description` 字段（那个是英文但内容不同于 `description_en`）。`examples` 来自 `examples_zh` 和 `examples_en`。

- [ ] **Step 2: 复制 icon.svg**

```bash
cp .workbuddy-plugin/sales-coach/icon.svg bundles/sales-coach/icon.svg
```

- [ ] **Step 3: 删除冗余文件**

```bash
rm .mcp.json
rm assets/icon.svg
```

- [ ] **Step 4: 验证 bundle.json 格式**

```bash
python3 -c "import json; json.load(open('bundles/sales-coach/bundle.json')); print('OK')"
```

Expected: `OK`

---

### Task 2: 实现 scripts/packaging/bundle.py

**Files:**
- Create: `scripts/packaging/__init__.py`
- Create: `scripts/packaging/bundle.py`
- Test: `tests/test_bundle.py`

- [ ] **Step 1: 创建 packaging 包**

```bash
mkdir -p scripts/packaging
```

创建 `scripts/packaging/__init__.py`（空文件）：

```python
```

- [ ] **Step 2: 编写 test_bundle.py 的失败测试**

创建 `tests/test_bundle.py`：

```python
"""bundle.py 测试（RFC-0003 §7）。"""
import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from packaging.bundle import load_bundle, validate_bundle, resolve_skills, SEMVER_RE


@pytest.fixture
def bundle_dir(tmp_path):
    """创建最小有效 bundle。"""
    skills_dir = tmp_path / "skills" / "test-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("---\nname: test\ndescription: test\n---\nbody")

    bundle_path = tmp_path / "bundles" / "test-bundle"
    bundle_path.mkdir(parents=True)
    (bundle_path / "icon.svg").write_text("<svg></svg>")
    return tmp_path


def make_bundle(tmp_path, overrides=None):
    """创建 bundle.json 并写入。"""
    data = {
        "schemaVersion": 1,
        "id": "test-bundle",
        "version": "1.0.0",
        "skills": ["test-skill"],
        "presentation": {
            "defaultLocale": "zh-CN",
            "locales": {
                "zh-CN": {
                    "name": "Test",
                    "description": "Test desc",
                    "examples": ["ex1"]
                }
            },
            "icon": "icon.svg"
        },
        "mcp": {
            "servers": {
                "test-server": {
                    "transport": "streamable-http",
                    "url": "https://mcp.example.com/mcp"
                }
            }
        },
        "targets": {
            "workbuddy": {
                "source": "test-bundle",
                "type": "mcp",
                "minVersion": "4.24.0"
            }
        }
    }
    if overrides:
        data.update(overrides)
    bundle_path = tmp_path / "bundles" / "test-bundle"
    (bundle_path / "bundle.json").write_text(json.dumps(data, ensure_ascii=False))
    return bundle_path


class TestSemverRe:
    def test_valid(self):
        assert SEMVER_RE.match("1.0.0")
        assert SEMVER_RE.match("0.1.0")
        assert SEMVER_RE.match("1.0.0-rc.1")

    def test_invalid(self):
        assert not SEMVER_RE.match("abc")
        assert not SEMVER_RE.match("1.0")
        assert not SEMVER_RE.match("")


class TestLoadBundle:
    def test_load_valid(self, bundle_dir):
        bp = make_bundle(bundle_dir)
        bundle = load_bundle(bp)
        assert bundle["id"] == "test-bundle"
        assert bundle["version"] == "1.0.0"

    def test_load_missing(self, tmp_path):
        with pytest.raises(SystemExit):
            load_bundle(tmp_path / "bundles" / "nonexistent")


class TestValidateBundle:
    def test_valid(self, bundle_dir):
        bp = make_bundle(bundle_dir)
        bundle = load_bundle(bp)
        validate_bundle(bundle)  # 不抛异常即通过

    def test_missing_version(self, bundle_dir):
        bp = make_bundle(bundle_dir, overrides={"version": None})
        # 删除 version key
        data = json.loads((bp / "bundle.json").read_text())
        del data["version"]
        (bp / "bundle.json").write_text(json.dumps(data))
        bundle = load_bundle(bp)
        with pytest.raises(SystemExit, match="version"):
            validate_bundle(bundle)

    def test_invalid_semver(self, bundle_dir):
        bp = make_bundle(bundle_dir, overrides={"version": "abc"})
        bundle = load_bundle(bp)
        with pytest.raises(SystemExit, match="semver"):
            validate_bundle(bundle)

    def test_missing_default_locale(self, bundle_dir):
        bp = make_bundle(bundle_dir)
        data = json.loads((bp / "bundle.json").read_text())
        data["presentation"]["defaultLocale"] = "fr"
        (bp / "bundle.json").write_text(json.dumps(data, ensure_ascii=False))
        bundle = load_bundle(bp)
        with pytest.raises(SystemExit, match="defaultLocale"):
            validate_bundle(bundle)

    def test_missing_icon(self, bundle_dir):
        bp = make_bundle(bundle_dir)
        (bp / "icon.svg").unlink()
        bundle = load_bundle(bp)
        with pytest.raises(SystemExit, match="icon"):
            validate_bundle(bundle)


class TestResolveSkills:
    def test_valid(self, bundle_dir):
        bp = make_bundle(bundle_dir)
        bundle = load_bundle(bp)
        skills_dir = bundle_dir / "skills"
        files = resolve_skills(bundle, skills_dir)
        assert "test-skill" in files

    def test_missing_skill_dir(self, bundle_dir):
        bp = make_bundle(bundle_dir, overrides={"skills": ["nonexistent"]})
        bundle = load_bundle(bp)
        skills_dir = bundle_dir / "skills"
        with pytest.raises(SystemExit, match="nonexistent"):
            resolve_skills(bundle, skills_dir)
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd /home/zoushen/projects/21coachskills/coachskills && python3 -m pytest tests/test_bundle.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packaging.bundle'`

- [ ] **Step 4: 实现 bundle.py**

创建 `scripts/packaging/bundle.py`：

```python
"""通用 bundle 配置读取、校验和 ZIP 组装（RFC-0003）。"""
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any, NoReturn

# 添加 scripts/ 到路径以便导入 file_validator
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import file_validator

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?$")
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def fail(message: str) -> NoReturn:
    """统一错误输出并退出。"""
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


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

    # icon 文件校验（由调用方传入 bundle_dir，此处只做字段存在性检查）
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
    result = {}
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
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /home/zoushen/projects/21coachskills/coachskills && python3 -m pytest tests/test_bundle.py -v`
Expected: All PASS

---

### Task 3: 实现 scripts/packaging/workbuddy.py

**Files:**
- Create: `scripts/packaging/workbuddy.py`
- Test: `tests/test_workbuddy.py`

- [ ] **Step 1: 编写 test_workbuddy.py 的失败测试**

创建 `tests/test_workbuddy.py`：

```python
"""workbuddy.py 测试（RFC-0003 §7）。"""
import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from packaging.workbuddy import (
    generate_connector_meta,
    generate_mcp_json,
    validate_workbuddy,
    _locale_field,
)


def make_bundle(**overrides):
    """创建最小有效 bundle dict。"""
    data = {
        "schemaVersion": 1,
        "id": "test-bundle",
        "version": "1.0.0",
        "skills": ["test-skill"],
        "presentation": {
            "defaultLocale": "zh-CN",
            "locales": {
                "zh-CN": {
                    "name": "测试包",
                    "description": "测试描述",
                    "examples": ["示例1"]
                },
                "en": {
                    "name": "Test Bundle",
                    "description": "Test description",
                    "examples": ["Example 1"]
                }
            },
            "icon": "icon.svg"
        },
        "mcp": {
            "servers": {
                "test-server": {
                    "transport": "streamable-http",
                    "url": "https://mcp.example.com/mcp"
                }
            }
        },
        "targets": {
            "workbuddy": {
                "source": "test-bundle",
                "type": "mcp",
                "minVersion": "4.24.0"
            }
        }
    }
    # 深度合并 overrides
    for key, val in overrides.items():
        if isinstance(val, dict) and key in data and isinstance(data[key], dict):
            data[key].update(val)
        else:
            data[key] = val
    return data


class TestLocaleField:
    def test_existing_locale(self):
        locales = {"zh-CN": {"name": "中文"}}
        assert _locale_field(locales, "zh-CN", "name") == "中文"

    def test_missing_locale(self):
        locales = {"zh-CN": {"name": "中文"}}
        assert _locale_field(locales, "en", "name") is None

    def test_missing_field(self):
        locales = {"zh-CN": {}}
        assert _locale_field(locales, "zh-CN", "name") is None

    def test_empty_examples(self):
        locales = {"zh-CN": {"examples": []}}
        assert _locale_field(locales, "zh-CN", "examples") == []


class TestGenerateConnectorMeta:
    def test_basic_mapping(self):
        bundle = make_bundle()
        meta = generate_connector_meta(bundle)
        assert meta["name"] == "测试包"  # defaultLocale = zh-CN
        assert meta["name_zh"] == "测试包"
        assert meta["name_en"] == "Sales Coach" or meta["name_en"] == "Test Bundle"
        assert meta["type"] == "mcp"
        assert meta["source"] == "test-bundle"
        assert meta["minWorkbuddyVersion"] == "4.24.0"

    def test_version_injection(self):
        bundle = make_bundle()
        meta = generate_connector_meta(bundle)
        assert meta["version"] == "1.0.0"

    def test_missing_en_locale(self):
        bundle = make_bundle(presentation={
            "defaultLocale": "zh-CN",
            "locales": {"zh-CN": {"name": "中文", "description": "描述", "examples": []}},
            "icon": "icon.svg"
        })
        meta = generate_connector_meta(bundle)
        assert meta["name"] == "中文"
        assert meta["name_zh"] == "中文"
        assert "name_en" not in meta
        assert "description_en" not in meta

    def test_empty_examples_preserved(self):
        bundle = make_bundle(presentation={
            "defaultLocale": "zh-CN",
            "locales": {
                "zh-CN": {"name": "中文", "description": "描述", "examples": []},
                "en": {"name": "English", "description": "Desc", "examples": []}
            },
            "icon": "icon.svg"
        })
        meta = generate_connector_meta(bundle)
        assert meta["examples_zh"] == []
        assert meta["examples_en"] == []


class TestGenerateMcpJson:
    def test_basic_mapping(self):
        bundle = make_bundle()
        mcp = generate_mcp_json(bundle)
        servers = mcp["mcpServers"]
        assert "test-server" in servers
        assert servers["test-server"]["type"] == "streamableHttp"
        assert servers["test-server"]["url"] == "https://mcp.example.com/mcp"


class TestValidateWorkbuddy:
    def test_valid(self):
        bundle = make_bundle()
        validate_workbuddy(bundle)  # 不抛异常

    def test_multiple_servers(self):
        bundle = make_bundle(mcp={
            "servers": {
                "s1": {"transport": "streamable-http", "url": "https://a.com/mcp"},
                "s2": {"transport": "streamable-http", "url": "https://b.com/mcp"},
            }
        })
        with pytest.raises(SystemExit, match="一个"):
            validate_workbuddy(bundle)

    def test_non_https(self):
        bundle = make_bundle(mcp={
            "servers": {
                "s1": {"transport": "streamable-http", "url": "http://a.com/mcp"},
            }
        })
        with pytest.raises(SystemExit, match="HTTPS"):
            validate_workbuddy(bundle)

    def test_no_servers(self):
        bundle = make_bundle(mcp={"servers": {}})
        with pytest.raises(SystemExit, match="为空"):
            validate_workbuddy(bundle)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_workbuddy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packaging.workbuddy'`

- [ ] **Step 3: 实现 workbuddy.py**

创建 `scripts/packaging/workbuddy.py`：

```python
"""WorkBuddy 平台字段映射和校验（RFC-0003）。"""
import sys
from pathlib import Path
from typing import Any, NoReturn


def fail(message: str) -> NoReturn:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


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
    servers = bundle.get("mcp", {}).get("servers", {})
    if not isinstance(servers, dict):
        fail("bundle.json 校验失败：'mcp.servers' 必须是对象")
    if len(servers) == 0:
        fail("WorkBuddy 校验失败：mcp.servers 为空")
    if len(servers) > 1:
        fail(f"WorkBuddy 校验失败：mcp.servers 只能有一个 server，发现 {len(servers)} 个：{', '.join(servers.keys())}")

    name, conf = next(iter(servers.items()))
    if not isinstance(conf, dict):
        fail(f"WorkBuddy 校验失败：mcp.servers.{name} 格式错误")
    url = conf.get("url", "")
    if not isinstance(url, str) or not url.startswith("https://"):
        fail(f"WorkBuddy 校验失败：mcp.servers.{name}.url 必须是 HTTPS 地址")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_workbuddy.py -v`
Expected: All PASS

---

### Task 4: 重构 pack.py

**Files:**
- Modify: `scripts/pack.py`

- [ ] **Step 1: 重写 pack.py**

完整重写 `scripts/pack.py`：

```python
#!/usr/bin/env python3
"""Bundle 打包脚本（RFC-0003）。

从 bundles/<bundle>/ 配置生成平台特定的 zip 包。

用法：
    python3 scripts/pack.py                                    # 打包所有 bundle（默认 workbuddy）
    python3 scripts/pack.py --bundle sales-coach               # 打包指定 bundle
    python3 scripts/pack.py --bundle sales-coach --target workbuddy  # 指定目标平台
    python3 scripts/pack.py --out dist/workbuddy               # 指定输出目录
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from packaging.bundle import load_bundle, validate_bundle, validate_bundle_icon, resolve_skills, write_zip
from packaging.workbuddy import generate_connector_meta, generate_mcp_json, validate_workbuddy

REPO = Path.cwd()
BUNDLES_DIR = REPO / "bundles"
SKILLS_DIR = REPO / "skills"


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


def pack_bundle(bundle_dir: Path, target: str, out_dir: Path) -> str:
    """打包单个 bundle 到指定目标平台，返回 zip 文件名。"""
    bundle = load_bundle(bundle_dir)
    validate_bundle(bundle)
    validate_bundle_icon(bundle, bundle_dir)
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
    zip_name = f"{bundle_name}-v{version}.zip"

    entries: dict[Path, bytes] = {}

    # connector-meta.json
    entries[Path("connector-meta.json")] = json.dumps(
        connector_meta, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"

    # mcp.json
    entries[Path("mcp.json")] = json.dumps(
        mcp_json, ensure_ascii=False, indent=2, sort_keys=True
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
        "--bundle", action="append", dest="bundles",
        help="指定要打包的 bundle（可多次指定；默认打包所有）"
    )
    parser.add_argument(
        "--target", default="workbuddy",
        help="目标平台（默认 workbuddy）"
    )
    parser.add_argument(
        "--out", default="dist/workbuddy",
        help="输出目录（默认 dist/workbuddy）"
    )
    args = parser.parse_args()

    out_dir = REPO / args.out
    bundles = discover_bundles(args.bundles)

    packed = []
    for bundle_dir in bundles:
        zip_name = pack_bundle(bundle_dir, args.target, out_dir)
        packed.append(zip_name)
        print(f"✓ {bundle_dir.name} → {args.out}/{zip_name}")

    print(f"\n打包完成：{len(packed)} 个 bundle → {args.out}/")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行打包测试**

```bash
cd /home/zoushen/projects/21coachskills/coachskills && python3 scripts/pack.py --bundle sales-coach --target workbuddy --out dist/workbuddy-test
```

Expected: `✓ sales-coach → dist/workbuddy-test/sales-coach-v0.1.0.zip`

- [ ] **Step 3: 语义对比 ZIP 内容**

```bash
# 解压新旧 ZIP 并对比 connector-meta.json
cd /home/zoushen/projects/21coachskills/coachskills
mkdir -p /tmp/old-zip /tmp/new-zip
cd /tmp/old-zip && unzip -o /home/zoushen/projects/21coachskills/coachskills/dist/workbuddy/sales-coach-v0.1.0.zip
cd /tmp/new-zip && unzip -o /home/zoushen/projects/21coachskills/coachskills/dist/workbuddy-test/sales-coach-v0.1.0.zip
# 语义对比（jq -S 排序 key）
diff <(jq -S . /tmp/old-zip/connector-meta.json) <(jq -S . /tmp/new-zip/connector-meta.json) && echo "connector-meta.json: OK"
diff <(jq -S . /tmp/old-zip/mcp.json) <(jq -S . /tmp/new-zip/mcp.json) && echo "mcp.json: OK"
diff /tmp/old-zip/icon.svg /tmp/new-zip/icon.svg && echo "icon.svg: OK"
diff -r /tmp/old-zip/skills /tmp/new-zip/skills && echo "skills/: OK"
```

Expected: 全部 OK（语义一致）

- [ ] **Step 4: 清理测试产物**

```bash
rm -rf dist/workbuddy-test /tmp/old-zip /tmp/new-zip
```

---

### Task 5: 重构 check.py

**Files:**
- Modify: `scripts/check.py`（仅 `check_manifests` 函数 + imports + 删除 SEMVER_RE）

- [ ] **Step 1: 修改 check.py 的 imports**

在 `scripts/check.py` 中：
- 删除 `SEMVER_RE = re.compile(...)` 行
- 删除 `PLUGIN_DIR = REPO / ".workbuddy-plugin"` 行
- 添加 `BUNDLES_DIR = REPO / "bundles"` 常量
- 在 `sys.path.insert` 后添加：`from packaging.bundle import load_bundle, validate_bundle, validate_bundle_icon, SEMVER_RE` 和 `from packaging.workbuddy import validate_workbuddy`

具体修改：

找到并删除：
```python
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?$")
```

找到并删除：
```python
PLUGIN_DIR = REPO / ".workbuddy-plugin"
```

在其位置添加：
```python
BUNDLES_DIR = REPO / "bundles"
```

在 `import file_validator` 后添加：
```python
from packaging.bundle import load_bundle, validate_bundle, validate_bundle_icon, SEMVER_RE
from packaging.workbuddy import validate_workbuddy
```

- [ ] **Step 2: 重写 check_manifests 函数**

替换整个 `check_manifests` 函数：

```python
def check_manifests(full):
    """校验 bundles/ 下每个 bundle 的 bundle.json。"""
    if not BUNDLES_DIR.is_dir():
        if full:
            fail("MANIFESTS", str(BUNDLES_DIR), "bundles 目录缺失")
        return

    bundles = [d for d in BUNDLES_DIR.iterdir() if d.is_dir() and d.name != "__pycache__" and (d / "bundle.json").is_file()]
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
```

- [ ] **Step 3: 运行 check.py 确认通过**

```bash
cd /home/zoushen/projects/21coachskills/coachskills && python3 scripts/check.py
```

Expected: `check.py: OK（...）`，exit 0

注意：此时 `.workbuddy-plugin/` 仍然存在但不再被 check.py 读取。bundles/ 目录已在 Task 1 创建。

---

### Task 6: 更新测试和清理

**Files:**
- Rewrite: `tests/test_pack.py`
- Modify: `tests/test_check.py`（新增 manifests 测试）
- Delete: `.workbuddy-plugin/`（整个目录）
- Modify: `README.md`
- Modify: `docs/releasing.md`
- Modify: `.gitlab-ci.yml`
- Modify: `docs/rfcs/completed/RFC-0002-workbuddy-multi-plugin-packaging.md`（frontmatter）

- [ ] **Step 1: 重写 tests/test_pack.py**

完整重写 fixture 和测试类。核心变更：
- `plugin_repo` → `bundle_repo`：创建 `bundles/test-bundle/bundle.json` + `icon.svg` 而非 `.workbuddy-plugin/` 下 4 文件
- CLI 参数从 `--plugin` 改为 `--bundle`
- 错误测试从"文件缺失"改为"bundle.json 字段缺失"

```python
"""pack.py 测试（RFC-0003）。"""
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PACK = ["python3", str(SCRIPTS / "pack.py")]


def run_pack(repo, *args):
    return subprocess.run(PACK + list(args), cwd=repo, capture_output=True, text=True)


@pytest.fixture
def bundle_repo(tmp_path):
    """创建包含一个 bundle 的最小仓库。"""
    # 创建 skills 目录
    skills_dir = tmp_path / "skills" / "test-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("---\nname: test\ndescription: test\n---\nbody")
    (skills_dir / "references").mkdir()
    (skills_dir / "references" / "doc.md").write_text("# Doc")

    # 创建 bundle 目录
    bundle_dir = tmp_path / "bundles" / "test-bundle"
    bundle_dir.mkdir(parents=True)

    bundle_data = {
        "schemaVersion": 1,
        "id": "test-bundle",
        "version": "1.0.0",
        "skills": ["test-skill"],
        "presentation": {
            "defaultLocale": "zh-CN",
            "locales": {
                "zh-CN": {
                    "name": "Test Bundle",
                    "description": "Test description",
                    "examples": ["Example 1"]
                }
            },
            "icon": "icon.svg"
        },
        "mcp": {
            "servers": {
                "test-server": {
                    "transport": "streamable-http",
                    "url": "https://mcp.example.com/mcp"
                }
            }
        },
        "targets": {
            "workbuddy": {
                "source": "test-bundle",
                "type": "mcp",
                "minVersion": "4.24.0"
            }
        }
    }
    (bundle_dir / "bundle.json").write_text(json.dumps(bundle_data, ensure_ascii=False))
    (bundle_dir / "icon.svg").write_text("<svg></svg>")

    return tmp_path


class TestSingleBundle:
    """单 bundle 打包测试。"""

    def test_basic_packaging(self, bundle_repo):
        result = run_pack(bundle_repo, "--bundle", "test-bundle")
        assert result.returncode == 0, result.stderr
        zip_path = bundle_repo / "dist" / "workbuddy" / "test-bundle-v1.0.0.zip"
        assert zip_path.is_file()

    def test_zip_contents(self, bundle_repo):
        run_pack(bundle_repo, "--bundle", "test-bundle")
        zip_path = bundle_repo / "dist" / "workbuddy" / "test-bundle-v1.0.0.zip"
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "connector-meta.json" in names
            assert "mcp.json" in names
            assert "icon.svg" in names
            assert any("skills/test-skill/SKILL.md" in n for n in names)

    def test_connector_meta_contents(self, bundle_repo):
        run_pack(bundle_repo, "--bundle", "test-bundle")
        zip_path = bundle_repo / "dist" / "workbuddy" / "test-bundle-v1.0.0.zip"
        with zipfile.ZipFile(zip_path) as zf:
            meta = json.loads(zf.read("connector-meta.json"))
            assert meta["name"] == "Test Bundle"
            assert meta["type"] == "mcp"
            assert meta["source"] == "test-bundle"
            assert meta["version"] == "1.0.0"
            assert meta["minWorkbuddyVersion"] == "4.24.0"


class TestDeterministic:
    """确定性 ZIP 测试。"""

    def test_sorted_entries(self, bundle_repo):
        run_pack(bundle_repo, "--bundle", "test-bundle")
        zip_path = bundle_repo / "dist" / "workbuddy" / "test-bundle-v1.0.0.zip"
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert names == sorted(names)

    def test_fixed_timestamp(self, bundle_repo):
        run_pack(bundle_repo, "--bundle", "test-bundle")
        zip_path = bundle_repo / "dist" / "workbuddy" / "test-bundle-v1.0.0.zip"
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                assert info.date_time == (1980, 1, 1, 0, 0, 0)


class TestErrorHandling:
    """错误处理测试。"""

    def test_missing_bundle(self, bundle_repo):
        result = run_pack(bundle_repo, "--bundle", "nonexistent")
        assert result.returncode != 0

    def test_custom_output(self, bundle_repo):
        result = run_pack(bundle_repo, "--bundle", "test-bundle", "--out", "custom-out")
        assert result.returncode == 0
        assert (bundle_repo / "custom-out").is_dir()
```

- [ ] **Step 2: 运行测试确认通过**

```bash
python3 -m pytest tests/test_pack.py -v
```

Expected: All PASS

- [ ] **Step 3: 删除 .workbuddy-plugin/ 目录**

```bash
rm -rf .workbuddy-plugin/
```

- [ ] **Step 4: 更新 .gitlab-ci.yml**

修改 release stage 的 pack.py 命令：

```yaml
# 变更前
    - python3 scripts/pack.py --out dist/workbuddy

# 变更后
    - python3 scripts/pack.py --bundle sales-coach --target workbuddy --out dist/workbuddy
```

- [ ] **Step 5: 更新 README.md**

按 RFC §6 阶段 4 的具体变更点更新：
- 项目结构目录树：`.workbuddy-plugin/` 段改为 `bundles/sales-coach/`
- 删除 `assets/icon.svg` 引用
- `scripts/` 段新增 `packaging/` 子目录
- "市场图标"说明更新为 `bundles/sales-coach/icon.svg`

- [ ] **Step 6: 更新 docs/releasing.md**

将命令模板中的 `--plugin` 改为 `--bundle`。

- [ ] **Step 7: 标记 RFC-0002 为 Superseded**

修改 `docs/rfcs/completed/RFC-0002-workbuddy-multi-plugin-packaging.md` 的 frontmatter：
- `status: Completed` → `status: Superseded`
- 添加 `superseded_by: RFC-0003`

同样修改 `docs/rfcs/draft/RFC-0002-workbuddy-multi-plugin-packaging.md`（如果存在）。

- [ ] **Step 8: 运行全量验证**

```bash
cd /home/zoushen/projects/21coachskills/coachskills
python3 scripts/check.py
python3 -m pytest tests/ -v
python3 scripts/pack.py --bundle sales-coach --target workbuddy
```

Expected: 全部通过，生成 `dist/workbuddy/sales-coach-v0.1.0.zip`

---

## Self-Review Checklist

- [x] 每条 AC 有对应 task：AC1→Task 5 Step 3, AC2→Task 4 Step 2, AC3→Task 4 Step 3, AC4→Task 6 Step 8
- [x] 无 TBD/TODO
- [x] 文件路径精确
- [x] 所有 commit 步骤已跳过（用户明确要求）
- [x] 代码完整（不是 "add validation" 等模糊描述）
- [x] 测试命令和预期输出具体
