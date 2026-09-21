# WorkBuddy 安装与提交指南

> **状态标注**：本文为 RFC-0002 多 Plugin 打包体系的目标流程文档。WorkBuddy 客户端不识别仓库内的 `.workbuddy-plugin/` 目录——它只是配置源。实际提交包由 `pack.py` 从 plugin 配置生成。

## 连接器包结构

每个 plugin 打包后生成独立的 WorkBuddy 连接器 zip：

```text
sales-coach-v0.1.0.zip             # 文件名 = plugin名-v版本号.zip
├── connector-meta.json            # 来自 .workbuddy-plugin/sales-coach/connector-meta.json
├── mcp.json                       # 来自 .workbuddy-plugin/sales-coach/mcp.json
├── icon.svg                       # 来自 .workbuddy-plugin/sales-coach/icon.svg
└── skills/                        # 根据 pack_config.json 引用从 skills/ 复制
    └── ai_customer_design/
        ├── SKILL.md
        └── references/
```

生成命令：

```bash
python3 scripts/pack.py --plugin sales-coach   # 打包指定 plugin
python3 scripts/pack.py                        # 打包所有 plugin
```

产物落 `dist/workbuddy/`。完整打包说明见 [.workbuddy-plugin/README.md](../../.workbuddy-plugin/README.md)。

## 员工安装

审核上线后，在 WorkBuddy 客户端的连接器市场中搜索本连接器安装。连接与 OAuth 授权由 WorkBuddy 自家账号体系管理，连接器不带 Token、不带固定 Authorization header。

## 提交流程（人工）

WorkBuddy 提交采用平台支持的人工流程：

1. 构建提交包（CI 发布作业或本地 `pack.py`）；
2. 经 WorkBuddy 官方人工提交通道上传连接器包与变更说明；
3. 分别记录四个状态：**构建完成、渠道已提交、渠道已上线、客户端已验证**（记于 GitLab Release 描述中的简表）；
4. 审核未通过时：修复配置后重新打包提交。

提交字段（`name` / `name_zh` / `name_en` / `description*` / `source` / `type` / `version` / `minWorkbuddyVersion` / `examples*`）以 WorkBuddy 连接器规范为准。

## minWorkbuddyVersion 待预检标注

`minWorkbuddyVersion: 4.24.0` 是文档基线，不是已验证的产品支持下限。核实路径：

- 用手工预览包在 ≥2 个版本跨度的 WorkBuddy 客户端预检；
- 真实安装验收后如需调整最低版本，修改 `connector-meta.json` 并重新打包。

## 升级

- 更新 plugin 配置或 skill 后，bump `pack_config.json` 的 `version` 字段；
- 重新打包：`python3 scripts/pack.py --plugin <plugin-name>`；
- 重新提交 WorkBuddy 审核；
- 用户"看到新版"的最小操作步骤按 WorkBuddy 客户端行为记录。
