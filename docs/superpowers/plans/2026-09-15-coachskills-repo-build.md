# coachskills 仓库建设（P1+P1.5+P2+P3a+P3b）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 RFC-0001（`docs/rfcs/approved/RFC-0001-superpowers-style-company-skills.md`）完成仓库建设增量：迁移 `ai_customer_design` 技能为跨宿主通用形态（P1/P1.5）、双平台清单（P2）、三维护脚本+T01–T17 测试+最小 CI（P3a）、安装与发布文档（P3b）。**不含** P0 spike / E01–E11 / X01–X06 / P4.5 / P5（外部依赖，另行人工执行）。

**Architecture:** 仓库根即一个插件：根 `skills/` 唯一技能源，`.codex-plugin/plugin.json` 版本字段为唯一版本源，构建器从 Git 快照白名单打包双平台 ZIP 并对 WorkBuddy 做 frontmatter 投影。三维护脚本扁平、互不 import，共享同一 YAML 解析契约。

**Tech Stack:** Python 3.11（维护脚本）、PyYAML（pinned）、pytest、GitLab CI。源技能：`/home/zoushen/.claude/skills/ai_customer_design/`（只读输入，**不修改**）。

**全局约束（每个 task 都适用）：**
- **不执行任何 git commit/push**（rfc-driven-dev 全局规则）。计划中无 commit 步骤；完成后由用户手动提交。**例外声明**：`tests/conftest.py` 的 fixture 在 `tmp_path` 内运行 `git init/add/commit`——这是测试局部构造迷你仓库，不触碰项目仓库，执行代理不得因此停滞。
- **不修改源目录** `/home/zoushen/.claude/skills/ai_customer_design/` 任何文件。
- Lint/type 只跑本次改动文件（`ruff check <files>`；无 pyright 配置时跳过），禁止全量。
- 所有新文件 UTF-8、LF。
- **测试脚本路径一律绝对化**：`SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"`，避免子进程 cwd 相对路径解析失败。

---

## File Structure（目标树，RFC §3.1）

```
coachskills/
├── .agents/plugins/marketplace.json          # Task 5
├── .codex-plugin/plugin.json                 # Task 5
├── .mcp.json                                 # Task 5
├── .workbuddy-plugin/connector-meta.json     # Task 5
├── skills/ai_customer_design/
│   ├── SKILL.md                              # Task 2
│   ├── references/{course-workflows,file-upload,result-and-progress,troubleshooting}.md  # Task 2
│   ├── scripts/render_qr.py                  # Task 4
│   └── vendor/segno/                         # Task 4（含 LICENSE）
├── assets/icon.svg                           # Task 5
├── scripts/{check.py,build.py,bump_version.py}  # Task 6/7/8
├── tests/
│   ├── conftest.py                           # Task 8（git 仓库 fixture）
│   ├── test_versioning.py                    # Task 6（T01/T11）
│   ├── test_check.py                         # Task 7（T05-b/T13/T14/T15/T16）
│   ├── test_packaging.py                     # Task 8（T02/T03/T04/T06/T07/T08/T09/T12/T17）
│   ├── test_render_qr.py                     # Task 4（T10）
│   ├── scenarios/ai_customer_design.md             # Task 2（关键业务场景记录）
│   └── e2e_base/                             # Task 9（E_base 静态脚手架）
├── docs/
│   ├── installation/{codex,workbuddy}.md     # Task 12
│   ├── releasing.md                          # Task 12
│   ├── migration/ai_customer_design.md             # Task 1 起（增量维护）
│   ├── mcp-contract/tools-list-snapshot.json # Task 12
│   └── deferred-acceptance.md                # Task 12（延后验收 checklist）
├── requirements-dev.txt                      # Task 10
├── .gitlab-ci.yml                            # Task 10
├── README.md                                 # Task 11（替换 GitLab 模板）
└── RELEASE-NOTES.md                          # Task 11
```

注：`tests/test_check.py`、`tests/conftest.py` 为 RFC §3.1 树的自然测试基建补充（check 校验与 packaging 分文件，保持 200–400 行内聚）。`docs/deferred-acceptance.md` 承载延后的 P0/E/X 验收项索引。

---

### Task 1: 迁移基线取证 + 骨架（M01）

**Files:**
- Create: `docs/migration/ai_customer_design.md`
- Create: `skills/ai_customer_design/`（空目录结构，由 Task 2/4 填充）

- [ ] **Step 1: 重新计算源文件哈希与行数（M01 硬前置）**

```bash
cd /home/zoushen/.claude/skills/ai_customer_design
sha256sum SKILL.md scripts/mcp_client.py
wc -l SKILL.md scripts/mcp_client.py INSTALL.md README.md
git -C . status 2>/dev/null || echo "not a git repo — record mtimes"
```

Expected: 得到当前哈希。与 RFC §1.1 快照（SKILL.md `01a7084e…`、mcp_client.py `2be49f69…`）比对；**若哈希变化，先 diff 审查新改动是否影响 §3.7 业务规则，把差异摘录写入迁移文档后再继续**。

- [ ] **Step 2: 写迁移文档（含四段 schema）**

`docs/migration/ai_customer_design.md` 初始内容（哈希/行数用 Step 1 实测值替换 `<…>`）：

```markdown
# ai_customer_design 迁移记录

## M01 源入口
- 源路径：/home/zoushen/.claude/skills/ai_customer_design/
- 迁移时取证（<日期>）：SKILL.md sha256=<hash> (<n> 行)；scripts/mcp_client.py sha256=<hash> (<n> 行)；INSTALL.md <n> 行；README.md <n> 行
- 基准 RFC 快照（2026-09-14）：SKILL.md 01a7084e…（582 行）/ mcp_client.py 2be49f69…；与迁移时差异审查结论：<无差异 / 差异摘要>
- 迁移后独立维护，不再从个人目录同步

## M03 绑定映射（源章节段 → 目标文件）
<!-- Task 2 填充，逐段核销：[ ] 未核销 / [x] 已核销 -->

| 源 SKILL.md 段落（行号区间以迁移时版本为准） | 目标 | 核销 |
|---|---|---|
| （待 Task 2 填） | | |

## M10 源文档处置
| 源文件 | 处置 | 去向 |
|---|---|---|
| INSTALL.md（<n> 行） | 重写 | docs/installation/{codex,workbuddy}.md（宿主中立重写，不逐句复制） |
| README.md（<n> 行） | 摘要并入 | 新根 README.md（M09）；安装细节 → docs/installation/ |

## P1.5 人工巡检记录
<!-- Task 3 填充：grep 命中清单 + 改写对照 -->
```

- [ ] **Step 3: 验证**

Run: `test -f docs/migration/ai_customer_design.md && grep -c "M01\|M03\|M10\|P1.5" docs/migration/ai_customer_design.md`
Expected: ≥4

---

### Task 2: SKILL.md 重写 + references 拆分（M02/M02-c/M03/M06/M06-c/M08-正文侧）

**Files:**
- Create: `skills/ai_customer_design/SKILL.md`
- Create: `skills/ai_customer_design/references/course-workflows.md`、`file-upload.md`、`result-and-progress.md`、`troubleshooting.md`
- Modify: `docs/migration/ai_customer_design.md`（M03 绑定映射逐段核销）

- [ ] **Step 1: 通读源 SKILL.md 全文并建立绑定映射**

读 `/home/zoushen/.claude/skills/ai_customer_design/SKILL.md` 全文，按以下映射把每个语义段落登记进迁移文档 M03 表（行号区间用 Task 1 取证版本）：

| 源段类型 | 目标 |
|---|---|
| 触发条件、业务前提、MCP 前提 | SKILL.md 主文件（重写为宿主中立） |
| 建课/改课/查询工作流细节 | references/course-workflows.md |
| 文档上传与 fileIds | references/file-upload.md |
| 结果核实、进度语义、双完成判定 | references/result-and-progress.md |
| 异常排查、超时、断流、认证失败 | references/troubleshooting.md |

- [ ] **Step 2: 写 SKILL.md 主文件**

结构要求（正文 ≤150 行，自包含"新建课程（含结果核实）"最小路径）：

```markdown
---
name: ai_customer_design
description: 创建和修改公司培训课程、上传课程资料、查询课程并生成练习链接。触发关键词：建课、AI 客户课程、AI 设计师对话、改课、查询培训课程、生成练习链接。
metadata:
  description_zh: 创建和修改公司培训课程，上传资料并生成练习入口。
  description_en: Create and edit company training courses and generate practice links.
---

# 公司培训课程技能（ai_customer_design）

## 适用场景
<动作+对象+场景句式；不含 "Use when" 等私有触发短语>

## 前提
- 宿主 MCP 客户端已连接 enterprise-training 服务（连接与授权由宿主 MCP 设置管理）
- 工具名称前缀以宿主实际 tools/list 为准，不硬编码任何宿主 SDK 假设

## 最小执行路径：新建课程（不读 references 也可完成）
1. <从源技能建课流程提取的自包含步骤，含双完成判定>
2. 完成判定：对话结束（status: completed 或 AI 回复完成）≠ 课程建成；必须调用
   get_ai_customer_config 核实 create_status_created 且 stages 非空
3. 交付：练习链接必达；二维码由 <skill-root>/scripts/render_qr.py 生成（宿主有
   Python 运行时时），QR 生成失败时直接向用户展示原始练习链接

## 详细流程
- [建课/改课/查询](references/course-workflows.md)
- [文档上传](references/file-upload.md)
- [结果核实与进度](references/result-and-progress.md)
- [异常排查](references/troubleshooting.md)

## 关键业务规则（不可精简）
<§3.7 五条权威规则逐条落文：双完成判定 / 不盲目重放（E-MCP-UNCERTAIN）/
fileIds 原样传递 / 改课基线核实 / 链接+QR 双交付>
```

**改写规则**（每处源文本过一遍）：
- `Claude Code`/`Codex`/宿主名 → "宿主"/"宿主 MCP 客户端"
- `~/.claude/skills/...` 等个人路径 → `<skill-root>/...`
- `python3 ~/...mcp_client.py` 备选调用 → 删除（M08）；无 MCP 宿主的 HTTP 直连降级指引**只写 troubleshooting.md** 并标注"仅非首期宿主适用"
- OAuth 失败引导 → "由宿主 MCP 设置重新连接"
- 错误提示挂 §3.13 错误码（E-USER-/E-HOST-/E-MCP-）

- [ ] **Step 3: 写 4 个 references 文件**

每个文件开头一行来源标注：`> 迁移自源技能 §<段落>，业务规则以本文为准`。内容按 M03 映射从源提取，套用 Step 2 同一套改写规则。**M07**：源技能中的测试环境阶段性经验（如"秒拒"现象等）不得直接断言为确定的后端原因——要么删除，要么保留并强制标注"适用日期 + 服务版本"（§3.7 M07）。`troubleshooting.md` 中解释 `_meta.progressToken` 陷阱等**禁令语境**内容必须包在 `<!-- host-term-note -->` … `<!-- /host-term-note -->` 注释对内（§3.14 豁免机制）。

- [ ] **Step 4: M03 核销自检 + 场景记录**

Run: `grep -c '\[x\]' docs/migration/ai_customer_design.md` 对照映射表行数——所有源段落均已登记且核销。

写 `tests/scenarios/ai_customer_design.md`（§3.1 树成员，P1 退出"关键行为有场景记录"的载体）：从源技能工作流提炼 5–8 个关键业务场景（建课含双完成判定 / 改课含基线核实 / 文档上传含 fileIds / 结果不确定不重放 / QR 降级仅链接交付），每个场景写：前置条件、调用序列（工具名层面，不复制 schema）、预期业务结果。供 E01–E11 执行时对照。

- [ ] **Step 5: 通用化静态自检（P1.5 人工代行，check.py 于 Task 7 才交付）**

```bash
cd skills/ai_customer_design
grep -RnE "Claude Code|Anthropic|Codex|WorkBuddy|Cursor|Aider|Continue\.dev|~/.claude/|~/.codex/|~/.workbuddy/|~/.cursor/|~/.aider/|~/.continue/" SKILL.md references/
grep -RnE "Use when|Only use|<when_to_use>|Use this skill when" SKILL.md references/
grep -RnE "SessionStart|StatusLine|_meta\.progressToken|subagent|tool_use" SKILL.md references/
```
Expected: 全部 0 命中（troubleshooting.md 的 host-term-note 对内命中允许——Task 7 的 check.py 会剥离豁免段后再扫）。把三次 grep 原始输出（含 0 命中）记入迁移文档 P1.5 节。

---

### Task 3: （并入 Task 2 Step 5，无独立 task）

> P1.5 巡检即 Task 2 Step 5 的 grep + 改写 + 记录，不单列。

---

### Task 4: render_qr.py 提取 + vendor（§3.8 / M08 / T10）

**Files:**
- Create: `skills/ai_customer_design/scripts/render_qr.py`
- Create: `skills/ai_customer_design/vendor/segno/`（从源复制）
- Test: `tests/test_render_qr.py`

- [ ] **Step 1: 写失败测试**

`tests/test_render_qr.py`：

```python
"""T10：QR helper 行为验收（RFC §3.8）。干净 venv 变体由 CI 单独 job 覆盖。"""
import subprocess, sys
from pathlib import Path

QR = Path(__file__).resolve().parents[1] / "skills/ai_customer_design/scripts/render_qr.py"

def run_qr(*args):
    return subprocess.run([sys.executable, str(QR), *args],
                          capture_output=True, text=True)

def test_normal_url_generates_decodable_png(tmp_path):
    out = tmp_path / "qr.png"
    r = run_qr("https://example.com/p/123", "--out", str(out))
    assert r.returncode == 0, r.stderr
    assert out.exists() and out.stat().st_size > 0
    try:
        from PIL import Image  # 可选：装了 pyzbar 就解码验证
        import pyzbar.pyzbar as pyzbar
        decoded = pyzbar.decode(Image.open(out))
        assert any(b"https://example.com/p/123" in d.data for d in decoded)
    except ImportError:
        pass  # 解码器不可用时仅验证文件生成（RFC：可解码验证在有解码器的环境补）

def test_empty_url_fails_with_user_error():
    r = run_qr("")
    assert r.returncode != 0
    assert "E-USER-" in r.stderr

def test_unwritable_out_dir_fails():
    r = run_qr("https://example.com/p/1", "--out", "/proc/x/qr.png")
    assert r.returncode != 0
    assert "E-USER-" in r.stderr

def test_missing_dependency_prints_link(tmp_path, monkeypatch):
    # 模拟 vendor 不可达：清空 PYTHONPATH 并把 vendor 目录改名
    vendor = QR.parent.parent / "vendor"
    renamed = tmp_path / "vendor-moved"
    vendor.rename(renamed)
    try:
        r = run_qr("https://example.com/p/1")
        assert r.returncode != 0
        assert "https://example.com/p/1" in r.stdout  # 链接回退到 stdout
    finally:
        renamed.rename(vendor)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m pytest tests/test_render_qr.py -v`
Expected: FAIL（render_qr.py 不存在）

- [ ] **Step 3: 复制 vendor 并补 LICENSE**

```bash
cp -r /home/zoushen/.claude/skills/ai_customer_design/vendor/segno skills/ai_customer_design/vendor/segno
curl -fsSL https://raw.githubusercontent.com/heuer/segno/1.6.6/LICENSE -o skills/ai_customer_design/vendor/segno/LICENSE
grep -q "BSD" skills/ai_customer_design/vendor/segno/LICENSE  # 确认 BSD 三条款
rm -f skills/ai_customer_design/vendor/segno/pyproject.toml   # 构建元数据不入包（保留源码+LICENSE）
```
若网络不可达：从本机 pip 缓存/上游源目录找 LICENSE，或手写 BSD-3 声明并注明来源 URL（记入迁移文档）。

- [ ] **Step 4: 写 render_qr.py（完整实现）**

```python
#!/usr/bin/env python3
"""渲染练习链接二维码（本地，无网络、无凭证、无 MCP）。

降级：依赖不可用时把原始链接打到 stdout 并非零退出（RFC-0001 §3.8）。
用法：python render_qr.py '<练习链接>' [--out '<可写目录>/practice.png']
"""
import argparse
import importlib
import sys
import tempfile
from pathlib import Path

E_USER_ARGS = "E-USER-ARGS"
E_USER_OUT = "E-USER-OUT"
E_HOST_DEP = "E-HOST-DEP"


def _import_segno():
    """加载 vendored segno（对齐源 cmd_qr 的 vendor 注入逻辑，§3.8）。"""
    vendor = Path(__file__).resolve().parent.parent / "vendor"
    if not (vendor / "segno").exists():
        raise ImportError(f"vendored segno not found under {vendor}")
    if str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))
    importlib.invalidate_caches()
    import segno
    return segno


def main(argv=None):
    parser = argparse.ArgumentParser(description="渲染练习链接二维码")
    parser.add_argument("url", help="练习链接")
    parser.add_argument("--out", default=None, help="输出 PNG 路径（默认临时目录）")
    args = parser.parse_args(argv)

    if not args.url or not args.url.startswith(("http://", "https://")):
        print(f"{E_USER_ARGS}: URL 缺失或不合法：{args.url!r}", file=sys.stderr)
        return 2

    try:
        segno = _import_segno()
    except ImportError as exc:
        print(f"{E_HOST_DEP}: 二维码依赖不可用（{exc}）；请直接使用原始练习链接：")
        print(args.url)
        return 3

    out = Path(args.out) if args.out else Path(tempfile.gettempdir()) / "practice.png"
    try:
        qr = segno.make(args.url, error="m")
        qr.save(str(out), scale=8, border=2)
    except OSError as exc:
        print(f"{E_USER_OUT}: 输出路径不可写：{exc}", file=sys.stderr)
        return 2

    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 跑测试确认通过**

Run: `python3 -m pytest tests/test_render_qr.py -v`
Expected: 4 passed

- [ ] **Step 6: 干净 venv 变体验证（T10）**

```bash
python3 -m venv /tmp/qr-clean-venv
/tmp/qr-clean-venv/bin/python skills/ai_customer_design/scripts/render_qr.py 'https://example.com/p/1' --out /tmp/qr-clean.png
test -s /tmp/qr-clean.png && echo CLEAN-VENV-OK
```
Expected: `CLEAN-VENV-OK`（vendored segno 自包含，无 pip 依赖）

---

### Task 5: 平台清单（P2）

**Files:**
- Create: `.codex-plugin/plugin.json`、`.mcp.json`、`.agents/plugins/marketplace.json`、`.workbuddy-plugin/connector-meta.json`、`assets/icon.svg`

- [ ] **Step 1: 写 4 份清单 + 图标**

`.codex-plugin/plugin.json`（RFC §3.2 原文）：

```json
{
  "name": "coachskills",
  "version": "0.1.0-rc.1",
  "description": "通过公司 MCP 服务完成培训课程创建、修改和查询。",
  "author": {"name": "MGV"},
  "skills": "./skills/",
  "mcpServers": "./.mcp.json",
  "hooks": {},
  "interface": {
    "displayName": "公司培训技能",
    "shortDescription": "连接公司培训服务并完成课程工作流",
    "developerName": "MGV",
    "category": "Productivity"
  }
}
```

`.mcp.json`：

```json
{
  "mcpServers": {
    "enterprise-training": {
      "url": "https://mcp.test.omnimay.com/coach/mcp"
    }
  }
}
```

`.agents/plugins/marketplace.json`（§3.3）：

```json
{
  "name": "coachskills-marketplace",
  "interface": {"displayName": "公司 Skills"},
  "plugins": [
    {
      "name": "coachskills",
      "source": {"source": "local", "path": "./"},
      "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
      "category": "Productivity"
    }
  ]
}
```

`.workbuddy-plugin/connector-meta.json`（§3.5 原文，TODO 注释写文件外 README 或 migration 文档，**不进 JSON**）。

`assets/icon.svg` 占位（业务品牌核定前的最小占位，中性配色）：

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#2B6CB0"/>
  <text x="32" y="40" font-family="sans-serif" font-size="28" fill="#fff" text-anchor="middle">CS</text>
</svg>
```

- [ ] **Step 2: JSON 解析自检**

Run: `python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('.codex-plugin/*.json')+glob.glob('.agents/plugins/*.json')+glob.glob('.workbuddy-plugin/*.json')+['.mcp.json']]; print('JSON-OK')"`
Expected: `JSON-OK`

---

### Task 6: bump_version.py + 版本测试（T01/T11）

**Files:**
- Create: `scripts/bump_version.py`
- Test: `tests/test_versioning.py`

- [ ] **Step 1: 写失败测试**

```python
"""T01/T11：版本同步与损坏防护（RFC §3.9）。"""
import json, subprocess, sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
BUMP = ["python3", str(SCRIPTS / "bump_version.py")]
CODEX = Path(".codex-plugin/plugin.json")
WB = Path(".workbuddy-plugin/connector-meta.json")


def test_bump_syncs_both_manifests(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for f in (CODEX, WB):
        f.parent.mkdir(parents=True, exist_ok=True)
    CODEX.write_text(json.dumps({"version": "0.1.0-rc.1"}))
    WB.write_text(json.dumps({"version": "0.1.0-rc.1"}))
    r = subprocess.run(BUMP + ["0.1.0"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(CODEX.read_text())["version"] == "0.1.0"
    assert json.loads(WB.read_text())["version"] == "0.1.0"


def test_t11_corrupt_json_leaves_other_manifest_untouched(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    CODEX.parent.mkdir(parents=True, exist_ok=True)
    WB.parent.mkdir(parents=True, exist_ok=True)
    CODEX.write_text('{"version": "0.1.0-rc.1"')
    WB.write_text('{"version": "0.1.0-rc.1"}')
    r = subprocess.run(BUMP + ["0.1.0"], capture_output=True, text=True)
    assert r.returncode != 0
    assert json.loads(WB.read_text())["version"] == "0.1.0-rc.1"  # 未被提前修改


def test_t01_version_mismatch_fails(tmp_path, monkeypatch):
    """check.py 侧 T01 在 Task 7；此处验证 bump 前置一致性检查。"""
    monkeypatch.chdir(tmp_path)
    CODEX.parent.mkdir(parents=True, exist_ok=True)
    WB.parent.mkdir(parents=True, exist_ok=True)
    CODEX.write_text(json.dumps({"version": "0.1.0-rc.1"}))
    WB.write_text(json.dumps({"version": "0.0.9"}))  # 两清单本就不一致
    r = subprocess.run(BUMP + ["0.1.0"], capture_output=True, text=True)
    assert r.returncode != 0
    assert "version" in r.stderr
```

- [ ] **Step 2: 跑测试确认失败** — `python3 -m pytest tests/test_versioning.py -v` → FAIL

- [ ] **Step 3: 写 bump_version.py**

```python
#!/usr/bin/env python3
"""同步两份清单版本（唯一版本源：.codex-plugin/plugin.json，RFC §3.2）。

全部校验通过后原子写出；不 commit、不打 tag、不推送。
"""
import json
import sys
import tempfile
from pathlib import Path

REPO = Path.cwd()  # 正常用法与 CI 均从仓库根运行；测试可 monkeypatch.chdir
MANIFESTS = {
    "codex": REPO / ".codex-plugin/plugin.json",
    "workbuddy": REPO / ".workbuddy-plugin/connector-meta.json",
}


def _load_all():
    """先全部解析成功，再进入写阶段（T11：不提前修改任何一份）。"""
    data = {}
    for name, path in MANIFESTS.items():
        try:
            data[name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"E-MAINT-VERSION: {path} 解析失败：{exc}", file=sys.stderr)
            sys.exit(2)
    versions = {d["version"] for d in data.values()}
    if len(versions) != 1:
        print(f"E-MAINT-VERSION: 清单版本不一致："
              f"{ {k: d['version'] for k, d in data.items()} }", file=sys.stderr)
        sys.exit(2)
    return data


def _semver_key(v):
    core, _, pre = v.partition("-")
    nums = tuple(int(x) for x in core.split("."))
    return (nums, pre == "", pre)  # 无 pre-release > 有 pre-release


def main():
    if len(sys.argv) != 2:
        print("用法：bump_version.py <新版本>", file=sys.stderr)
        sys.exit(2)
    new = sys.argv[1]
    data = _load_all()
    old = data["codex"]["version"]
    if _semver_key(new) <= _semver_key(old):
        print(f"E-MAINT-VERSION: 版本不能回退或持平：{old} → {new}", file=sys.stderr)
        sys.exit(2)
    for name, path in MANIFESTS.items():
        data[name]["version"] = new
        # 原子写出：先写临时文件再替换
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data[name], ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        tmp.replace(path)
        print(f"bumped {path}: {old} → {new}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过** — `python3 -m pytest tests/test_versioning.py -v` → 3 passed

---

### Task 7: check.py + 通用化测试（T05-b/T13/T14/T15/T16 + E_base 静态部分）

**Files:**
- Create: `scripts/check.py`
- Test: `tests/test_check.py`

- [ ] **Step 1: 写失败测试**

```python
"""T05-b/T13/T14/T15/T16 + E_base01/02/04/05 静态检查（RFC §3.14/§3.6.1）。

失败/通过用例均通过 --only 选择器运行单项检查，互不牵连；
全量 check.py 的集成绿在 Task 11 Step 3（README 替换后）验证。"""
import subprocess, sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
CHECK = ["python3", str(SCRIPTS / "check.py")]


def run_check(cwd, *only):
    cmd = CHECK + (["--only", *only] if only else [])
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def _mk_skill(tmp_path, body, frontmatter="name: t\ndescription: 测试"):
    skill = tmp_path / "skills/ai_customer_design"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n{body}")


def test_t05b_banned_host_terms_fail(tmp_path):
    _mk_skill(tmp_path, "在 Claude Code 中运行本技能。\n")
    r = run_check(tmp_path, "host-terms")
    assert r.returncode != 0 and "Claude Code" in r.stderr


def test_t05b_host_term_note_exempt(tmp_path):
    _mk_skill(tmp_path, "正常正文。\n\n"
        "<!-- host-term-note -->\n注意避免 Claude Code 专属字段。\n<!-- /host-term-note -->\n")
    r = run_check(tmp_path, "host-terms")
    assert r.returncode == 0, r.stderr


def test_t13_trigger_phrase_fails(tmp_path):
    _mk_skill(tmp_path, "正文\n", frontmatter='name: t\ndescription: "Use when 用户要建课"')
    r = run_check(tmp_path, "trigger-phrases")
    assert r.returncode != 0 and "Use when" in r.stderr


def test_t14_broken_reference_link_fails(tmp_path):
    _mk_skill(tmp_path, "见 [文档](references/nope.md)\n")
    r = run_check(tmp_path, "references")
    assert r.returncode != 0 and "nope.md" in r.stderr


def test_t14_out_of_bounds_link_fails(tmp_path):
    _mk_skill(tmp_path, "见 [越界](../../../etc/passwd)\n")
    r = run_check(tmp_path, "references")
    assert r.returncode != 0


def test_t05_symlink_in_skill_dir_fails(tmp_path):
    import os
    skill = tmp_path / "skills/ai_customer_design"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: t\ndescription: d\n---\n正文\n")
    os.symlink("/etc/hosts", skill / "evil_link")
    r = run_check(tmp_path, "references")
    assert r.returncode != 0 and "symlink" in r.stderr


def test_t15_private_mechanism_term_fails(tmp_path):
    _mk_skill(tmp_path, "依赖 _meta.progressToken 与 SessionStart。\n")
    r = run_check(tmp_path, "mechanism-terms")
    assert r.returncode != 0 and "_meta.progressToken" in r.stderr


def test_t16_gitlab_readme_template_fails(tmp_path):
    (tmp_path / "README.md").write_text("# t\n\n## Add your files\n")
    r = run_check(tmp_path, "readme")
    assert r.returncode != 0 and "Add your files" in r.stderr


def test_frontmatter_allowed_tools_written_fails(tmp_path):
    _mk_skill(tmp_path, "正文\n", frontmatter="name: t\ndescription: d\nallowed-tools: Bash")
    r = run_check(tmp_path, "frontmatter")
    assert r.returncode != 0 and "allowed-tools" in r.stderr


def test_frontmatter_whitelist_ok(tmp_path):
    _mk_skill(tmp_path, "QR 生成失败时直接展示原始练习链接。\n",
              frontmatter="name: t\ndescription: d\nlicense: Proprietary\nmetadata:\n  description_zh: 测")
    r = run_check(tmp_path, "frontmatter")
    assert r.returncode == 0, r.stderr


def test_e_base01_required_fields_missing_fails(tmp_path):
    _mk_skill(tmp_path, "正文\n", frontmatter="name: t")  # 缺 description
    r = run_check(tmp_path, "frontmatter")
    assert r.returncode != 0 and "description" in r.stderr


def test_e_base04_qr_fallback_guidance_required(tmp_path):
    _mk_skill(tmp_path, "正文没有降级指引。\n")
    r = run_check(tmp_path, "qr-fallback")
    assert r.returncode != 0 and "QR" in r.stderr


def test_e_base05_oauth_copy_neutral(tmp_path):
    _mk_skill(tmp_path, "认证失败请打开 Claude 设置重连。\n")
    r = run_check(tmp_path, "oauth-copy")
    assert r.returncode != 0
```

（以上已完整可执行；实现时原样落盘。）

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 写 check.py（完整实现，~280 行）**

核心结构（实现时展开为完整代码）：

```python
#!/usr/bin/env python3
"""仓库静态检查（RFC §3.9/§3.14/§7.1）。

check.py     : 结构 + 通用化 + 一致性检查
check.py --release : 追加生产门禁（PRODUCTION_MCP_URL 匹配等）
错误输出：E-MAINT-<类别>：文件:行号 说明
"""
```

必须实现的检查函数（每个对应测试）：
- `--only` 选择器：`frontmatter|host-terms|trigger-phrases|mechanism-terms|references|readme|migration|manifests|qr-fallback|oauth-copy`（不传 → 全量）
- `load_frontmatter(path)` → `(dict, body_lines)`：**共享解析契约**——与 build.py 用同一 PyYAML 版本、同一函数签名（UTF-8/LF/`---` 边界）
- `check_frontmatter_whitelist`：五字段白名单；`allowed-tools` 出现即 fail；**必填字段** `name`/`description` 缺失即 fail（E_base01）
- `strip_exemptions(text)`：剥离 `<!-- host-term-note -->…<!-- /host-term-note -->` 段后再扫描
- `BANNED = {触发短语: [Use when, Only use, <when_to_use>, Use this skill when],
            宿主名: [Claude Code, Anthropic, Codex, WorkBuddy, Cursor, Aider, Continue.dev],
            私有目录: [~/.claude/, ~/.codex/, ~/.workbuddy/, ~/.cursor/, ~/.aider/, ~/.continue/],
            私有机制: [SessionStart, StatusLine, Hook, thinking, tool_use, subagent, Task 工具, _meta.progressToken]}`
  （仅扫 `skills/` 下 SKILL.md + references；大小写敏感精确子串；对齐 §3.6.1 操作化表）
- `check_reference_links`：Markdown 链接解析 → 目标存在于 skill 根内、不越界（resolve 后仍在 skill 目录下）；**T05 符号链接**：扫描 skill 目录内所有 entry，`p.is_symlink()` → fail（含相对链接目标为符号链接的情况）
- `check_readme_template`：三关键字
- `check_migration_schema`：迁移文档含 M01 源入口/M03 绑定映射/M10 处置/P1.5 记录四节
- `check_manifests_sync`：两清单 version 一致（T01 的 check 侧）
- `check_ebase04/05`：正文含 QR 降级指引关键词；OAuth 文案中性（命中宿主设置点名 → fail）
- `--release`：`PRODUCTION_MCP_URL` 环境变量与 `.mcp.json` URL 逐字匹配；测试地址/example 域名 → fail；`build_runtime` 记录提示

- [ ] **Step 4: 跑测试确认通过** — 全绿

- [ ] **Step 5: 对真实仓库跑一次（选择器范围）**

Run: `python3 scripts/check.py --only frontmatter host-terms trigger-phrases mechanism-terms references qr-fallback oauth-copy migration manifests`
Expected: 退出 0（Task 2 的通用化改写此时被机器复检；`readme` 检查留待 Task 11——当前 README 仍是 GitLab 模板，T16 必然命中）

---

### Task 8: build.py + 打包测试（T02/T03/T04/T06/T07/T08/T09/T12/T17）

**Files:**
- Create: `scripts/build.py`
- Create: `tests/conftest.py`
- Test: `tests/test_packaging.py`

- [ ] **Step 1: 写 conftest.py（迷你 git 仓库 fixture）**

```python
"""打包测试共用 fixture：在 tmp_path 里构造一个迷你 coachskills 仓库并 git init。"""
import json, subprocess
from pathlib import Path
import pytest

SKILL_MD = "---\nname: ai_customer_design\ndescription: 测试技能。\nmetadata:\n  description_zh: 测试\n  description_en: test\n---\n\n正文：QR 生成失败时直接展示原始练习链接。\n"

def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)

@pytest.fixture
def mini_repo(tmp_path):
    root = tmp_path / "repo"
    # scripts/build.py 本体随 fixture 提交（行为#1 要求 build 脚本属于目标 ref）
    real_build = Path(__file__).resolve().parents[1] / "scripts" / "build.py"
    for rel, content in {
        ".codex-plugin/plugin.json": json.dumps({"name": "coachskills", "version": "0.1.0-rc.1", "skills": "./skills/", "mcpServers": "./.mcp.json", "hooks": {}}),
        ".mcp.json": json.dumps({"mcpServers": {"enterprise-training": {"url": "https://mcp.test.omnimay.com/coach/mcp"}}}),
        ".workbuddy-plugin/connector-meta.json": json.dumps({"name": "t", "version": "0.1.0-rc.1", "source": "mgv-coachskills", "type": "mcp"}),
        "skills/ai_customer_design/SKILL.md": SKILL_MD,
        "assets/icon.svg": "<svg/>",
        "scripts/build.py": real_build.read_text(encoding="utf-8"),
    }.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@t"); git(root, "config", "user.name", "t")
    (root / ".gitignore").write_text("dist/\n__pycache__/\n")
    git(root, "add", "-A"); git(root, "commit", "-qm", "init")
    git(root, "tag", "v0.1.0-rc.1")
    return root
```

- [ ] **Step 2: 写失败测试（tests/test_packaging.py，每条对应一个 T-ID）**

```python
"""T01/T02/T03/T04/T06/T07/T08/T09/T11/T12/T17（RFC §7.1）。"""
import json, subprocess, zipfile
from pathlib import Path
from conftest import git, SKILL_MD

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
BUILD = ["python3", str(SCRIPTS / "build.py")]


def run_build(repo, *args, env_extra=None, ref="v0.1.0-rc.1"):
    import os
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(BUILD + ["--ref", ref, *args],
                          cwd=repo, capture_output=True, text=True, env=env)


def test_t02_dirty_tree_rejected(mini_repo):
    (mini_repo / "untracked.txt").write_text("x")
    r = run_build(mini_repo, "--platform", "codex")
    assert r.returncode != 0 and "未提交" in r.stderr


def test_t02_dirty_tree_allowed_for_dev(mini_repo):
    (mini_repo / "untracked.txt").write_text("x")
    r = run_build(mini_repo, "--platform", "codex", "--allow-dirty")
    assert r.returncode == 0, r.stderr


def test_release_and_allow_dirty_mutex(mini_repo):
    r = run_build(mini_repo, "--platform", "codex", "--allow-dirty", "--release",
                  env_extra={"PRODUCTION_MCP_URL": "https://mcp.example.com/mcp"})
    assert r.returncode != 0 and "互斥" in r.stderr


def test_t06_release_with_test_url_fails(mini_repo):
    r = run_build(mini_repo, "--platform", "codex", "--release")
    assert r.returncode != 0 and "PRODUCTION_MCP_URL" in r.stderr


def test_t07_second_server_rejected(mini_repo):
    mcp = mini_repo / ".mcp.json"
    mcp.write_text(json.dumps({"mcpServers": {
        "a": {"url": "https://x.example.com/mcp"},
        "b": {"url": "https://y.example.com/mcp"}}}))
    git(mini_repo, "add", "-A"); git(mini_repo, "commit", "-qm", "two")
    git(mini_repo, "tag", "-f", "v0.1.0-rc.1")
    r = run_build(mini_repo, "--platform", "workbuddy")
    assert r.returncode != 0 and "第二个" in r.stderr


def test_t08_whitelist_excludes_root_scripts(mini_repo):
    (mini_repo / "scripts/build.py").write_text("# dev only")
    git(mini_repo, "add", "-A"); git(mini_repo, "commit", "-qm", "s")
    git(mini_repo, "tag", "-f", "v0.1.0-rc.1")
    out = mini_repo / "dist"
    r = subprocess.run(BUILD + ["--ref", "v0.1.0-rc.1", "--platform", "codex",
                                "--out", str(out)],
                       cwd=mini_repo, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    z = next(out.rglob("*.zip"))
    names = zipfile.ZipFile(z).namelist()
    assert not any("scripts/build.py" in n for n in names)
    assert any("skills/ai_customer_design" in n for n in names)


def test_t04_workbuddy_frontmatter_projection(mini_repo):
    out = mini_repo / "dist"
    subprocess.run(BUILD + ["--ref", "v0.1.0-rc.1", "--platform", "workbuddy",
                            "--out", str(out)],
                   cwd=mini_repo, capture_output=True, text=True, check=True)
    z = next(out.rglob("*workbuddy*.zip"))
    skill = zipfile.ZipFile(z).read("skills/ai_customer_design/SKILL.md").decode()
    assert "description_zh: 测试" in skill          # metadata 保留
    assert "version: 0.1.0-rc.1" in skill           # 投影注入
    # 正文与源逐字节一致（分隔符之后）：
    src_body = SKILL_MD.split("---\n", 2)[2]
    assert src_body in skill
    # mcp.json 生成（§3.4）：streamableHttp + 同 URL
    mcp = json.loads(zipfile.ZipFile(z).read("mcp.json"))
    assert mcp["mcpServers"]["enterprise-training"]["type"] == "streamableHttp"
    assert mcp["mcpServers"]["enterprise-training"]["url"] == "https://mcp.test.omnimay.com/coach/mcp"


def test_t09_missing_localization_fails(mini_repo):
    p = mini_repo / "skills/ai_customer_design/SKILL.md"
    p.write_text("---\nname: ai_customer_design\ndescription: 测试。\n---\n正文\n")
    git(mini_repo, "add", "-A"); git(mini_repo, "commit", "-qm", "no-l10n")
    git(mini_repo, "tag", "-f", "v0.1.0-rc.1")
    r = run_build(mini_repo, "--platform", "workbuddy")
    assert r.returncode != 0 and "description_zh" in r.stderr


def test_t01_tag_manifest_mismatch_fails_at_release(mini_repo):
    """T01 核心：--ref v0.1.0 vs 清单 0.1.0-rc.1 → release 构建失败并指出字段。"""
    git(mini_repo, "tag", "v0.1.0")  # 清单仍是 0.1.0-rc.1
    r = run_build(mini_repo, "--platform", "codex", "--release", ref="v0.1.0",
                  env_extra={"PRODUCTION_MCP_URL": "https://mcp.example.com/mcp"})
    assert r.returncode != 0 and "version" in r.stderr and "v0.1.0" in r.stderr


def test_t06_wrong_production_url_fails(mini_repo):
    """T06 变体：PRODUCTION_MCP_URL 已设置但与 .mcp.json 不匹配 → fail。"""
    r = run_build(mini_repo, "--platform", "codex", "--release",
                  env_extra={"PRODUCTION_MCP_URL": "https://wrong.example.com/mcp"})
    assert r.returncode != 0 and "PRODUCTION_MCP_URL" in r.stderr


def test_t02_build_script_not_in_ref_rejected(mini_repo):
    """T02 变体（§3.9）：build 脚本不属于目标 ref → 拒绝跨版本构建。
    从 ref 快照中移除 scripts/ 后重建 tag，build.py 必须检测自身不在 ref 内并拒绝。"""
    git(mini_repo, "rm", "-rq", "scripts")
    git(mini_repo, "commit", "-qm", "drop scripts")
    git(mini_repo, "tag", "-f", "v0.1.0-rc.1")
    r = run_build(mini_repo, "--platform", "codex")
    assert r.returncode != 0 and "ref" in r.stderr


def test_t11_cross_parse_consistency(mini_repo):
    """T11 变体（§3.9 共享解析契约）：同一损坏 frontmatter，
    check.py 与 build.py 判定必须一致（同败且同指 frontmatter 解析）。"""
    p = mini_repo / "skills/ai_customer_design/SKILL.md"
    p.write_text("---\nname: [broken\n  bad yaml :::\n---\n正文\n")
    git(mini_repo, "add", "-A"); git(mini_repo, "commit", "-qm", "broken-fm")
    git(mini_repo, "tag", "-f", "v0.1.0-rc.1")
    chk = subprocess.run(["python3", str(SCRIPTS / "check.py"), "--only", "frontmatter"],
                         cwd=mini_repo, capture_output=True, text=True)
    bld = run_build(mini_repo, "--platform", "codex")
    assert chk.returncode != 0 and bld.returncode != 0          # 同败
    assert "SKILL.md" in chk.stderr and "SKILL.md" in bld.stderr  # 同因（frontmatter 解析失败）


def test_t12_same_version_different_hash_rejected(mini_repo):
    out = mini_repo / "dist"
    subprocess.run(BUILD + ["--ref", "v0.1.0-rc.1", "--platform", "codex",
                            "--out", str(out)],
                   cwd=mini_repo, capture_output=True, text=True, check=True)
    # 修改内容后同版本重建 → 拒绝覆盖
    p = mini_repo / "skills/ai_customer_design/SKILL.md"
    p.write_text(SKILL_MD + "\n改动\n")
    git(mini_repo, "add", "-A"); git(mini_repo, "commit", "-qm", "change")
    git(mini_repo, "tag", "-f", "v0.1.0-rc.1")
    r = run_build(mini_repo, "--platform", "codex", "--out", str(out))
    assert r.returncode != 0 and "已存在" in r.stderr


def test_t03_manifest_hashes_consistent(mini_repo):
    out = mini_repo / "dist"
    subprocess.run(BUILD + ["--ref", "v0.1.0-rc.1", "--platform", "all",
                            "--out", str(out)],
                   cwd=mini_repo, capture_output=True, text=True, check=True)
    import hashlib
    manifest = json.loads(next(out.rglob("release-manifest.json")).read_text())
    for archive in manifest["archives"]:
        digest = hashlib.sha256((out / archive["filename"]).read_bytes()).hexdigest()
        assert digest == archive["sha256"]
    # T17：成功构建后产物原子移入唯一最终路径，无 staging 残留
    assert (out / "0.1.0-rc.1").is_dir()
    assert not any(out.glob("0.1.0-rc.1-*")), list(out.iterdir())
```

- [ ] **Step 3: 跑测试确认失败**

- [ ] **Step 4: 写 build.py（完整实现，~330 行）**

必须实现的行为（对照测试逐条；**检查按编号顺序执行**，保证各测试的 stderr 断言确定性）：
1. `git rev-parse <ref>` 解析完整 commit；`git status --porcelain` 非空 → 拒绝（`--allow-dirty` 仅 dev；与 `--release` 互斥）；**T02 变体**：build 脚本自身不属于目标 ref 快照 → 拒绝跨版本构建（错误信息含 "ref"）。检查顺序：dirty/mutex → ref-membership → 版本一致性 → 生产 URL 门禁
2. 从 `git archive <ref>` 解包到临时目录读取内容（不混用工作树）
3. 版本 = `.codex-plugin/plugin.json.version`；两清单不一致 → fail；**T01**：`--release` 且 ref 形如 `vX.Y.Z` 时，X.Y.Z 必须等于清单 version（预发布后缀允许 `0.1.0-rc.1` ↔ tag `v0.1.0-rc.1`），不符 → fail 并在 stderr 指出字段与两边的值
4. WorkBuddy 投影：`load_frontmatter`（共享契约）→ 顶层写 `description_zh/en`、`version`、`author`；同名顶层冲突 → fail；分隔符后正文逐字节保留；**mcp.json 生成（§3.4）**：从 `.mcp.json` 明确字段读取（仅 `url`），生成 WorkBuddy 根 `mcp.json` `{"mcpServers": {"<key>": {"type": "streamableHttp", "url": ...}}}`——不做文件改名，不自动转发未知字段；遇 `type`/`headers`/`command` 等未知字段 → 按行为 9 失败
5. 白名单打包：codex = `.codex-plugin/ .mcp.json skills/ assets/`(+LICENSE)；workbuddy = `connector-meta.json mcp.json(生成) icon.svg skills/`(+LICENSE)；ZIP 固定排序 + 固定时间戳（`ZipInfo.date_time=(1980,1,1,0,0,0)`）
6. `--release`：`PRODUCTION_MCP_URL` 与 `.mcp.json` 逐字匹配（缺失或值不符均 fail，错误信息含 `PRODUCTION_MCP_URL`）；测试/example 域 → fail；记录 `build_runtime`
7. 输出 `dist/<version>-<short-hash>/`（T17 staging 路径），构建成功后原子 `os.replace` 到 `dist/<version>/`、staging 目录不残留；同版本不同 hash → 拒绝（T12）
8. `release-manifest.json`：`plugin_name/version/source_commit/mcp_url/build_runtime/skills(含 l10n 字段存在性)/archives[{filename,sha256}]`（filename 为相对 `--out` 根的路径，**含 `<version>/` 目录前缀**）+ 引用 `docs/mcp-contract/tools-list-snapshot.json` 的 hash；`SHA256SUMS` 覆盖两 archive + manifest
9. 第二个 server / stdio / 自定义认证头 / 未知字段 → 按异常失败（T07；§3.12 表）；**失败输出统一 `E-MAINT-<类别>：<文件/字段> <不满足的条件>` 前缀**（§3.14 规则 8）

- [ ] **Step 5: 跑测试确认通过** — `python3 -m pytest tests/test_packaging.py -v` 全绿

---

### Task 9: E_base 静态脚手架（P3a，E_base01/02/04/05）

**Files:**
- Create: `tests/e2e_base/run_e2e_base.py`

- [ ] **Step 1: 写脚手架入口**

```python
#!/usr/bin/env python3
"""E_base 静态检查入口（RFC §7.2.1）：调用 scripts/check.py 的对应检查项，
输出 E_base01/02/04/05 四项判定表。真实 MCP 调用不在本脚手架范围（E_base03
已移入 X 矩阵）。"""
import subprocess, sys
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
        r = subprocess.run(["python3", check, "--only", *flags],
                           capture_output=True, text=True, cwd=repo_root)
        status = "PASS" if r.returncode == 0 else "FAIL"
        print(f"{eid}: {status}")
        if status == "FAIL":
            failed.append(eid)
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
```

（check.py 的 `--only` 选择器已列入 Task 7 Step 3 函数清单首行——实现时加入。）

- [ ] **Step 2: 跑通**

Run: `python3 tests/e2e_base/run_e2e_base.py`
Expected: 四行 PASS

---

### Task 10: requirements-dev.txt + .gitignore + 最小 CI（§3.12）

**Files:**
- Create: `requirements-dev.txt`、`.gitignore`、`.gitlab-ci.yml`

- [ ] **Step 1: 固定开发依赖（实施时验证精确版本号）**

```text
PyYAML==6.0.2
pytest==8.3.3
```
（以实施当日 `pip install` 实际解析版本为准锁定；禁止 `>=` 浮动。）

- [ ] **Step 1b: 写 .gitignore（§3.10 dist/ 不提交的前提）**

```text
dist/
__pycache__/
*.pyc
.venv/
.pytest_cache/
```

- [ ] **Step 2: 写 .gitlab-ci.yml**

```yaml
# 最小 CI（RFC §3.12）：MR 静态检查+离线测试；tag 发布作业。
# 镜像需含 git（源码检出 + conftest 迷你仓库 fixture + build.py git archive），
# python:3.11 基于 buildpack-deps 自带 git；具体 patch tag 实施时锁定。
stages: [check, release]

check:
  stage: check
  image: python:3.11
  script:
    - pip install -r requirements-dev.txt
    - python3 scripts/check.py
    - python3 -m pytest tests/ -q
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main"

release:
  stage: release
  image: python:3.11
  resource_group: release-dist      # T17：发布作业串行化
  script:
    - pip install -r requirements-dev.txt
    - python3 scripts/check.py --release
    - python3 scripts/build.py --ref $CI_COMMIT_TAG --platform all --out dist --release
  artifacts:
    paths: [dist/]
    expire_in: never      # §3.12：发布资产长期保留
  rules:
    - if: $CI_COMMIT_TAG
```

- [ ] **Step 3: 本地全量回归（readme 除外）**

Run: `python3 -m pytest tests/ -q && python3 scripts/check.py --only frontmatter host-terms trigger-phrases mechanism-terms references qr-fallback oauth-copy migration manifests`
Expected: 全绿（`readme` 待 Task 11；全量 `check.py` 绿在 Task 11 Step 3 验证）

---

### Task 11: README 替换 + RELEASE-NOTES（M09）

**Files:**
- Modify: `README.md`（整体替换 GitLab 模板）
- Create: `RELEASE-NOTES.md`

- [ ] **Step 1: 写 README.md**

结构：项目一句话（公司 Skills 仓库，仓库根即插件）→ 技能列表（ai_customer_design）→ 安装入口（指向 `docs/installation/`，不重复步骤）→ 维护命令（check/build/bump 三行）→ 版本策略（唯一版本源 §3.2 一句）→ RFC 索引链接。**禁止**出现 `Getting started with GitLab` / `Add your files` / `Test and Deploy`。

- [ ] **Step 2: 写 RELEASE-NOTES.md**

```markdown
# Release Notes

## 0.1.0-rc.1（未发布）
- 首个预览版：ai_customer_design 技能迁移 + Codex/WorkBuddy 双平台清单与构建
- 待 P4 验收与 P4.5 灰度后转 0.1.0
```

- [ ] **Step 3: T16 机器复检** — `python3 scripts/check.py` → 通过

---

### Task 12: 安装/发布文档 + MCP 契约快照 + 延后验收清单（P3b）

**Files:**
- Create: `docs/installation/codex.md`、`docs/installation/workbuddy.md`、`docs/releasing.md`、`docs/mcp-contract/tools-list-snapshot.json`、`docs/deferred-acceptance.md`

- [ ] **Step 1: codex.md** — 按 RFC §3.3 目标用法写：marketplace add（固定 ref）→ plugin add → 首次 OAuth（宿主管理）→ 验证 skill 发现。**每条命令旁标注**“目标用法，实测版本 pending P0 spike”；记录 SSH 私库前提。M10：从源 INSTALL.md 摘取仍适用的环境要求（不复制宿主专属步骤）。
- [ ] **Step 2: workbuddy.md** — 连接器包结构说明 + 提交流程（人工，指向 §3.5 字段表）+ minWorkbuddyVersion 待预检标注。
- [ ] **Step 3: releasing.md** — §3.11 发布流程表 + §3.11.2 触发条件表原样落文 + build/check/bump 命令手册。
- [ ] **Step 4: tools-list-snapshot.json**

```json
{
  "confirmed_by": "PENDING — P1 取证时与 MCP 服务团队核对（RFC §3.13）",
  "confirmed_date": null,
  "idempotent": ["get_ai_customer_config", "organization.* 查询类"],
  "non_idempotent": ["edit_ai_customer_chat", "文档上传（按 fileIds 幂等语义处理）"],
  "note": "本快照当前为 RFC 转录，未经服务端确认；确认后更新 confirmed_by/date，release-manifest 将引用本文件 hash"
}
```

- [ ] **Step 5: deferred-acceptance.md** — 列出全部延后项：P0 三项附加验证（Codex spike / minWorkbuddyVersion 预检 / 测试 MCP 认证确认）、E01–E11、X01–X06（含 E_base03 移入项）、P4.5 灰度、P5 首发；每项附 RFC 章节引用与执行人占位。

- [ ] **Step 6: 终检**

```bash
python3 scripts/check.py && python3 scripts/check.py --release 2>&1 | grep -q PRODUCTION_MCP_URL && echo GATE-OK
python3 -m pytest tests/ -q
```
Expected: GATE-OK + 全绿

---

## 完成定义（DoD）

1. `python3 -m pytest tests/ -q` 全绿（T01–T17 对应测试 + T10 干净 venv 变体手动验证记录在案）
2. `python3 scripts/check.py` 退出 0（含 M03 核销、M09、§3.14 八规则、迁移 schema 四节）
3. 打包链路经 `tests/test_packaging.py` 全绿验证（T02/T03/T04/T06/T07/T08/T09/T11/T12/T17 在迷你 git 仓库 fixture 中覆盖）；**交付时点不运行真实仓库 `--platform all` 构建**（无 commit/tag 可指、工作树含未跟踪产物会被行为#1 拒绝）——用户手动 commit + tag 后按 `docs/releasing.md` 重跑
4. `python3 tests/e2e_base/run_e2e_base.py` 四项 PASS
5. 目录树与 RFC §3.1 一致（允许偏差：tests/{conftest,test_check}.py、docs/{superpowers/,deferred-acceptance.md}、.gitignore 为 §3.10 要求）
6. **无任何 git 写操作**——交付后提示用户手动 commit
