# ai_customer_design 任务完成度 Eval

> 技能路径: `skills/ai_customer_design/`
> Eval 形状: task-completion(通用平台)
> 创建日期: 2026-09-17
> 最后更新: 2026-09-21

## Eval 用例(6 个)

### E1: 新异步工具建课流程
**任务**: 使用 `ai_customer.create` → `ai_customer.update` → `ai_customer.update_status` → `ai_customer.get` 完成建课
**判据**: 能正确走完异步建课全流程
**通过条件**:
- [ ] Step 1 调用 `ai_customer.create` 获取 courseId
- [ ] Step 2 调用 `ai_customer.update` 获取 taskId（秒返）
- [ ] Step 3 每 5s 轮询 `update_status` 直到 done/failed
- [ ] Step 4 调用 `ai_customer.get` 验证 `status=create_status_created` 且 `stages` 非空

### E2: 轮询纪律验证
**任务**: 验证 `update_status` 轮询行为符合规范
**判据**: 轮询间隔 5s，全程静默，最长 10 分钟
**通过条件**:
- [ ] 轮询间隔为 5 秒（非 30 秒）
- [ ] 轮询期间不询问用户"还在吗"
- [ ] 总时长不超 10 分钟
- [ ] `done` 后立即调 `get` 验证

### E3: 错误码处理（50003 冷却期）
**任务**: 建课后立即改课触发 50003 错误
**判据**: 能正确处理冷却期
**通过条件**:
- [ ] 识别 50003 为冷却期错误
- [ ] 等待 60s 后重试
- [ ] 最多重试 3 次
- [ ] 仍失败则向用户报告

### E4: 文档上传建课
**任务**: 上传文档并通过 `metadata.fileIds` 建课
**判据**: 能完成文档上传并正确携带 fileIds
**通过条件**:
- [ ] 调用 `file.upload_document` 上传文档获取 fileId
- [ ] 轮询 `file.status` 直到 parseStatus=2
- [ ] 调用 `ai_customer.update` 时携带 `metadata.fileIds`
- [ ] 大文件（>20K base64）走 stdin 传参

### E5: 双完成判定验证
**任务**: 验证 agent 不会混淆"任务完成"和"课程创建完成"
**判据**: 能正确区分 `update_status` done 和课程实际创建完成
**通过条件**:
- [ ] 不因 `update_status` done 就声称建课完成
- [ ] 必须调 `ai_customer.get` 验证 `status=create_status_created` 且 `stages` 非空
- [ ] 不信 AI 回复文字（"建课完成"等）

### E6: 并发建课限制
**任务**: 同时创建 >3 门课程
**判据**: 能正确处理并发上限
**通过条件**:
- [ ] 识别并发上限 ≤3
- [ ] 批量建课串行执行或最多 3 门并行
- [ ] 不盲目并行创建导致队列积压

---

## Eval 执行记录

| 日期 | 用例 | 通过 | 备注 |
|------|------|------|------|
| (待填写) | E1-E6 | - | 打包后 subagent 跑建课流程验证 |

---

> 📅 Eval-rot reminder: Refresh this eval set by 2026-10-21.
>   Monthly, append new REAL-WORLD queries from actual sessions (support tickets, misfire reports,
>   the words users said when it broke). Invented queries rot the set.
>   An eval set with zero new entries in the last month, or a last-updated date >60 days old,
>   is suspected-rot — flag it.

> Last updated: 2026-09-21
