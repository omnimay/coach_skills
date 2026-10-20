# 错误码全表

业务错误以 in-band 协议透传：HTTP 200 + `results.errorCode` / `results.errorMessage`。

| errorCode | 含义 | agent 应对 |
|---|---|---|
| 40001 | 参数无效 | 检查 message/courseId/fileIds 格式 |
| 42901 | 积分配额耗尽 | 告知用户充值或联系管理员 |
| 42902 | 频率超限（10次/分钟）或在飞任务>3 | 稍后重试 |
| 43501 | 课程不存在或已删除 | 确认 courseId，必要时重新 create |
| 43502 | 无课程编辑权限 | useTo=0 仅管理员；useTo=4 仅创建者 |
| 43503 | 同课程正在生成中 | 等当前任务 done 后再提交 |
| 43504 | taskId 无效/不属于你/已过期(>2h) | 改用 get 查课程现状 |
| 43505 | fileIds 非法或文件不存在 | 校验 fileIds 来源与格式 |
| 50002 | agent 调用失败 | 见 SKILL.md「50002 详细处理流程」（写库与状态翻转存在竞态，需先验证再重试） |
| 50003 | 会话创建失败 | 等 60s 重试（冷却期） |
| 50000 | 内部错误 | 联系管理员 |
| 40101 | 登录失效（middleware 层） | 网关返回 authentication_expired，重新 OAuth |
