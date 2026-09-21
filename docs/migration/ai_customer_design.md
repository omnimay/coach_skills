# ai_customer_design 迁移记录

## M01 源入口
- 源路径：/home/zoushen/.claude/skills/ai_customer_design/
- 迁移时取证（2026-09-15）：SKILL.md sha256=01a7084e97219c6a58e7f1ca586a84103a02c74ca9a0412394dbc691bc072a8b (582 行)；scripts/mcp_client.py sha256=2be49f6984fe0051ea06f9fa60a28d80d704c8155f436ee624c3ce821c495503 (1257 行)；INSTALL.md 123 行；README.md 74 行
- 基准 RFC 快照（2026-09-14）：SKILL.md 01a7084e…（582 行）/ mcp_client.py 2be49f69…；与迁移时差异审查结论：无差异（两个文件 sha256 与基准快照完全一致，五条业务规则——双完成判定/不盲目重放/fileIds 原样传递/改课先记基线/QR 双交付——均为基准版本，无需摘录差异）
- 迁移后独立维护，不再从个人目录同步

## M03 绑定映射（源章节段 → 目标文件）
<!-- Task 2 填充，逐段核销：[ ] 未核销 / [x] 已核销 -->
<!-- 行号区间：源 SKILL.md sha256=01a7084e…（582 行，Task 1 取证版本）。

处置符号说明：
- [x] 已核销 = 段落内容已按映射提取到目标文件（宿主中立改写，非逐句复制）
- 删除 = 按迁移契约有意不迁移（宿主耦合/替代物见备注），无孤儿段落 -->

| 源 SKILL.md 段落（行号区间） | 目标 | 核销 |
|---|---|---|
| L1-4 frontmatter（含 "Use when" 私有触发短语） | SKILL.md frontmatter（触发关键词句式重写） | [x] |
| L6-10 标题与前提（MCP 服务器 OAuth 鉴权前提） | SKILL.md §前提（宿主 MCP 设置管理） | [x] |
| L12-18 工具调用方式（原生 MCP / mcp_client.py 备选 / 本地 QR 脚本） | SKILL.md §前提+§最小执行路径（备选脚本调用删除，M08；QR 归 render_qr.py） | [x] |
| L20-41 MCP 流式通知协议契约（单向通知/伪叙述禁令） | references/troubleshooting.md（协议契约说明，禁令语境豁免段内） | [x] |
| L43-103 course.edit_ai_customer_chat 的本质（两种完成/响应陷阱/误导性回复） | references/result-and-progress.md（双完成判定）+ SKILL.md §关键业务规则 1 | [x] |
| L105-131 流式输出（SSE）支持（开流/通知三类形态/流式 vs 非流式/脚本路径） | references/result-and-progress.md §流式调用支持（脚本路径删除，M08） | [x] |
| L133-167 流式通知类型与终态判定（帧类型/终态表/percent 语义/边界） | references/result-and-progress.md §终态判定+§percent 语义+§边界 | [x] |
| L169-179 建课前的核心问题（三问/信息推断） | references/course-workflows.md §建课前准备 | [x] |
| L181-234 建课工作流 Step 1-5（含盲走路径/权威验证/兜底轮询） | references/course-workflows.md §建课工作流 + SKILL.md §最小执行路径（自包含提炼） | [x] |
| L236-274 建课完成的判断标准（JS 示例/字段清单/AI 不可信） | references/result-and-progress.md §正确的判断逻辑（与 L43-103 合并去重） | [x] |
| L276-296 关于超时、断流与轮询兜底（超时预算表/轮询纪律/禁止中途询问） | references/troubleshooting.md §超时预算+§轮询兜底纪律 | [x] |
| L298-307 chat 调用解析契约（stderr/structuredContent/禁传 requestId/禁并行/indeterminate） | references/troubleshooting.md §调用契约 + result-and-progress.md §schema 红线 | [x] |
| L309-315 关于并发建课（上限 3） | references/course-workflows.md §并发建课 | [x] |
| L317-330 已知行为模式（prepare 不拦截/60s 冷却/AI 补阶段等实测表） | references/troubleshooting.md §已知行为模式（M07 实测标注） | [x] |
| L332-347 课程简报检查清单（6 要素） | references/course-workflows.md §课程简报检查清单 | [x] |
| L349-381 文档上传工作流（强制决策规则/上传步骤/fileIds 规则） | references/file-upload.md 全文 | [x] |
| L383-412 改课工作流（基线/核实/重试上限）+ 运行参数边界 | references/course-workflows.md §改课工作流 | [x] |
| L414-452 二维码 + 链接展示（双交付/禁止做法/脚本渲染） | references/course-workflows.md §练习链接与二维码交付 + SKILL.md §最小执行路径第 5 步 | [x] |
| L454-468 常用工具表 | references/course-workflows.md §查询工作流与常用工具（get_ai_customer_report 保留"schema 待确认"标注） | [x] |
| L470-524 Python API / CLI 调用（call_tool/stream_call/sys.path 注入） | 删除（M08：不携带旧 MCP 客户端进发布包） | [x] |
| L526-532 已知约定（鉴权透传/字段转换/错误封装/响应数据位置） | references/result-and-progress.md §响应数据位置与错误封装 | [x] |
| L534-553 错误处理表 + 三种不可用鉴别表 | references/troubleshooting.md §错误处理表+§三种形态鉴别表 | [x] |
| L555-582 OAuth 过期处理（auth --status/auth 脚本/token 有效期实测） | references/troubleshooting.md §认证失败处理（脚本 auth 改为"由宿主 MCP 设置重新连接"，M05） | [x] |

核销自检：映射表数据行 23 行全部核销（`grep -c '\[x\]'` = 25，含 2 条含 "[x]" 字样的注释行）；源 582 行全部段落（L1-583）均已登记，无孤儿段落；目标文件无无源内容（新增仅为宿主中立改写表述与 M07 实测标注、错误码挂接）。

## 补充记录（2026-09-15）

针对用户反馈"务必仔细检查，确保 /ai_customer_design 中的重要信息都整合到本项目的 ai_customer_design 中"，进行以下补充：

### SKILL.md 补充

1. **前提部分**：新增工具调用方式与 QR 渲染要求
   - "工具调用：推荐使用宿主原生 MCP 工具"
   - "QR 渲染：必须使用 `<skill-root>/scripts/render_qr.py`（禁止大模型直接生成二维码）"

2. **新增章节"流式调用行为规范"**：
   - 信息展示约定（调用前/中/后的行为规范）
   - 禁止伪叙述的约束

3. **新增章节"技能文件结构"**：
   - 说明各文件功能（SKILL.md / references/* / scripts/render_qr.py / vendor/segno/）

### references/ 核对结果

- **course-workflows.md**：常用工具表完整（11 个工具，含 get_ai_customer_report 的 schema 待确认标注）
- **result-and-progress.md**：已知约定完整（鉴权透传/字段转换/错误封装/响应数据位置/chat 参数 schema 红线）
- **troubleshooting.md**：错误处理完整（7 类错误 + 3 种不可用鉴别 + 超时预算 + 轮询纪律 + 8 种已知行为模式 + 认证失败处理 + 降级指引）

### 未迁移内容（按 RFC-0001 契约）

- **Python API / CLI 调用**（原 SKILL.md L470-524）：按 M08 不携带旧 MCP 客户端
- **客户端支持矩阵**（原 SKILL.md L47-55）：涉及具体客户端名称（Claude Code/Cursor 等），违反 §3.14 规则 2
- **脚本模式详细说明**（原 SKILL.md L64-76）：涉及 mcp_client.py，按 M08 不携带

## M10 源文档处置
| 源文件 | 处置 | 去向 |
|---|---|---|
| INSTALL.md（123 行） | 重写 | docs/installation/{codex,workbuddy}.md（宿主中立重写，不逐句复制） |
| README.md（74 行） | 摘要并入 | 新根 README.md（M09）；安装细节 → docs/installation/ |

## P1.5 人工巡检记录
<!-- Task 2 填充：grep 命中清单 + 改写对照 -->

### P1.5 静态自检（2026-09-15，check.py 于 Task 7 交付前人工代行）

```text
$ cd skills/ai_customer_design
$ grep -RnE "Claude Code|Anthropic|Codex|WorkBuddy|Cursor|Aider|Continue\.dev|~/.claude/|~/.codex/|~/.workbuddy/|~/.cursor/|~/.aider/|~/.continue/" SKILL.md references/
（0 命中，exit=1）

$ grep -RnE "Use when|Only use|<when_to_use>|Use this skill when" SKILL.md references/
（0 命中，exit=1）

$ grep -RnE "SessionStart|StatusLine|_meta\.progressToken|subagent|tool_use" SKILL.md references/
references/troubleshooting.md:65:`notifications/progress` 及其关联令牌机制（如 `_meta.progressToken`，由宿主 MCP SDK 注入）是 **server → client 的单向通知**，此处解释其陷阱并指示规避：
references/troubleshooting.md:69:- 不要假设存在"server → 调用方流式中间结果"机制；也不要依赖宿主私有机制（subagent 分发、宿主钩子注入等）处理流式内容
```

grep3 的 2 处命中均位于 troubleshooting.md L63-73 `<!-- host-term-note -->…<!-- /host-term-note -->` 豁免段内（§3.14 禁令语境豁免：解释 `_meta.progressToken` 陷阱并指示规避）。剥离豁免段后复扫 grep3 = 0 命中（exit=1）。结论：**通过**。

### P1.5 改写对照（主要宿主耦合 → 中性表述）

| 源表述 | 改写后 |
|---|---|
| frontmatter `Use when 用户要创建…` | `触发关键词：建课、AI 客户课程、…` 句式 |
| `MCP 服务器已通过 agent 的原生 MCP 客户端注册并完成 OAuth 鉴权`（Claude Code 等客户端语境） | `宿主 MCP 客户端已连接 enterprise-training 服务；连接与 OAuth 授权由宿主 MCP 设置管理` |
| `mcp_client.py` 的 `call`/`stream` 备选调用、Python API、CLI 调用、sys.path 注入示例（L12-18、L131、L470-524） | 删除（M08：不携带旧 MCP 客户端进发布包；QR 由 `<skill-root>/scripts/render_qr.py` 承接） |
| `~/.claude/skills/ai_customer_design/scripts/mcp_client.py`（L466、509、512 等） | 删除/改为 `<skill-root>/scripts/render_qr.py` |
| `python3 <skill安装路径>/scripts/mcp_client.py qr` | `python3 <skill-root>/scripts/render_qr.py`（Task 4 交付） |
| `客户端（Claude Code 等）只通过 UI 展示流式内容` | `宿主 MCP 客户端实时展示在用户界面上`（豁免段内保留禁令语境解释） |
| OAuth 失败执行 `mcp_client.py auth` 重新授权（L555-583） | `由宿主 MCP 设置重新连接`（M05，不点名客户端） |
| `CLI Bash 调用`/`Bash 工具默认 300s` | `宿主命令行调用`/`命令行工具默认超时` |
| 无 MCP 宿主的 HTTP 直连 | troubleshooting.md 单独一节并标注"仅非首期宿主适用" |
| 测试环境阶段性实测结论（秒拒成因、373s、84s、60s 冷却期等） | 各 references 文末"M07 实测经验标注"（适用日期 2026-09-14 + 测试环境/服务版本未记录声明） |
| 错误处理无错误码 | 挂接 §3.13：E-MCP-UNCERTAIN（结果不确定）、E-USER-/E-HOST-（QR 脚本错误码） |

## 待核定字段（P0 责任人确认）

平台清单（Task 5）按 RFC §3.2/§3.3/§3.5 原文落盘，以下字段为 RFC 标注的默认值/拟定值，JSON 内不写 TODO 备注，统一在此登记待业务负责人（P0）核定后回写：

| 字段 | 当前值 | 所在文件 | RFC 依据 |
|---|---|---|---|
| WorkBuddy `source` | `mgv-coachskills` | .workbuddy-plugin/connector-meta.json | §3.2"拟用，首次注册时确认可用性" |
| WorkBuddy `minWorkbuddyVersion` | `4.24.0` | .workbuddy-plugin/connector-meta.json | §3.5 TODO(pending business owner) |
| WorkBuddy `name`/`name_zh`/`name_en`/`description*` 展示文案 | 公司培训技能 / Company Training Skills 等 | .workbuddy-plugin/connector-meta.json | §3.5 TODO(pending business owner) |
| `author.name`/`developerName`（MGV 文案） | `MGV` | .codex-plugin/plugin.json | §3.2"待业务负责人核定的默认值" |
| `interface.displayName`/`shortDescription` | 公司培训技能 / 连接公司培训服务并完成课程工作流 | .codex-plugin/plugin.json | §3.2"待业务负责人核定的默认值" |
| `authentication: "ON_INSTALL"` 触发时序 | `ON_INSTALL` | .agents/plugins/marketplace.json | §3.3"P0 spike 实测记录，不符则改用其他 policy 值" |

版本说明：两清单 version 均为 `0.1.0-rc.1`，唯一版本源为 `.codex-plugin/plugin.json` 的 `version` 字段（§3.2）。

## T10 干净 venv 验证记录

- 2026-09-15：全新 venv（无 pip 包）运行 `render_qr.py` → CLEAN-VENV-OK，产物 sha256 d708aaac83ef0d128c66805c9bbbb12f1a02d316d97dccb45078e22ae1a4cb27（vendored segno 自包含，无外部依赖）
