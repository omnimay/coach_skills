# 发布手册

> 本手册描述 RFC-0003 Bundle 化打包体系的发布流程。

## 发布流程

```mermaid
flowchart LR
    A["修改 Bundle 配置或 Skill"] --> B["更新 bundle.json 版本"]
    B --> C["打包：pack.py"]
    C --> D["WorkBuddy 提交连接器包"]
    D --> E["审核上线后验证"]
```

发布流程必须分别记录：**构建完成、渠道已提交、渠道已上线、客户端已验证**。使用 GitLab Release 描述中的简表记录即可。

| 版本 | Bundle | commit | WorkBuddy 渠道状态 | 验证证据 |
|---|---|---|---|---|
| 示例 `0.1.0` | sales-coach | 完整 SHA | 待提交 | 链接到验收记录 |

要点：

- 每个 bundle 独立版本，来源于其 `bundle.json` 的 `version` 字段。各平台产物继承该版本。
- WorkBuddy 提交采用平台支持的人工流程，CI 只交付提交包；不使用浏览器自动化或非公开 API。
- MCP 工具名称、参数或 Skill 工作流变化时，需要同步升级 bundle 版本并记录变更范围。
- **回滚**：保留既有版本产物。首选修复问题后以更高 patch 版本重新发布。WorkBuddy 市场恢复可能需要重新审核。

## 维护命令手册

维护环境：CI linux、Python 3.11；开发依赖在 `requirements-dev.txt` 固定精确版本。

| 脚本 | 接口 | 行为 |
|---|---|---|
| 检查 | `python scripts/check.py` | 校验技能通用化基线 + bundle manifest |
| 打包 | `python scripts/pack.py [--bundle <name>] [--target <platform>] [--env <env>] [--out <dir>]` | 从 bundles/ 配置生成平台特定 zip |

### check.py（仓库静态检查）

```bash
python3 scripts/check.py             # 全量：frontmatter、禁用词、references、manifest 等
python3 scripts/check.py --only <检查项>  # 只跑所选检查
```

检查项包括：
- `frontmatter`：SKILL.md frontmatter 白名单
- `host-terms`：禁用宿主名称
- `trigger-phrases`：禁用触发词句式
- `mechanism-terms`：禁用宿主私有机制
- `references`：引用文件存在性
- `manifests`：bundle.json 完整性（通用 + WorkBuddy 平台校验）
- `qr-fallback`：二维码降级路径
- `oauth-copy`：OAuth 文案中性

### pack.py（打包）

```bash
python3 scripts/pack.py                                    # 打包所有 bundle（默认 test 环境）
python3 scripts/pack.py --bundle sales-coach               # 打包指定 bundle
python3 scripts/pack.py --bundle sales-coach --target workbuddy  # 指定目标平台
python3 scripts/pack.py --env coach                        # 打包到 coach（正式）环境
python3 scripts/pack.py --out dist/workbuddy               # 指定输出目录（默认）
```

- 从 `bundles/<bundle>/` 读取 `bundle.json`
- 从 `environments.json` 加载环境 URL，替换 bundle.json 中的 `${VAR}` 占位符
- 通用校验（schema、skills 目录、icon）+ WorkBuddy 平台校验（一个 MCP server、HTTPS）
- 从 `skills/` 递归复制引用的 skill（排除 `__pycache__` 和 `.pyc`）
- 生成确定性 zip（固定时间戳/排序/权限）
- 产物落 `dist/workbuddy/`：`<bundle-id>-v<version>.zip`

详细打包说明见 [RFC-0003](rfcs/completed/RFC-0003-skill-bundle-refactoring.md)。

## 发布序列（操作顺序）

1. 修改 Skill 或 Bundle 配置；
2. 更新对应 bundle 的 `bundle.json` 版本字段（遵循 SemVer）；
3. 本地验证：`python3 scripts/check.py` + `python3 -m pytest tests/ -q` + `python3 scripts/pack.py`；
4. 合并审核并打 tag（可选，CI 在 tag 时自动打包）；
5. CI 发布作业：`check.py` → `pytest` → `pack.py`，产物归档为 Release 资产；
6. WorkBuddy：按平台提交流程人工提交连接器包；
7. 各渠道刷新安装并在新会话验证；在 GitLab Release 简表记录四个状态。

CI 细节见 [.gitlab-ci.yml](../.gitlab-ci.yml)。
