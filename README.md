<div align="center">
  <img src="assets/GitHub项目主页封面横幅设计.jpeg" alt="coachskills banner" width="100%" />
</div>

# coachskills — 公司 Skills 仓库

公司内部 Agent 技能仓库。技能放在 `skills/` 下，通过 `bundles/` 配置组合成不同的发布包（bundle），构建时生成各平台原生格式。

## 项目结构

```
coachskills/
├── skills/                          # 技能目录（中立池，每个技能自包含）
│   ├── ai_customer_design/                # 销售陪练：建课/改课/资料上传/练习交付
│   ├── flashcard_design/                  # 学习闪卡：出题/验题/双发布模式
│   ├── coach-mcp-connect/                 # 横切：用户侧连接恢复（随 bundle 分发，mcp_diagnose 自助诊断）
│   ├── connect/                           # 横切：开发/运维侧完整 MCP 客户端与排障（不随 bundle 分发）
│   └── connect/                           # 横切：开发/运维侧完整 MCP 客户端与排障（不随 bundle 分发）
│
├── bundles/                         # 技能包目录（每个 bundle = 一个市场分发单元）
│   ├── sales-coach/                 # 深维智讯・销售陪练（ai-customer + coach-mcp-connect）
│   │   ├── bundle.json              # 通用定义（组合、版本、展示、连接、市场目标）
│   │   ├── icon.svg                 # 包图标
│   │   └── CONNECTOR.md             # 内部产品文档（端点/技能集/工具域）
│   └── flashcard/                   # 深维智信·学习闪卡
│       ├── bundle.json
│       ├── icon.svg
│       └── CONNECTOR.md
│
├── scripts/                         # 构建工具（不随包分发）
│   ├── check.py                     # 静态检查
│   ├── pack.py                      # 打包入口（--bundle / --target / --env）
│   ├── file_validator.py            # 文件边界校验（敏感文件/路径穿越/临时文件）
│   └── bundle_builder/              # 构建模块
│       ├── bundle.py                # 通用层（配置读取、校验、ZIP 组装、确定性压缩）
│       └── workbuddy.py             # WorkBuddy 平台适配（connector-meta/mcp 生成）
│
├── tests/                           # 测试用例（check / pack / bundle / workbuddy）
├── docs/                            # 文档（RFC、迁移、规范、安装、发布手册）
│   ├── rfcs/                        # RFC 文档
│   ├── migration/                   # 迁移记录
│   ├── installation/                # 平台安装指南
│   └── releasing.md                 # 发布手册
│
├── assets/                          # 静态资源
├── environments.json                # 环境 URL 注册表（test / coach / dingtalk）
├── README.md                        # 本文件
├── INSTALL.md                       # 用户安装指南
├── RELEASE-NOTES.md                 # 版本发布记录
└── .gitlab-ci.yml                   # CI：MR 检查 + tag 发布
```

## 技能列表

| 技能 | 说明 |
| --- | --- |
| [ai_customer_design](skills/ai_customer_design/SKILL.md) | 销售陪练：通过宿主 MCP 连接 enterprise-training，完成建课/改课/资料上传/练习链接与二维码交付 |
| [flashcard_design](skills/flashcard_design/SKILL.md) | 学习闪卡：基于资料/主题出题、验题，按用户角色路由双发布模式（管理员编辑链接 / 学员自动练习） |
| [coach-mcp-connect](skills/coach-mcp-connect/SKILL.md) | 横切：用户侧 MCP 连接恢复（bundle 安装后工具不可用时的自助诊断，`mcp_diagnose.py`） |
| [connect](skills/connect/SKILL.md) | 横切：开发/运维侧完整 MCP 客户端（OAuth PKCE/流式调用/registry 命令，自含 `scripts/mcp_client.py`） |

## Bundle 列表

| Bundle | 说明 | Skills | 包格式 |
| --- | --- | --- | --- |
| [sales-coach](bundles/sales-coach/) | 深维智讯・销售陪练 | ai_customer_design, coach-mcp-connect | `sales-coach-v<version>-<env>.zip` |
| [flashcard](bundles/flashcard/) | 深维智信·学习闪卡 | flashcard_design | `flashcard-v<version>-<env>.zip` |

端点由 `environments.json` 按环境解析（test / coach / dingtalk），打包时注入 `bundle.json` 的 `${MCP_URL}` 占位符。

| 环境 | MCP 端点 |
|------|----------|
| test | `https://mcp.test.omnimay.com/coach/mcp` |
| coach | `https://mcp.omnimay.com/coach/mcp` |
| dingtalk | `https://aicoach.eapps.dingtalkcloud.com/omnimay/coach/mcp` |

## 维护命令

```bash
# 仓库静态检查（含技能通用化规则、bundle manifest 校验、文件边界）
python3 scripts/check.py

# 打包 bundle（默认 test 环境）
python3 scripts/pack.py
python3 scripts/pack.py --bundle flashcard          # 打包指定 bundle
python3 scripts/pack.py --bundle sales-coach --env coach   # 指定 bundle + 环境
python3 scripts/pack.py --env dingtalk              # 钉钉云环境
python3 scripts/pack.py --out dist/custom           # 自定义产物目录
```

产物命名：`<bundle>-v<version>-<env>.zip`（如 `flashcard-v1.0.0-coach.zip`），单源生成 connector-meta.json / mcp.json。打包前校验：bundle schema（semver/locale/icon）、WorkBuddy 约束（单 server、HTTPS、targets 字段）、skill 文件边界（路径穿越/敏感文件/临时文件）。产物 `dist/` 不入库。

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
python3 scripts/check.py          # 全量检查
python3 scripts/check.py --only frontmatter   # 只查 frontmatter 白名单
python3 scripts/check.py --only host-terms    # 只查禁用术语
python3 -m pytest tests/ -q       # 跑测试
```

完整规则见 [RFC-0001 §3.14](docs/rfcs/completed/RFC-0001-superpowers-style-company-skills.md)。

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
| `mcp.servers` | 是 | MCP 端点定义（key=server 名，含 `transport` 与 `url`；`url` 支持 `${ENV_VAR}` 占位） |
| `targets.workbuddy` | 是 | WorkBuddy 平台目标（`source` / `type` / `minVersion`） |

构建流程详见 [RFC-0003](docs/rfcs/completed/RFC-0003-skill-bundle-refactoring.md) 与 [docs/releasing.md](docs/releasing.md)。

## 安装

各平台安装步骤见对应文档（本 README 不重复）：

- WorkBuddy：见 [docs/releasing.md](docs/releasing.md)
- 用户级使用：见 [INSTALL.md](INSTALL.md)
