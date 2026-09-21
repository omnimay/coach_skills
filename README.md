<div align="center">
  <img src="assets/GitHub项目主页封面横幅设计.jpeg" alt="coachskills banner" width="100%" />
</div>

# coachskills — 公司 Skills 仓库

公司内部 Agent 技能仓库。技能放在 `skills/` 下，通过 `bundles/` 配置组合成不同的发布包（bundle），构建时生成各平台原生格式。

## 项目结构

```
coachskills/
├── skills/                          # 技能目录
│   ├── ai_customer_design/                # MCP 培训技能
│   │   ├── SKILL.md                 # 技能定义
│   │   ├── references/              # 参考文档
│   │   ├── scripts/                 # 脚本（render_qr.py）
│   │   └── vendor/                  # 第三方依赖（segno）
│   └── coach-mcp-connect/           # MCP 连接技能
│       ├── SKILL.md                 # 技能定义
│       └── scripts/                 # 脚本（mcp_diagnose.py）
│
├── bundles/                         # 技能包目录
│   └── sales-coach/                 # 销售陪练包
│       ├── bundle.json              # 通用定义（组合、版本、展示、连接）
│       └── icon.svg                 # 包图标
│
├── dist/                            # 构建产物（打包生成的 zip）
│   └── workbuddy/
│       └── sales-coach-v0.1.0.zip
│
├── scripts/                         # 维护脚本
│   ├── check.py                     # 静态检查
│   ├── pack.py                      # 打包脚本
│   ├── file_validator.py            # 文件边界校验（共享）
│   └── bundle_builder/              # 构建模块
│       ├── bundle.py                # 通用层（配置读取、校验、ZIP 组装）
│       └── workbuddy.py             # WorkBuddy 平台适配
│
├── tests/                           # 测试用例
├── docs/                            # 文档
│   ├── rfcs/                        # RFC 文档
│   └── migration/                   # 迁移记录
│
├── assets/                          # 静态资源
│   └── GitHub项目主页封面横幅设计.jpeg  # 封面图片
│
├── environments.json                # 环境 URL 注册表（test / coach）
├── README.md                        # 项目说明
└── .gitignore
```

## 技能列表

| 技能 | 说明 |
| --- | --- |
| [ai_customer_design](skills/ai_customer_design/SKILL.md) | 通过宿主 MCP 客户端连接 enterprise-training 服务，完成培训课程创建/修改/查询、文档上传、练习链接与二维码交付 |
| [coach-mcp-connect](skills/coach-mcp-connect/SKILL.md) | 连接企业培训 MCP 服务器、执行工具调用、管理 catalog 的操作指南 |

## Bundle 列表

| Bundle | 说明 | Skills |
| --- | --- | --- |
| [sales-coach](bundles/sales-coach/) | 深维智讯・销售陪练 | ai_customer_design, coach-mcp-connect |

## 安装

安装步骤见各平台文档（本 README 不重复）：

- WorkBuddy：见 `docs/releasing.md`

## 维护命令

```bash
python3 scripts/check.py                  # 仓库静态检查
python3 scripts/pack.py                   # 打包所有 bundle（默认 test 环境）
python3 scripts/pack.py --bundle sales-coach  # 打包指定 bundle
python3 scripts/pack.py --env coach       # 打包到 coach（正式）环境
```

开发依赖与测试：

```bash
pip install -r requirements-dev.txt
python3 -m pytest tests/ -q
```

## 新增技能

技能放在 `skills/<name>/` 下。新增技能必须满足：

1. **SKILL.md frontmatter 白名单**：只允许 `name` / `description` / `license` / `metadata` / `allowed-tools` 五类字段（首期不写 `allowed-tools`）
2. **跨宿主通用**：不点任何宿主名（Claude Code / Codex / WorkBuddy 等），不写宿主私有路径（`~/.claude/` 等），不写宿主私有机制（thinking / hooks 等）
3. **触发关键词句式**：不用 `Use when` / `Only use` 等短语，改写为"触发关键词：……"
4. **路径占位**：用 `<skill-root>` / `<host-config-dir>`，不写具体目录
5. **降级路径**：宿主缺某能力时给出降级指引，不断言"业务闭环"
6. **本地化**：主 description 一种语言，本地化文案放 `metadata.description_zh` / `metadata.description_en`
7. **错误码**：引用 §3.13 错误码目录（E-USER- / E-MAINT- / E-HOST- / E-MCP-），不新造

新增技能时运行验证：

```bash
python3 scripts/check.py          # 全量检查（含新增技能的通用化规则）
python3 scripts/check.py --only frontmatter   # 只查 frontmatter 白名单
python3 scripts/check.py --only host-terms    # 只查禁用术语
python3 -m pytest tests/ -q       # 跑测试
```

完整规则见 [RFC-0001 §3.14](docs/rfcs/completed/RFC-0001-superpowers-style-company-skills.md) 的"通用化设计原则"。首期迁移示例：[docs/migration/ai_customer_design.md](docs/migration/ai_customer_design.md)。

## 新增 Bundle

在 `bundles/` 下创建新目录，包含：
- `bundle.json`：通用定义（组合、版本、展示、连接、平台目标）
- `icon.svg`：包图标

平台原生文件（`connector-meta.json`、`mcp.json`）由构建从 `bundle.json` 自动生成，不手工维护。详见 [RFC-0003](docs/rfcs/completed/RFC-0003-skill-bundle-refactoring.md)。

### bundle.json 配置

`bundle.json` 是平台无关的单一权威配置，包含三层信息：

| 字段 | 必填 | 说明 |
|---|---|---|
| `schemaVersion` | 是 | 配置版本号，当前固定 `1` |
| `id` | 是 | Bundle 唯一标识（字母、数字、连字符、下划线、点） |
| `version` | 是 | SemVer 版本号（如 `"0.1.0"`） |
| `skills` | 是 | 包含的 skill 名称列表 |
| `presentation.defaultLocale` | 是 | 默认语言（如 `"zh-CN"`） |
| `presentation.locales.<locale>.name` | 是 | 该语言的名称 |
| `presentation.locales.<locale>.description` | 是 | 该语言的描述 |
| `presentation.locales.<locale>.examples` | 是 | 该语言的示例（可为空数组） |
| `presentation.icon` | 是 | 图标文件名 |
| `mcp.servers.<name>.transport` | 是 | 传输协议（`streamable-http` / `sse`） |
| `mcp.servers.<name>.url` | 是 | 服务器 URL，支持 `${VAR}` 占位符 |
| `targets.workbuddy.source` | WorkBuddy | 渠道身份标识 |
| `targets.workbuddy.type` | WorkBuddy | 连接器类型（固定 `"mcp"`） |
| `targets.workbuddy.minVersion` | WorkBuddy | 最低 WorkBuddy 版本 |

### 环境变量

URL 等环境相关的值使用 `${VAR}` 占位符，实际值在 `environments.json` 中按环境注册：

```json
{
  "test": { "MCP_URL": "https://mcp.test.omnimay.com/coach/mcp" },
  "coach": { "MCP_URL": "https://mcp.omnimay.com/coach/mcp" }
}
```

打包时通过 `--env` 选择环境，占位符被替换为对应值。缺失变量时打包报错。

## 版本策略

每个 bundle 维护一个版本，来源于其 `bundle.json` 的 `version` 字段。各平台产物继承该版本。

**版本格式**：遵循 [SemVer](https://semver.org/)（`MAJOR.MINOR.PATCH`，如 `1.0.0`、`0.2.1`）。

**版本升级规则**：
- `MAJOR`：不兼容的配置变更（如 MCP 工具签名变化、删除功能）
- `MINOR`：新增功能（向下兼容）
- `PATCH`：修复问题（如 skill 文本修正、配置调整）

**操作流程**：
1. 修改对应 bundle 的 `bundle.json` 中的 `version` 字段
2. 运行 `python3 scripts/pack.py --bundle <bundle-name>` 生成新版本 zip
3. 提交到目标平台（新版本会作为新 connector 提交审核）

**注意**：
- 不同 bundle 版本独立，互不影响
- 没有全局版本同步工具，直接编辑 JSON 文件即可
- WorkBuddy 通过 `source` 字段识别同一 bundle 的不同版本，`source` 一旦设定不要更改
- `connector-meta.json` 中的 `version` 字段由 pack.py 在打包时从 `bundle.json` 注入，源码中无需填写

## 更多文档

- RFC 索引：[docs/rfcs/](docs/rfcs/)
- Bundle 打包指南（RFC-0003）：[docs/rfcs/completed/RFC-0003-skill-bundle-refactoring.md](docs/rfcs/completed/RFC-0003-skill-bundle-refactoring.md)
- 发布手册：[docs/releasing.md](docs/releasing.md)
- 迁移记录：[docs/migration/ai_customer_design.md](docs/migration/ai_customer_design.md)
