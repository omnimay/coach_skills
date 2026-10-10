# OSS 通用包自动上传（设计说明）

> 本文档描述「通用包」通过 OSS 分发的路径规范与 CI 自动化方案。**全链路已实现**：构建（`pack.py --target universal`）、multi-target promote、上传脚本（`scripts/upload_oss.py`）与 CI `upload-oss` 作业。

## 背景

除 WorkBuddy 平台分发（`dist/workbuddy/latest/`，通过 GitLab Registry）外，公司 Skills 仓库同时提供一个**通用包**路径，供用户直接从网上下载 ZIP 自行安装技能。

通用包与 WorkBuddy 包的区别：

| 维度 | WorkBuddy 包 | 通用包 |
|------|------|------|
| 分发渠道 | GitLab Registry + `dist/workbuddy/latest/` | OSS 直接下载 |
| 目标用户 | WorkBuddy 平台终端用户 | 任何 MCP 客户端用户 |
| 安装方式 | WorkBuddy 平台自动安装 | 用户手动下载 + 配置 |
| 内容 | 技能文件 + mcp.json | 技能文件 + mcp.json + README.md（安装指南） |

**注**：两个渠道的包是完全独立的，当前阶段内容恰好相同，但未来可能分化。

## 路径规范

### OSS 目标路径格式

```
https://megaview.oss-cn-zhangjiakou.aliyuncs.com/mcpskills/coach/<bundle_id>/<bundle-id>-<variant>.zip
```

**注**：
- 文件夹名 `<bundle_id>` 使用**下划线格式**（如 `ai_customer`、`recommend_courses`）
- 文件名 `<bundle-id>` 使用**连字符格式**（如 `ai-customer-coach.zip`）
- 文件名不含版本号（`latest` 语义），始终保持最新。历史版本可追溯 GitLab Generic Package Registry。

### 当前 Bundle 清单

截至 2026-10-09，需要上传的 bundle 共 3 个：

| Bundle ID | 版本 | 技能数 | 说明 |
|-----------|------|--------|------|
| `ai-customer` | 1.0.5 | 2 | 销售陪练与智能评测 |
| `flashcard` | 1.0.4 | 2 | AI 闪卡学习工具 |
| `recommend-courses` | 1.0.3 | 4 | 课程推荐与任务下发 |

### 源文件路径（promote 产物）

OSS 上传的源文件来自 `dist/universal/latest/`（由 `release_bundle.py promote` 生成），**不是** `dist/universal/` 下的带版本号构建中间产物。

发布流程：
```
tag 触发 → archive（构建 + 上传 Registry）→ promote（下载到 dist/<target>/latest/）→ upload-oss（上传到 OSS）
```

`promote` 生成的源文件路径：
```
dist/universal/latest/
├── ai-customer-coach.zip
├── ai-customer-dingtalk.zip
├── ai-customer-test.zip
├── flashcard-coach.zip
├── flashcard-dingtalk.zip
├── flashcard-test.zip
├── recommend-courses-coach.zip
├── recommend-courses-dingtalk.zip
├── recommend-courses-test.zip
└── index.json
```

文件名不含版本号，始终保持最新。`index.json` 记录各坐标的版本、SHA-256、tag 等元数据。

**前提条件**：各 bundle 的 `release-plan.json` 需在 `targets` 中声明 `universal`，promote 才会生成对应产物：
```json
{
  "version": "1.0.0",
  "targets": {
    "workbuddy": ["coach", "test", "dingtalk"],
    "universal": ["coach", "test", "dingtalk"]
  }
}
```

### 目标 OSS 路径

上传映射（源 → 目标）：

| 源文件路径 | OSS 目标 URL |
|-----------|--------------|
| `dist/universal/latest/ai-customer-coach.zip` | `https://megaview.oss-cn-zhangjiakou.aliyuncs.com/mcpskills/coach/ai_customer/ai-customer-coach.zip` |
| `dist/universal/latest/ai-customer-dingtalk.zip` | `https://megaview.oss-cn-zhangjiakou.aliyuncs.com/mcpskills/coach/ai_customer/ai-customer-dingtalk.zip` |
| `dist/universal/latest/ai-customer-test.zip` | `https://megaview.oss-cn-zhangjiakou.aliyuncs.com/mcpskills/coach/ai_customer/ai-customer-test.zip` |
| `dist/universal/latest/flashcard-coach.zip` | `https://megaview.oss-cn-zhangjiakou.aliyuncs.com/mcpskills/coach/flashcard/flashcard-coach.zip` |
| `dist/universal/latest/flashcard-dingtalk.zip` | `https://megaview.oss-cn-zhangjiakou.aliyuncs.com/mcpskills/coach/flashcard/flashcard-dingtalk.zip` |
| `dist/universal/latest/flashcard-test.zip` | `https://megaview.oss-cn-zhangjiakou.aliyuncs.com/mcpskills/coach/flashcard/flashcard-test.zip` |
| `dist/universal/latest/recommend-courses-coach.zip` | `https://megaview.oss-cn-zhangjiakou.aliyuncs.com/mcpskills/coach/recommend_courses/recommend-courses-coach.zip` |
| `dist/universal/latest/recommend-courses-dingtalk.zip` | `https://megaview.oss-cn-zhangjiakou.aliyuncs.com/mcpskills/coach/recommend_courses/recommend-courses-dingtalk.zip` |
| `dist/universal/latest/recommend-courses-test.zip` | `https://megaview.oss-cn-zhangjiakou.aliyuncs.com/mcpskills/coach/recommend_courses/recommend-courses-test.zip` |

**命名规则**：
- OSS 路径中的文件夹名使用**下划线格式**（如 `ai_customer`、`recommend_courses`，非连字符）
- OSS 文件名使用**连字符格式**（如 `ai-customer-coach.zip`）
- 每次上传覆盖同名文件，保持 `latest` 语义
- 上传映射由 `index.json` 的 `bundleId` + `latestFile` 字段驱动（不解析文件名）——即使某 bundle 的 `distributionName` 与 bundle-id 分歧，OSS 路径仍然正确

当前 `latest` 对象按文件逐个覆盖，极短窗口内不同变体可能来自不同版本；直接下载单个 ZIP 不受影响。若后续需要整套 bundle 的原子切换，应增加版本化 OSS 前缀和最后切换的 manifest 指针。

## 通用包内容

通用包 ZIP 包含：

```
<bundle-id>-<variant>.zip
├── skills/                    # 技能文件（与 WorkBuddy 包相同）
│   ├── <skill-1>/SKILL.md
│   ├── <skill-2>/SKILL.md
│   └── ...
├── mcp.json                   # MCP server 配置模板
└── README.md                  # 安装指南（通用流程）
```

### README.md 安装指南

每个 universal 包的 `README.md` 由 `templates/universal-readme.md` 模板自动生成（见 `scripts/bundle_builder/targets/universal.py`），包含：

- Bundle 名称、描述（从 `bundle.json` 的 `presentation.locales` 读取）
- 技能列表（从 `bundle.json` 的 `skills` 数组遍历）
- `mcp.json` 示例配置（由 `generate_mcp_json()` 生成，含占位符解析）
- 安装指南（配置 MCP Server、安装技能、验证连接）
- 故障排查指南

如需调整模板样式，修改 `templates/universal-readme.md` 即可。

## 实现方式

| 模块 | 状态 | 说明 |
|------|------|------|
| 构建脚本 | ✅ 已完成 | `scripts/pack.py --target universal` 生成通用格式 ZIP |
| promote 流程 | ✅ 已完成 | `release_bundle.py promote` 按 target 分组写独立 `index.json`；各 bundle `release-plan.json` 已声明 universal 坐标 |
| 上传脚本 | ✅ 已完成 | `scripts/upload_oss.py`（oss2 SDK，index.json 驱动映射 + sha256 核验） |
| CI 作业 | ✅ 已完成 | `.gitlab-ci.yml` 第四阶段 `upload-oss`，promote 产物经 artifacts 传递 |

### 构建命令（已实现）

```bash
# 本地调试用——手动打包单个 bundle
python3 scripts/pack.py --bundle ai-customer --target universal --env coach

# CI 中由 release_bundle.py 调用，不需要手动执行
```

### 上传脚本（已实现：scripts/upload_oss.py）

```bash
# 预览上传计划（完整本地校验：index/zip 配对 + SHA-256 核验；无需凭证、无需安装 oss2）
python3 scripts/upload_oss.py --dry-run

# 实际上传（默认目录 dist/universal/latest/）
python3 scripts/upload_oss.py

# 仅在 RAM 策略无法授予 GetObject/HEAD 权限时使用
python3 scripts/upload_oss.py --skip-remote-verify
```

核心逻辑：
- **index.json 驱动映射**：`oss_key = mcpskills/coach/{bundle_id_with_underscores}/{item.latestFile}`，其中 `bundle_id_with_underscores = item.bundleId.replace("-", "_")`，不解析文件名
- **上传前校验**：本地 SHA-256 与 index 记录一致才上传；index 条目缺文件 / 目录存在孤儿 zip 均 fail-fast
- **覆盖上传**：`put_object_from_file` + `Content-Type: application/zip` + `Cache-Control: no-cache` + `x-oss-object-acl: public-read`（latest 对象变更后不长期复用旧包；bucket 为 private 模式，通过对象级 ACL 实现公开可读）
- **上传可靠性**：网络错误和 408/429/5xx 自动指数退避重试；上传请求写入 SHA-256 元数据，并通过 HEAD 核验对象大小和元数据
- **索引安全校验**：拒绝路径穿越、非法文件名、重复 OSS key、损坏 SHA-256 和目录外 symlink，避免错误索引误传对象
- **oss2 惰性 import**：`--dry-run` 零依赖可跑；正式上传缺凭证或缺 SDK 时给出明确报错

### CI 作业（已实现）

```yaml
# .gitlab-ci.yml（节选）
stages: [check, build, promote, upload]

promote:
  # ……（promote 脚本同前）……
  artifacts:
    paths: [dist/universal/latest/]    # 供 upload-oss 上传
    expire_in: 1 week

upload-oss:
  stage: upload
  image: python:3.11
  resource_group: release-dist         # 与 build/promote 串行，防并发覆盖同一 latest key
  script:
    - pip install --no-cache-dir oss2==2.19.1
    - python3 scripts/upload_oss.py dist/universal/latest/
  rules:
    # 全部变量未配置时跳过；只配置部分变量则执行并明确失败，避免静默漏发
    - if: '$CI_COMMIT_TAG && $OSS_ACCESS_KEY_ID && $OSS_ACCESS_KEY_SECRET && $OSS_ENDPOINT && $OSS_BUCKET'
    - if: '$CI_COMMIT_TAG && ($OSS_ACCESS_KEY_ID || $OSS_ACCESS_KEY_SECRET || $OSS_ENDPOINT || $OSS_BUCKET)'
  needs:
    - job: promote
      artifacts: true
```

上传失败会使流水线失败（可重试；确定性构建 → 覆盖上传幂等）。

### GitLab CI Variables 配置

Settings → CI/CD → Variables 添加：

| 变量 | 值 | 说明 |
|---|---|---|
| `OSS_ACCESS_KEY_ID` | \<子账号 AK\> | 建议仅授予目标前缀的 PutObject + GetObject（用于上传后 HEAD 核验）权限 |
| `OSS_ACCESS_KEY_SECRET` | \<子账号 SK\> | 勾选 Masked |
| `OSS_ENDPOINT` | `oss-cn-zhangjiakou.aliyuncs.com` | 区域 endpoint，**不含 bucket 名**（含则签名错误） |
| `OSS_BUCKET` | `megaview` | |
| `OSS_SECURITY_TOKEN` | 可选 | 使用 RAM/STS 临时凭证时填写，与 AK/SK 一起使用 |

上传脚本默认会执行一次 `HeadObject` 核验，因此 RAM 策略需要同时允许 `oss:PutObject` 和 `oss:GetObject`；若环境只能授予写权限，可显式使用 `--skip-remote-verify`，但会失去上传后的远端核验。

**Protected 变量注意**：若勾选 Protected，需确保发布 tag 是受保护 tag，否则流水线拿不到变量，`upload-oss` 作业会被规则跳过。

## 与现有发布流程的关系

通用包 OSS 上传是现有 6 步发布流程的**补充渠道**（类似步骤⑥ WorkBuddy 渠道交付），不替代 Registry 归档和 `latest/` 提升：

```
③ 构建 → ④ 归档（Registry）→ ⑤ 提升（dist/<target>/latest/）→ ⑥-a WorkBuddy 渠道 → ⑥-b OSS 通用包（CI 自动上传）
```

所有渠道共享同一份构建产物（同输入 → 同哈希），仅分发路径不同。promote 阶段同时生成 `dist/workbuddy/latest/` 和 `dist/universal/latest/`，OSS 上传直接读取后者（经 CI artifacts 传递）。
