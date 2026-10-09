# Bundle 发布 Checklist

> **⚠️ 重要说明**：`release_bundle.py` 是**半自动化**工具，仅覆盖发布六步中的 **③④⑤**（构建、归档、提升）。

## 认证配置

`release_bundle.py` 支持两种认证方式（按优先级）：

1. **glab CLI 自动认证**（推荐）：如果已安装并登录 [glab CLI](https://gitlab.com/gitlab-org/cli)，脚本会自动读取认证信息
   ```bash
   # 检查认证状态
   glab auth status
   
   # 如需登录
   glab auth login --hostname git.mgvai.cn
   ```

2. **环境变量认证**：手动设置以下环境变量
   ```bash
   export GITLAB_API_URL="https://git.mgvai.cn/api/v4"
   export GITLAB_PROJECT_ID="490"  # 从 glab 或 GitLab 项目设置获取
   export GITLAB_TOKEN="<your-personal-access-token>"
   ```

> 💡 **CI 环境**：GitLab CI 会自动注入这些环境变量，无需手动配置。

---

## 发布流程概览

```
① MR 准备（人工）
   ↓
② 打 tag（人工）
   ↓
③ 构建（自动）← release_bundle.py archive
   ↓
④ 归档（自动）← release_bundle.py archive
   ↓
⑤ 提升（自动）← release_bundle.py promote
   ↓
⑥ 渠道交付（人工）
```

---

## 阶段一：MR 准备（人工）

### 任务清单

- [ ] **更新版本号**
  - [ ] 修改 `bundles/<bundle>/bundle.json` 的 `version` 字段
  - [ ] 修改 `bundles/<bundle>/release-plan.json` 的 `version` 字段
  - [ ] 确保两处版本号完全一致

- [ ] **编写 CHANGELOG**
  - [ ] 在 `bundles/<bundle>/CHANGELOG.md` 顶部添加新版本条目
  - [ ] 格式：`## [<version>] - YYYY-MM-DD`
  - [ ] 分类记录：`### Features` / `### Fixes` / `### Changes`
  - [ ] 用用户可见的语言描述变更
  - [ ] 参考现有 CHANGELOG.md 格式（如 `bundles/ai-customer/CHANGELOG.md`）

- [ ] **配置发布矩阵**
  - [ ] 确认 `release-plan.json` 的 `targets` 字段正确
  - [ ] 示例：`{"workbuddy": ["coach", "test", "dingtalk"]}`

- [ ] **静态检查**
  ```bash
  python3 scripts/check.py
  ```
  - [ ] 所有检查通过

- [ ] **本地测试**
  ```bash
  python3 -m pytest tests/ -q
  ```
  - [ ] 所有测试通过

- [ ] **提交 MR**
  - [ ] 提交代码改动
  - [ ] 创建 MR 到 main 分支
  - [ ] 等待 CI 通过
  - [ ] 合并 MR

### 示例

```bash
# 编辑版本号
vim bundles/ai-customer/bundle.json
vim bundles/ai-customer/release-plan.json

# 编写 CHANGELOG
vim bundles/ai-customer/CHANGELOG.md

# 运行检查
python3 scripts/check.py
python3 -m pytest tests/ -q

# 提交
git add .
git commit -m "feat: 新增 XX 功能"
git push origin feat/xxx
```

---

## 阶段二：打 tag（人工）

### 任务清单

- [ ] **切到 main 分支**
  ```bash
  git checkout main
  git pull origin main
  ```

- [ ] **创建 tag**
  - [ ] tag 格式：`<bundle-id>-v<SemVer>`
  - [ ] 示例：`ai-customer-v1.0.2`
  - [ ] 确保与 `bundle.json` 的 `id` 和 `version` 精确匹配

  ```bash
  git tag ai-customer-v1.0.2
  ```

- [ ] **推送 tag**
  ```bash
  git push origin ai-customer-v1.0.2
  ```

- [ ] **验证 tag**
  ```bash
  git tag -l | grep ai-customer
  git show ai-customer-v1.0.2
  ```

---

## 阶段三：构建 + 归档（自动）

### 前置条件

- [ ] **配置 GitLab API 环境变量**
  ```bash
  export GITLAB_API_URL="https://git.mgvai.cn/api/v4"
  export GITLAB_PROJECT_ID="<project-id>"
  export GITLAB_TOKEN="<your-token>"
  ```
  - Token 需要 `api` scope
  - Project ID 可在 GitLab 项目首页查看

- [ ] **（可选）预览发布计划**
  ```bash
  python3 scripts/release_bundle.py plan ai-customer-v1.0.2
  ```

### 执行归档

```bash
python3 scripts/release_bundle.py archive ai-customer-v1.0.2
```

### 预期输出

```
📦 ai-customer-v1.0.2-coach.zip
   构建完成：114356 bytes, SHA-256=9adb179ae2255953...
   上传完成：SHA-256=9adb179ae2255953...
   ✓ 下载核验通过

📦 ai-customer-v1.0.2-test.zip
   构建完成：114359 bytes, SHA-256=80ff546c4c33a610...
   上传完成：SHA-256=80ff546c4c33a610...
   ✓ 下载核验通过

📦 ai-customer-v1.0.2-dingtalk.zip
   构建完成：114366 bytes, SHA-256=80d012a5f300289d...
   上传完成：SHA-256=80d012a5f300289d...
   ✓ 下载核验通过

📝 Release 已创建/更新：ai-customer-v1.0.2
```

### 验证

- [ ] 查看 GitLab Release：`https://git.mgvai.cn/coach/coachskills/-/releases/ai-customer-v1.0.2`
- [ ] 确认 Release 描述包含所有坐标的 SHA-256

---

## 阶段四：提升到 latest/（自动）

### 执行提升

```bash
python3 scripts/release_bundle.py promote ai-customer-v1.0.2
```

### 预期输出

```
  ↓ ai-customer-coach.zip（SHA-256=9adb179ae2255953...）
✓ ai-customer-coach.zip
  ↓ ai-customer-test.zip（SHA-256=80ff546c4c33a610...）
✓ ai-customer-test.zip
  ↓ ai-customer-dingtalk.zip（SHA-256=80d012a5f300289d...）
✓ ai-customer-dingtalk.zip

📂 latest/ 已更新：3 个坐标
```

### 验证

- [ ] 检查 `dist/workbuddy/latest/` 目录
  ```bash
  ls -lh dist/workbuddy/latest/
  ```
- [ ] 确认 `index.json` 已更新
  ```bash
  cat dist/workbuddy/latest/index.json | jq '.items["ai-customer/coach"]'
  ```

### 提交更新

**⚠️ 重要：根据执行方式选择不同的操作路径**

#### 路径 A：通过 CI 自动执行（推荐）

如果通过推送 tag 触发 CI 流水线，CI 会自动完成以下操作：
- 运行 `promote` 命令
- 提交 `dist/<target>/latest/` 变更（workbuddy + universal）
- 推送到 main 分支
- 运行 `upload-oss` 作业，把通用包上传到 OSS（需配置 `OSS_*` CI/CD Variables，未配置时自动跳过）

**无需手动操作**，可直接跳到"阶段五：渠道交付"。

#### 路径 B：本地手动执行

如果是本地手动运行 `promote` 命令，需要手动提交变更：

```bash
git add dist/workbuddy/latest/
git commit -m "chore: promote ai-customer-v1.0.2 to latest/"
git push origin main
```

---

## 阶段五：渠道交付（人工）

### 任务清单

- [ ] **查看 Release**
  - [ ] 打开 GitLab Release 页面
  - [ ] 确认所有 ZIP 文件可下载
  - [ ] 确认 SHA-256 哈希值正确

- [ ] **提交 WorkBuddy**
  - [ ] 下载对应环境的 ZIP 文件
  - [ ] 登录 WorkBuddy 管理后台
  - [ ] 上传 ZIP 文件
  - [ ] 验证安装成功

- [ ] **确认 OSS 通用包**（CI 自动上传，人工核验）
  - [ ] 流水线 `upload-oss` 作业成功（OSS_* 变量未配置时作业跳过，属预期）
  - [ ] 抽查下载 URL 可访问，如：
        `https://megaview.oss-cn-zhangjiakou.aliyuncs.com/mcpskills/coach/<bundle-id>/<bundle-id>-<variant>.zip`

- [ ] **更新 Release 描述**
  - [ ] 编辑 Release 描述中的"渠道状态"表格
  - [ ] 标记已完成的渠道
  - [ ] 记录操作人和时间

### 示例 Release 描述

```markdown
## 发布资产

Tag: `ai-customer-v1.0.2`

- **ai-customer/coach**: `ai-customer-v1.0.2-coach.zip` SHA-256: `9adb179ae2255953...`
- **ai-customer/test**: `ai-customer-v1.0.2-test.zip` SHA-256: `80ff546c4c33a610...`
- **ai-customer/dingtalk**: `ai-customer-v1.0.2-dingtalk.zip` SHA-256: `80d012a5f300289d...`

## 渠道状态

| 渠道 | 状态 | 操作人 | 时间 |
|---|---|---|---|
| ai-customer/coach | ✅ 已提交 | 张三 | 2026-09-29 15:30 |
| ai-customer/test | ⏳ 待提交 | — | — |
| ai-customer/dingtalk | ⏳ 待提交 | — | — |
```

---

## 快速预览（dry-run）

不想实际执行时，可以加 `--dry-run` 参数预览：

```bash
# 预览发布计划
python3 scripts/release_bundle.py plan ai-customer-v1.0.2 --dry-run

# 预览 archive 流程（不实际上传）
python3 scripts/release_bundle.py archive ai-customer-v1.0.2 --dry-run

# 预览 promote 流程（不实际更新 latest/）
python3 scripts/release_bundle.py promote ai-customer-v1.0.2 --dry-run

# 预览全流程
python3 scripts/release_bundle.py full ai-customer-v1.0.2 --dry-run
```

---

## 常见问题

### Q1: 为什么需要手动打 tag？

A: 脚本设计为不执行交互式 git 操作，避免误操作。tag 是发布的触发点，需要人工确认。

### Q2: archive 命令报错 "环境变量未配置"？

A: 需要设置 `GITLAB_API_URL`、`GITLAB_PROJECT_ID`、`GITLAB_TOKEN`。详见"阶段三：前置条件"。

### Q3: promote 命令报错 "版本回退"？

A: 碰撞检测发现你要发布的版本比 `latest/index.json` 中的版本旧。确认版本号是否正确。

### Q4: 如何回滚发布？

A: 
1. 删除 GitLab Release
2. 从 Registry 删除对应包版本
3. 恢复 `latest/index.json` 到上一版本
4. 重新运行 `promote` 命令

### Q5: CI 会自动执行这些步骤吗？

A: 是的。CI 配置了四阶段流水线：
- **check 阶段**：MR 或 main 分支 push 时执行静态检查 + 单元测试
- **build 阶段**：tag push 时自动执行 `archive`（构建 + 上传 Registry + 创建 Release）
- **promote 阶段**：tag push 时自动执行 `promote`（更新 latest/ + 提交 + 推送）
- **upload 阶段**：tag push 时自动上传通用包到 OSS（`OSS_*` 变量未配置时跳过）

环境变量（`GITLAB_API_URL` / `GITLAB_PROJECT_ID` / `GITLAB_TOKEN`）需在 GitLab CI/CD Settings 中配置。详见 `.gitlab-ci.yml`。

---

## 相关文档

- [README.md - 发布流程](../README.md#发布流程)
- [RFC-0006 - Bundle 版本管理与交付](rfcs/approved/RFC-0006-skill-package-versioning-and-delivery.md)
- [bundle-release-management.md](bundle-release-management.md)
