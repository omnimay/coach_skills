---
name: recommend-courses
description: 处理任意分析报告并下发培训任务：从录音分析、复盘总结、能力评估等报告中提取学员短板、按标签匹配课程、无匹配时委托建课并打标、向指定学员批量下发任务。触发关键词：分析报告、总结报告、复盘、录音分析、能力评估、短板、培训任务下发、批量下发任务、培训闭环。
metadata:
  description_zh: 任意分析报告→短板提取→课程匹配→无匹配建课打标→任务下发闭环。
  description_en: Close the loop from any analysis report to training task dispatch.
---

# 课程推荐技能（recommend-courses）

编排技能：读取任意分析报告（录音分析、复盘总结、能力评估等——含学员姓名、工号、短板结论）→ 按标签匹配已有课程 → 命中即准备下发；未命中 → 委托建课技能（对练课 `ai-customer-design` / 闪卡课 `flashcard-design`）建课并打标回写 → 经用户确认后向名单学员**批量下发成员任务**（飞书通知默认发出）。

**适用性判定**：报告须同时含「人」（姓名或工号）与「短板」（不足/待改进/弱项类结论）；缺任一 → 不强行提取，如实告知不适用（录音分析报告是典型场景，但不是唯一入口）。

## 分工边界（与其他技能不重复）

| 职责 | 归属 |
|---|---|
| 报告结构化提取、标签匹配、打标回写、找人、成员任务下发契约、确认门 | **本技能** |
| 建课 / 改课工作流、课程简报、文档上传、完成判定、链接二维码交付 | 委托 **ai-customer-design** 技能 |
| 闪卡课（考官V2）建课 / 改题工作流、出题素材上传、完成判定、学习链接交付 | 委托 **flashcard-design** 技能 |
| MCP 连接恢复 | 委托 **coach-mcp-connect** 技能 |

## 前提

- 宿主 MCP 客户端已连接 enterprise-training 服务；工具经宿主原生 MCP 工具调用（`training.*`、`organization.*`）
- MCP 工具不可用时调用 `coach-mcp-connect` 技能恢复连接
- 业务数据在工具返回的 structuredContent 顶层，无 `.data` 信封
- **参数名以宿主 tools/list 实际 schema 为准**——本技能工具存在 snake/camel 混用（如 `label_batch_create` 用 `course_id`、`label_list` 用 `courseId`），不要凭风格推断

## 总编排（七步）

```text
Step 1 读报告 → 结构化提取学员清单
  students[{name, employee_no, weaknesses[]}]；0 学员或无短板 → 终止并告知（不猜不建）；
  同工号合并为一人（短板取并集）

Step 2 标签对齐
  training.course.label_list 拉本组织标签词表 → 短板结论映射到标签；
  映射不上的短板暂记（建课打标时补建）

Step 3 课程匹配
  training.course.list 传命中的标签 ids（AND 语义：课程须同时具备全部标签）
  → 命中 1 门 → Step 5
  → 命中多门 → 列候选（标签数最贴近学员标签集的排前；每门标注课程类型，见规则 5）让用户挑 → Step 5
  → 未命中 → Step 4

Step 4 建课 + 打标回写（未命中才走）
  4a 按课程类型委托建课：知识掌握/背诵/出题类短板 → flashcard-design 技能；
      其余（默认）对练课 → ai-customer-design 技能（短板结论作为评估维度输入）；
      用户未明确课程类型 → 先问再建。完成判定各以其技能权威端点为准
      （对练课 ai_customer.get；闪卡课 flashcard.update_status done），未就绪不进下发段
  4a-后 新课类型 = 本步实际委托的技能类型（对练课 / 闪卡课），Step 5 汇报时必须带上
  4b training.course.label_batch_create 给新课打标：命中标签 + Step 2 映射不上的新标签
      （id=0 自动新建，落库标记 AI 生成）；⚠️ 整体替换语义，必须传全集

Step 5 确认门（先问再发）
  向用户汇报：学员清单、短板、匹配/新建的课程（**每门课程必须标注类型：AI 客户对练课 / AI 闪卡课**）
  → 明确询问是否下发培训任务
  （可发、可不发）→ 未得到明确答复禁止创建任何任务

Step 6 找人（名单 → user_id）
  有 user_id 直接用；有工号 → organization.user.batch_resolve；
  仅姓名 → training.organization.tree 按姓名找（重名列候选让用户选）

Step 7 下发
  training.task.create_open_project 传 courseId + userIds（+可选 endTime/noticeConfig）
  → 通知结果以响应 noticeDispatched/noticeReason 为准，向用户复述
```

## 工具清单（本技能自有）

| 工具 | 用途 | 关键参数 |
|---|---|---|
| `training.course.label_list` | 标签词表（可带某课已关联标签） | `{"keyword":"异议"}`；`courseId` 可选 |
| `training.course.list` | 按标签筛课（AND 语义） | `{"labelIds":[1,2]}`（camel，以 tools/list 为准） |
| `training.course.label_batch_create` | 批量建标并关联课程（**写操作，整体替换**） | `{"course_id":123,"labels":[{"id":0,"name":"异议处理"}]}`（snake `course_id`） |
| `organization.user.batch_resolve` | 批量工号→user_id | `{"employeeNos":["E1001","E1002"]}`（≤50） |
| `training.organization.tree` | 部门成员树（按姓名找人） | `{"treeId":0,"size":9999}` |
| `training.task.create_open_project` | 下发成员任务 / 开放链接 | `{"courseId":123,"userIds":[5,8]}`；完整契约见 references |

响应判读要点：

- `label_list` → `labels:[{id, name, isAIGenerated}]`；传 `courseId` 时另有 `courseLabels`
- `label_batch_create` → `createdLabels`（本次新建的标签）+ `success:true`
- `batch_resolve` → `results:[{employeeNo, isSuccess, userId, failedReason}]`——未命中项只报 failedReason，**不模糊猜测**
- `create_open_project` → 通知结果看 `noticeDispatched`/`noticeReason`，不要自行推断

## 关键业务规则（不可精简）

1. **先问再发**：分析归分析、下发归下发。必须先汇报分析结果并明确询问用户是否下发（可发、可不发），未得到明确答复前禁止创建任何任务——分析无副作用，创建任务有。
2. **匹配语义**：course.list 按 `labelIds` 是 AND 语义（课程须同时具备全部传入标签）；命中多门让用户挑，未命中才建课，不跳步。
3. **建课委托**：按课程类型委托——对练课走 ai-customer-design 技能（完成判定唯一权威是 `ai_customer.get` 返回 `create_status_created` 且 `stages` 非空），闪卡课走 flashcard-design 技能（完成判定唯一权威是 `flashcard.update_status` 返回 done）；均不信 AI 回复文字。新课未就绪不得进入下发段。
4. **打标回写是闭环的必要步骤**：新建的课程必须 `label_batch_create` 打标，否则下次同类短板永远匹配不到、会重复建课。⚠️ 该工具是**整体替换**该课程标签关联——每次必须传"应保留的旧标签 + 新标签"全集，只传新增会清掉原有标签。
5. **课程类型必须标注**：凡向用户展示课程（候选列表 / Step 5 汇报 / 下发结果），每门课程都要说明它是哪种类型——「AI 客户对练课」或「AI 闪卡课」（其他类型照实说）。类型判定：新建课按 Step 4a 实际委托的技能；匹配课按 `training.course.list` 返回的 `type` 字段映射：`4/5/6/7` → AI 客户对练课，`12` → AI 闪卡课，其余值按类型号照实标注。
6. **通知语义以响应为准**：不传 `noticeConfig` 默认发 1 条飞书任务开始通知；传 `[]` 明示不发；传配置数组按配置发。向用户复述通知结果以 `noticeDispatched`/`noticeReason` 为准。
7. **40301 不重试**：无任务发布权限，或 userIds 含非本组织/已离职用户——改参数重试无效，向用户报告让用户处理权限或名单。
8. **找人不反问已有信息**：用户给了工号就不要再问 user_id；给姓名先查组织树；重名列候选让用户选，组织架构确实找不到再要工号，禁止虚构 user_id。
9. **边界策略**：报告缺「人」或缺「短板」→ 不适用，如实告知；提取 0 学员 → 终止并告知；`batch_resolve` 全部未命中 → 终止不下发；部分未命中 → 只下发命中学员、未命中进人工清单；同工号重复学员 → 合并（短板取并集）。

## 详细流程

- [下发工作流详解](references/dispatch-workflows.md)：适用性判定、提取规范、标签映射规则、匹配与 HITL 细则、建课委托说明、打标回写全集规则、下发契约（参数/通知三态/错误码）、找人路径、确认门话术、边界策略
