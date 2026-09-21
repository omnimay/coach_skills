# ai_customer_design 关键业务场景记录（E01–E11 对照用）

> 来源：迁移时从源技能工作流提炼（2026-09-21，新异步工具组 RFC-0014）。供 E01–E11 双端验收执行时对照；调用序列为工具名层面，参数 schema 以宿主实际 tools/list 为准。

## S1 建课含双完成判定（对应 E01/E05）

- **前置条件**：MCP 服务器已连接并完成授权；用户给出课程需求（场景/角色/评估维度）
- **调用序列**：`ai_customer.create` → `ai_customer.update`（课程简报，秒返 taskId）→ `ai_customer.update_status`（每 5s 轮询至 done）→ `ai_customer.get`（核实 `status=create_status_created` 且 `stages` 非空）→ `task.create_open_project`
- **预期业务结果**：
  - 完成判定**只**依据 `ai_customer.get` 返回 `status=create_status_created` 且 `stages` 非空
  - 即使 `update_status` done 或 AI 回复"建课完成"，config 未满足判定条件时继续轮询 `get`（等 30s 再查，最长 10 分钟，全程静默）
  - 交付练习链接 + 二维码

## S2 改课含基线核实（对应 E05）

- **前置条件**：课程已建成（config 恒为 created）；用户提出修改诉求（如调整角色/阶段/评分维度）
- **调用序列**：`ai_customer.get`（记基线）→ `ai_customer.update`（修改诉求，秒返 taskId）→ `ai_customer.update_status`（轮询至 done）→ `ai_customer.get`（核实字段实际变化）→ 必要时重试（更明确的诉求，最多 3 次）→ `task.create_open_project`（新链接）
- **预期业务结果**：
  - 有基线与最终配置的差异证据；字段值确实变化才算修改生效
  - AI 回复"配置已满足要求"但字段值与基线相同时，判定为未生效
  - 建课后 60s 内的改课 update 遇 50003 属冷却期：等 60s 重试，最多 3 次

## S3 文档上传含 fileIds（对应 E04）

- **前置条件**：用户提供了原始文档文件（PDF/Word 等）；课程待建或待改
- **调用序列**：`file.upload_document`（整份原始文档，base64）→ `file.status`（轮询解析：parseStatus=2 完成 / =3 失败 / 错误码 40404/40000/40801 即停）→ `ai_customer.update`（message + `metadata.fileIds`）
- **预期业务结果**：
  - 上传的是**原始文档**，fileIds 以正整数数组原样传递（≤20 个）；不以内容摘录/纯文字替代上传
  - 解析失败（parseStatus=3）时向用户报错并从后续 update 的 fileIds 中移除该文件，不反复重试
  - 解析超 20 分钟仍未完成：停止轮询直接建课对话（服务端守卫自动恢复）

## S4 任务过期重提交（对应 E03）

- **前置条件**：`update_status` 轮询中
- **调用序列**：`ai_customer.update_status` → 返回 43504（任务不存在/已过期）→ 重新调用 `ai_customer.update` 提交新任务 → 继续轮询
- **预期业务结果**：
  - 识别 43504 为任务过期，不继续轮询无效 taskId
  - 重新 submit 后获取新 taskId
  - 轮询期间全程静默，不询问用户

## S5 冷却期处理（对应 E03）

- **前置条件**：建课后立即改课，`ai_customer.update` 返回 50003
- **调用序列**：观察错误码 → 50003（会话创建失败）→ 等 60s → 重试 update（最多 3 次）
- **预期业务结果**：
  - 识别 50003 为冷却期错误
  - 等待 60s 后重试，不立即重试
  - 最多重试 3 次，仍失败则向用户报告

## S6 QR 降级仅链接交付（对应 E07 降级场景）

- **前置条件**：课程已建成，`task.create_open_project` 已返回链接；宿主无 Python 运行时（或 render_qr.py 依赖缺失 / 输出不可写）
- **调用序列**：`task.create_open_project` → 尝试执行 `python3 <skill-root>/scripts/render_qr.py '<链接>'` → 失败（非零退出，E-HOST-/E-USER- 错误码）
- **预期业务结果**：
  - 原始练习链接**必达**（纯文本可复制形式展示）——链接本身是有效交付
  - 向用户明确说明二维码增强项缺失及原因；不伪造二维码、不由大模型直接生成二维码
  - 不因 QR 失败记为业务失败，也不记为完整验收通过（标记为增强缺失）

## S7 QR 正常双交付（对应 E07 正常场景）

- **前置条件**：宿主有 Python 运行时，`<skill-root>/vendor/segno` 完整
- **调用序列**：`task.create_open_project` → `python3 <skill-root>/scripts/render_qr.py '<链接>' --out '<可写目录>/practice.png'` → 展示 PNG
- **预期业务结果**：
  - 二维码内容与原链接一致（可解码验证）
  - 同一条回复中同时包含可复制链接文本与二维码图片，缺一不可

## S8 课程查询与无关请求不触发（对应 E03）

- **前置条件**：技能已加载；会话中可能出现两类请求：培训课程查询、与培训无关的任务
- **调用序列**：查询类 → `course.list` / `task.get_detail_list` / `organization.info_get` → 汇总答复
- **预期业务结果**：
  - 查询返回正确数据
  - 与培训课程无关的请求不启动任何培训流程（不建课、不调 update）
