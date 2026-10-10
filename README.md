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
│   ├── flashcard_design/                  # 学习闪卡：出题/验题/权限分叉
│   └── coach-mcp-connect/                 # 横切：用户侧连接恢复（随 bundle 分发，mcp_diagnose 自助诊断）
│
├── bundles/                         # 技能包目录（每个 bundle = 一个市场分发单元）
│   ├── ai-customer/                 # 深维智讯・销售陪练（ai-customer + coach-mcp-connect）
│   │   ├── bundle.json              # 通用定义（组合、版本、展示、连接、市场目标）
│   │   ├── CHANGELOG.md             # 版本变更记录
│   │   ├── release-plan.json        # 发布矩阵（target × 变体）
│   │   ├── icon.svg                 # 包图标
│   │   └── CONNECTOR.md             # 内部产品文档（端点/技能集/工具域）
│   └── flashcard/                   # 深维智讯·学习闪卡
│       ├── bundle.json
│       ├── CHANGELOG.md
│       ├── release-plan.json
│       ├── icon.svg
│       └── CONNECTOR.md
│
├── dist/                            # 交付目录（按 target 分目录）
│   ├── workbuddy/                   # WorkBuddy 平台分发
│   │   └── latest/                  # 各坐标最新正式 ZIP + index.json（入库）
│   └── universal/                   # 通用包分发（OSS 下载）
│       └── *.zip                    # 含安装指南的通用包
│
├── scripts/                         # 构建工具（不随包分发）
│   ├── check.py                     # 静态检查（含 release-plan / distribution 检查项）
│   ├── pack.py                      # 打包入口（--bundle / --target / --env）
│   ├── release_bundle.py            # 发布入口（tag 解析 / 归档 / 提升）
│   ├── file_validator.py            # 文件边界校验（敏感文件/路径穿越/临时文件）
│   └── bundle_builder/              # 构建模块
│       ├── bundle.py                # 通用层（配置读取、校验、SemVer）
│       ├── build.py                 # 共用组包函数（pack.py 和 release_bundle.py 共享）
│       ├── workbuddy.py             # WorkBuddy 平台适配（connector-meta/mcp 生成）
│       ├── gitlab_client.py         # GitLab API 封装（Registry / Release）
│       └── targets/                 # Target 平台实现（OOP 架构）
│           ├── base.py              # TargetBuilder Protocol 定义
│           ├── workbuddy.py         # WorkbuddyTarget 实现
│           └── universal.py         # UniversalTarget 实现（通用包分发）
│
├── tests/                           # 测试用例（check / pack / bundle / workbuddy）
├── docs/                            # 文档（RFC、迁移、规范、安装、发布手册）
│   ├── rfcs/                        # RFC 文档（draft / approved / completed）
│   ├── migration/                   # 迁移记录
│   ├── installation/                # 平台安装指南
│   └── releasing.md                 # 发布手册
│
├── assets/                          # 静态资源
├── environments.json                # 环境 URL 注册表（test / coach / dingtalk）
├── README.md                        # 本文件
├── INSTALL.md                       # 用户安装指南
├── RELEASE-NOTES.md                 # 旧式统一版本记录（已冻结为历史导航）
└── .gitlab-ci.yml                   # CI：MR 检查 + tag 发布
```

## 技能列表

| 技能 | 说明 |
| --- | --- |
| [ai_customer_design](skills/ai_customer_design/SKILL.md) | 销售陪练：通过宿主 MCP 连接 enterprise-training，完成建课/改课/资料上传/练习链接与二维码交付 |
| [flashcard_design](skills/flashcard_design/SKILL.md) | 学习闪卡：基于资料/主题出题、验题，按用户角色路由权限分叉（管理员编辑链接 / 学员自动练习） |
| [coach-mcp-connect](skills/coach-mcp-connect/SKILL.md) | 横切：用户侧 MCP 连接恢复（bundle 安装后工具不可用时的自助诊断，`mcp_diagnose.py`） |

## Bundle 列表

| Bundle | 发行别名 | 说明 | Skills | 包格式 |
| --- | --- | --- | --- | --- |
| [ai-customer](bundles/ai-customer/) | `ai-customer` | 深维智讯・销售陪练 | ai_customer_design, coach-mcp-connect | `ai-customer-v<version>-<env>.zip` |
| [flashcard](bundles/flashcard/) | `flashcard`（= id） | 深维智讯·学习闪卡 | flashcard_design, coach-mcp-connect | `flashcard-v<version>-<env>.zip` |
| [recommend-courses](bundles/recommend-courses/) | `recommend-courses`（= id） | 深维智讯·课程推荐 | ai_customer_design, coach-mcp-connect, recommend_courses, flashcard_design | `recommend-courses-v<version>-<env>.zip` |

> 发行别名（`distributionName`）仅用于 `latest/` 下载文件名前缀，不影响包内身份。在 `bundle.json` 的 `targets.workbuddy.distributionName` 中声明；未声明时默认等于 `id`。详见 [RFC-0006](docs/rfcs/approved/RFC-0006-skill-package-versioning-and-delivery.md)。

端点由 `environments.json` 按环境解析（test / coach / dingtalk），打包时注入 `bundle.json` 的 `${MCP_URL}` 占位符。

| 环境 | MCP 端点 |
|------|----------|
| test | `https://mcp.test.omnimay.com/coach/mcp` |
| coach | `https://mcp.omnimay.com/coach/mcp` |
| dingtalk | `https://aicoach.eapps.dingtalkcloud.com/omnimay/coach/mcp` |

## 维护命令

```bash
# 仓库静态检查（含技能通用化规则、bundle manifest 校验、文件边界、release-plan、distribution）
python3 scripts/check.py

# 打包 bundle（默认 workbuddy target，test 环境）
python3 scripts/pack.py
python3 scripts/pack.py --bundle flashcard          # 打包指定 bundle
python3 scripts/pack.py --bundle ai-customer --env coach   # 指定 bundle + 环境
python3 scripts/pack.py --target universal --env dingtalk  # 打包通用包（OSS 分发）
python3 scripts/pack.py --out dist/custom           # 自定义产物目录
```

产物命名：`<bundle>-v<version>-<env>.zip`（如 `flashcard-v1.0.1-coach.zip`），单源生成 connector-meta.json / mcp.json。打包前校验：bundle schema（semver/locale/icon）、WorkBuddy 约束（单 server、HTTPS、targets 字段）、skill 文件边界（路径穿越/敏感文件/临时文件）。`dist/<target>/latest/` 入库（各坐标最新正式 ZIP）；旧版带版本 ZIP 在迁移完成前暂留工作树。

### Target 平台架构

构建系统采用 **TargetBuilder OOP 架构**，将平台特定逻辑封装为独立的 Target 类：

| Target | 用途 | 产物特点 |
|--------|------|----------|
| `workbuddy` | WorkBuddy 平台分发 | 包含 connector-meta.json、auth-profile.json、icon |
| `universal` | 通用包分发（OSS 下载） | 包含 README.md 安装指南，用户自行配置 MCP 客户端 |

**架构设计**：
- `TargetBuilder` Protocol 定义统一接口（`validate` + `build_entries`）
- `build.py` 处理通用文件（mcp.json、skills），Target 类处理平台特定文件
- 每个 Target 独立校验、独立生成产物，便于扩展新平台

**扩展新 Target**：
1. 在 `scripts/bundle_builder/targets/` 下创建新文件
2. 实现 `TargetBuilder` Protocol（`validate` + `build_entries` 方法）
3. 在 `build.py` 的 target 选择逻辑中注册

详见 [RFC-0003](docs/rfcs/completed/RFC-0003-skill-bundle-refactoring.md) 和代码注释。

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
- `CHANGELOG.md`：版本变更记录（每发布版本简述用户可见变更）
- `release-plan.json`：发布矩阵（声明本次发布的 target × 变体）
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
| `targets.workbuddy` | 是 | WorkBuddy 平台目标（`source` / `distributionName`? / `type` / `minVersion`） |

构建流程详见 [RFC-0003](docs/rfcs/completed/RFC-0003-skill-bundle-refactoring.md) 与 [docs/releasing.md](docs/releasing.md)。

## 发布流程

> 详见 [docs/releasing.md](docs/releasing.md) 和 [RFC-0006](docs/rfcs/approved/RFC-0006-skill-package-versioning-and-delivery.md)

### ⚠️ 半自动化工具说明

`release_bundle.py` 是**半自动化**发布工具，仅覆盖发布六步中的 **③④⑤**（构建、归档、提升）。以下步骤需要**人工完成**：

- ① MR 准备（更新版本号、编写 CHANGELOG、配置 release-plan.json）
- ② 打 tag（创建 Git tag）
- ⑥ 渠道交付（提交 WorkBuddy 等平台）

### 🔐 认证方式

`release_bundle.py` 支持两种认证方式（按优先级）：

1. **glab CLI 自动认证**（推荐）：如果已安装并登录 [glab CLI](https://gitlab.com/gitlab-org/cli)，脚本会自动读取认证信息，无需手动配置环境变量
   ```bash
   # 检查 glab 认证状态
   glab auth status
   
   # 如需登录
   glab auth login --hostname git.mgvai.cn
   ```

2. **环境变量认证**：手动设置以下环境变量
   ```bash
   export GITLAB_API_URL="https://git.mgvai.cn/api/v4"
   export GITLAB_PROJECT_ID="490"
   export GITLAB_TOKEN="<your-personal-access-token>"
   ```

> 💡 **提示**：CI 环境中会自动注入这些环境变量，无需手动配置。

### 发布六步

| 步骤 | 做什么 | 自动化 | 关键约束 |
|---|---|---|---|
| ① MR 准备 | 改代码 + 升版本 + 写 CHANGELOG + 写 release-plan.json | ❌ 人工 | `check.py` 静态检查；合并前不动 `latest/` |
| ② 打 tag | 创建 `<bundle-id>-v<SemVer>` 受保护 tag | ❌ 人工 | tag 与 bundle.json 的 id/version 精确匹配 |
| ③ 构建 | 共用 `build_bundle_zip` 函数 | ✅ 自动 | 同输入 → 同哈希 |
| ④ 归档 | 上传 Registry + 创建 Release | ✅ 自动 | 同坐标同哈希 = 安全重试；不同哈希 = 阻断 |
| ⑤ 提升 | 复制 ZIP 到 `latest/`，更新 `index.json` | ✅ 自动 | 全有或全无；碰撞检测读默认分支实际索引 |
| ⑥ 渠道交付 | 人工提交 WorkBuddy | ❌ 人工 | Release 描述分两段：机器资产 + 人工渠道状态 |

### 完整发布 Checklist

#### 阶段一：MR 准备（人工）

- [ ] 更新 `bundles/<bundle>/bundle.json` 的 `version` 字段
- [ ] 更新 `bundles/<bundle>/release-plan.json` 的 `version` 字段
- [ ] 编写 `bundles/<bundle>/CHANGELOG.md`，记录本次变更
- [ ] 运行 `python3 scripts/check.py` 确保静态检查通过
- [ ] 提交代码并创建 MR，合并到 main

#### 阶段二：打 tag（人工）

> **核心原则**：tag 名称必须与 `bundle.json` 中的 `id` 和 `version` 字段**完全一致**。CI 会用 tag 名称构建包，如果不匹配会导致发布失败。

**逐步执行**：

```bash
# 1. 确认你在 main 分支且已是最新
git checkout main
git pull origin main

# 2. 查看当前 bundle.json 的版本号（以 ai-customer 为例）
cat bundles/ai-customer/bundle.json | grep '"version"'
# 输出示例："version": "1.0.5"

# 3. 构造 tag 名称 = bundle-id + "-v" + 版本号
#    例如：id="ai-customer", version="1.0.5" → tag 名称为 ai-customer-v1.0.5

# 4. 创建 tag
git tag ai-customer-v1.0.5

# 5. 推送 tag 到远程仓库
git push origin ai-customer-v1.0.5
```

**⚠️ 常见错误**：
- **版本号不一致**：tag 写 `v1.0.5` 但 `bundle.json` 里是 `1.0.4` → CI 的 `plan` 阶段会报错
- **拼写错误**：`ai-customer-v1.0.5` 写成 `ai_customer-v1.0.5`（下划线 vs 连字符）→ tag 格式校验失败
- **重复 tag**：如果 tag 已存在，先删除再创建：`git tag -d ai-customer-v1.0.5 && git push origin :refs/tags/ai-customer-v1.0.5`

**推送 tag 后会发生什么**：

CI 自动触发四阶段流水线（无需人工干预）：

| 阶段 | 自动执行内容 | 产物 |
|---|---|---|
| `check` | 静态检查 + 单元测试 | CI 通过/失败状态 |
| `build` | `plan`（校验 tag 一致性）→ 构建 ZIP → 上传 Registry → 创建 Release | Release 页面 + Registry 归档 |
| `promote` | 复制 ZIP 到 `dist/<target>/latest/` → 更新 `index.json` → 提交推送 main | `dist/workbuddy/latest/` + `dist/universal/latest/` |
| `upload-oss` | 上传通用包到 OSS（`OSS_*` 变量未配置时跳过） | OSS 可访问的 ZIP 文件 |

**人工仅需确认**：
1. 流水线是否全部通过（GitLab → CI/CD → Pipelines）
2. Release 描述中的 SHA-256 是否正确
3. 然后执行阶段五：手动提交 WorkBuddy 平台

#### 阶段三：构建 + 归档（自动）

```bash
# 运行 archive 命令（构建 + 上传 Registry + 创建 Release）
python3 scripts/release_bundle.py archive ai-customer-v1.0.5

# 输出示例（以 ai-customer 为例，包含 3 个变体）：
# 📦 ai-customer-v1.0.5-coach.zip
#    构建完成：114356 bytes, SHA-256=9adb179ae2255953...
#    上传完成：SHA-256=9adb179ae2255953...
#    ✓ 下载核验通过
# 📦 ai-customer-v1.0.5-test.zip
#    构建完成：114359 bytes, SHA-256=80ff546c4c33a610...
#    上传完成：SHA-256=80ff546c4c33a610...
#    ✓ 下载核验通过
# 📦 ai-customer-v1.0.5-dingtalk.zip
#    构建完成：114366 bytes, SHA-256=80d012a5f300289d...
#    上传完成：SHA-256=80d012a5f300289d...
#    ✓ 下载核验通过
# 📝 Release 已创建/更新：ai-customer-v1.0.5
```

**注意**：需要先配置 GitLab API 环境变量：
```bash
export GITLAB_API_URL="https://git.mgvai.cn/api/v4"
export GITLAB_PROJECT_ID="<project-id>"
export GITLAB_TOKEN="<your-token>"  # 需要 api scope
```

#### 阶段四：提升到 latest/（自动 / 本地）

**CI 自动 promote**（需要 push 权限）：

```bash
# CI 自动执行（tag 触发），不需要手动运行
python3 scripts/release_bundle.py promote ai-customer-v1.0.5

# 输出示例：
#   ↓ ai-customer-coach.zip（SHA-256=9adb179ae2255953...）
# ✓ workbuddy/ai-customer-coach.zip
# ✓ universal/ai-customer-coach.zip
# 📂 latest/ 已更新：6 个坐标（workbuddy, universal）
```

**本地 promote**（无 push 权限时使用）：

如果你没有直接 push 到 main 的权限，可以本地运行 promote，然后将 `dist/<target>/latest/` 随 MR 合入：

```bash
# 1. 确保 CI 的 archive 阶段已成功（包已在 Registry）

# 2. 本地运行 promote（使用 glab CLI 认证或环境变量）
python3 scripts/release_bundle.py promote ai-customer-v1.0.5

# 3. 提交生成的 latest/ 文件
git add dist/
git commit -m "chore(dist): promote ai-customer-v1.0.5 to latest/"

# 4. 推送并在 MR 中合入 main
git push origin HEAD
# 创建 MR → 合并到 main
```

本地 promote 需要认证（按优先级）：
1. 环境变量 `GITLAB_API_URL` / `GITLAB_PROJECT_ID` / `GITLAB_TOKEN`（PAT）
2. GitLab CI 内置变量 `CI_API_V4_URL` / `CI_PROJECT_ID` / `CI_JOB_TOKEN`（仅 CI 环境）
3. glab CLI 配置 `~/.config/glab-cli/config.yml`（本地开发推荐）

#### 阶段五：渠道交付（人工）

- [ ] 在 GitLab 查看 Release：`https://git.mgvai.cn/coach/coachskills/-/releases/ai-customer-v1.0.5`
- [ ] 手动提交 WorkBuddy 平台（从 Release 下载 ZIP 并上传）
- [ ] 更新 Release 描述中的"渠道状态"表格，标记已完成的渠道

### 快速预览（dry-run）

不想实际执行时，可以加 `--dry-run` 参数预览：

```bash
# 预览发布计划（plan 本身不执行任何修改操作，可安全运行）
python3 scripts/release_bundle.py plan ai-customer-v1.0.5

# 预览 archive 流程（不实际上传）
python3 scripts/release_bundle.py archive ai-customer-v1.0.5 --dry-run

# 预览 promote 流程（不实际更新 latest/）
python3 scripts/release_bundle.py promote ai-customer-v1.0.5 --dry-run

# 预览全流程（plan + archive + promote）
python3 scripts/release_bundle.py full ai-customer-v1.0.5 --dry-run
```

**取包**：日常从 `dist/<target>/latest/` 取最新正式包；历史版本在 GitLab Generic Package Registry。

## 安装

各平台安装步骤见对应文档（本 README 不重复）：

- 取最新正式包：`dist/<target>/latest/`（如 `dist/workbuddy/latest/ai-customer-coach.zip`）
- 取历史版本：GitLab Generic Package Registry（按 bundle/version/target/variant 检索）
- WorkBuddy 渠道提交：见 [docs/releasing.md](docs/releasing.md)
- 用户级使用：见 [INSTALL.md](INSTALL.md)

## 通用包分发（OSS）

除 WorkBuddy 平台分发外，公司 Skills 仓库同时提供**通用包**路径，供用户直接从网上下载 ZIP 自行安装技能。

- **OSS 路径**：`mcpskills/coach/<bundle_id>/<bundle-id>-<variant>.zip`（文件夹名下划线，文件名连字符）
- **示例**：
  - `https://megaview.oss-cn-zhangjiakou.aliyuncs.com/mcpskills/coach/ai_customer/ai-customer-coach.zip`
  - `https://megaview.oss-cn-zhangjiakou.aliyuncs.com/mcpskills/coach/ai_customer/ai-customer-dingtalk.zip`

通用包与 WorkBuddy 包是独立的分发渠道，当前阶段内容相同。通用包内含 `README.md` 安装指南，用户下载后参考配置 MCP 客户端。tag 触发的 CI 流水线在 promote 后自动上传到 OSS（`upload-oss` 作业；`OSS_*` 变量未配置时跳过，详见 [docs/oss-upload-automation.md](docs/oss-upload-automation.md)）。
