# Codex 安装指南

> **状态标注**：本文命令均为**目标用法，实测版本 pending P0 spike**（RFC §3.3：本机此前检查的 Codex CLI 为 0.153.4，仅确认了相关命令帮助，未证明公司 Git 源已可安装）。P0 附加项①（根插件 `source.path: "./"` 安装 spike，0.5 天）实测通过后，本文更新为实测版本并固定测试用客户端版本与 OS（E01 验收基线，见 [../deferred-acceptance.md](../deferred-acceptance.md)）。

## 适用对象

通过 Codex CLI 的插件市场（Git Marketplace）安装公司 `coachskills` 插件的员工。Git Marketplace 是首期正式 Codex 渠道；ZIP 仅供离线交付和后续入口使用（若 P0 spike 失败，本渠道降级为 ZIP 离线交付 + 手动安装指引，届时修订本文）。

## 前提条件

| 前提 | 说明 |
|---|---|
| SSH 私库访问 | 仓库地址 `git@git.mgvai.cn:coach/coachskills.git`（SSH 协议）。需将个人 SSH 公钥加入公司 GitLab，且拥有本仓库读权限。HTTPS 克隆方式未经实测，不承诺可用 |
| 网络可达 MCP 服务 | 客户端环境可访问 MCP 服务域名（当前为测试地址 `https://mcp.test.omnimay.com/coach/mcp`，生产 URL 待分配，见 RFC §8）及其 OAuth 端点；授权经系统浏览器完成 |
| Python 运行时（可选） | 仅二维码渲染增强需要：Python 3.8+，随包 `vendor/segno/` 已内置，无需 pip 安装。无 Python 运行时时按技能正文降级为直接展示原始练习链接（RFC §3.8，QR 为增强、链接必交付） |

> 以上环境前提摘自源技能 INSTALL.md 中仍适用的通用部分（M10 处置记录见 [../migration/ai_customer_design.md](../migration/ai_customer_design.md)）。源文档中的宿主专属步骤（解压技能包到个人技能目录、手动加载 SKILL.md、脚本 `auth` 登录）不适用于本插件，未收录。

## 首次安装

目标用法，实测版本 pending P0 spike：

```bash
# 首次安装：添加市场，固定一个已经验收并发布的版本 ref。（目标用法，实测 pending P0 spike）
codex plugin marketplace add git@git.mgvai.cn:coach/coachskills.git --ref v0.1.0

# 从市场安装插件。（目标用法，实测 pending P0 spike）
codex plugin add coachskills@coachskills-marketplace
```

## 首次 OAuth（宿主管理）

- 市场条目 policy 为 `authentication: "ON_INSTALL"`，即安装时触发授权。实际触发时序（安装时授权 vs 首次调用时授权、是否双重弹窗）以 P0 spike 实测记录为准；若与实际流程不符，改用平台支持的其他 policy 值（RFC §3.3）。
- 授权全程由 Codex 的 MCP 客户端经系统浏览器完成（PKCE + 动态客户端注册等细节由宿主自动处理）。凭证由宿主管理；插件不读取本地 tokens 文件，不调用任何脚本登录（RFC §3.4）。
- 授权失败时的处理：由宿主 MCP 设置重新连接（技能正文的中性指引，E_base05；详细排查见 [../../skills/ai_customer_design/references/troubleshooting.md](../../skills/ai_customer_design/references/troubleshooting.md)）。

## 验证 Skill 发现（E01 口径）

安装完成后在新会话中确认：

1. 技能以正确名称 `ai_customer_design` 出现；
2. 能读取 references（建课工作流、文档上传等指引被正确加载）；
3. MCP 配置随插件生效：`enterprise-training` 服务可连接，工具名称前缀以宿主实际 `tools/list` 为准。

E01 的 Codex 子项还需核实：`source.path: ./` 生效、私库访问、插件缓存位于源码之外、不递归再次注册同一个 Marketplace——均属 P4 验收，见 [../deferred-acceptance.md](../deferred-acceptance.md)。

## 更新

目标用法，实测版本 pending P0 spike：

```bash
# 查看市场；固定 tag 的市场不会自动追踪下个版本。（目标用法，实测 pending P0 spike）
codex plugin marketplace list

# 升级市场到新 ref。（目标用法，实测 pending P0 spike）
codex plugin marketplace upgrade coachskills-marketplace
```

- 追踪受保护 `stable` 分支的用户执行 refresh 后，仍须检查已安装版本及新会话行为（E11）。
- 固定 tag 用户的经验证切换 ref 方法待 P0 spike 后补充到本文（不凭猜测承诺重复 `marketplace add` 会覆盖旧配置，RFC §3.3）。
- 升级验收（E09）与"客户端看到新版"的最小操作步骤（E11）见 [../deferred-acceptance.md](../deferred-acceptance.md)。

## 故障排查

- 业务与连接类问题先查技能内指引：[../../skills/ai_customer_design/references/troubleshooting.md](../../skills/ai_customer_design/references/troubleshooting.md)。
- 向维护者反馈时附完整报错原文，便于按 RFC §3.13 错误码分类（E-USER- / E-HOST- / E-MCP-）定位。
- 发布渠道状态与产物核对（SHA256SUMS）见 [../releasing.md](../releasing.md)。
