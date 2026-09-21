> 迁移自源技能 §文档上传工作流（强制决策规则 / 上传步骤 / fileIds 携带规则），业务规则以本文为准

# 文档上传与 fileIds

## 强制决策规则（先判断再动手）

当用户对话中**提供了原始文档文件**（PDF/Word/PPT/Excel/图片等附件），**必须**走文档上传路径：

- ✅ **正确做法**：调用 `file.upload_document` 上传整份文档 → 拿到 fileId → 在 `ai_customer.update` 中通过 `metadata.fileIds` 把文档附到对话
- ❌ **禁止做法**：把文档内容提取/摘录/改写为纯文字后只通过 `message` 字段传入

**判断逻辑（按顺序命中即停）**：

1. **用户已提供原始文档文件** → 强制走文档上传（无论文档长短）
2. 无原始文档，但参考资料 >1000 字，或含表格/图表/结构化数据 → 建议文档上传（询问用户是否提供文件）
3. 仅简短场景描述/角色设定/小知识点（<1000 字）→ 直接用对话文本

**为什么**：文档内含表格、图表、版式等结构化信息，提取为纯文字会丢失价值；AI 设计师需要整份文档才能正确绑定和读取。

## 上传前格式预处理（避免 parseStatus=3）

服务端对大体积或结构复杂的 DOCX 解析偶有失败（`parseStatus=3`），且无法从外部修复。**最稳妥的做法是：上传前先转成 Markdown（.md）**，MD 是纯文本，服务端解析稳定，且能保留标题/表格/列表等结构。

**触发条件**（命中任一即先转换再上传）：
- 文件格式为 DOCX / PPTX / XLSX 且 base64 体积 > 50KB
- 文件曾上传过但 `parseStatus=3` 失败（重传原始格式前必须先转 MD）

**转换方式（按可用性顺序选择）**：
1. **pandoc**（推荐，保留表格/格式最好）：`pandoc input.docx -t markdown -o output.md`
2. **python-docx**（纯 Python，DOCX 专用）：提取段落和表格，手动拼成 MD（标题用 `#`，表格用 `|---|`）
3. **agent 直接转换**：若文件不大（< 200KB）且用户能提供内容，agent 可读取后直接输出 MD 文件

转换后的 `.md` 文件按正常流程上传（`file.upload_document`，`fileName` 改为 `*.md`）。

> **MD 也有体积软上限（建议 <600KB）**：超大 MD 同样会触发 parseStatus=3。当整份文档转换后仍过大时，**按用户要练习的场景精选相关章节**再转 MD 上传（分卷精选），而非上传全文——这既符合解析限制，又契合"用户只要一类典型场景"的建课语义。

## 上传步骤

当课程需要基于大篇幅参考资料（如产品手册、操作规范、FAQ 库）时，使用文档上传而非对话文本。

**大文件上传指引**（base64 > 20K 字符时）：
- ❌ 禁止把 base64 内联进对话/工具入参（手抄不可行）
- ❌ 禁止把 base64 作为命令行位置参数（Windows argv 上限约 32K，必超限）
- ✅ 把参数写入临时 JSON 文件，通过宿主 MCP 工具直接调用：
  ```python
  import base64, json
  from pathlib import Path
  
  b64 = base64.b64encode(open("manual.pdf","rb").read()).decode()
  args_json = json.dumps({"fileContent": b64, "fileName": "manual.pdf"})
  
  # 通过宿主 MCP 工具直接调用 training.file.upload_document
  # 参数为上面的 args_json
  ```

1. **上传文档**：调用 `training.file.upload_document` → 获取 fileId（knowledge_type=0 时服务端自动触发解析）
2. **轮询解析状态**：`training.file.status({"fileId": 456})`，终止条件：
   - `parseStatus=2` 完成 → 进入第 3 步
   - `parseStatus=3` 失败 → **立即停止**，**将文件转为 Markdown 后重新上传**（见「上传前格式预处理」），**从后续 update 的 fileIds 中移除原失败文件**（勿反复重试原始格式）
   - `parseStatus=1/0` 解析中 → 间隔数秒重查；**持续超 20 分钟 → 停止轮询，直接进入第 3 步**（服务端守卫会自动恢复解析）
   - 错误码 40404/40000/40801 → 立即停止
3. **建课对话**：调用 `ai_customer.update`，携带 fileIds：
   ```json
   {
     "courseId": 123,
     "message": "基于上传的产品手册生成课程",
     "metadata": {"fileIds": [456]}
   }
   ```
   服务端校验并把 fileIds 翻译为 agent 契约，AI 设计师自主绑定并读取文档

## fileIds 携带规则（RFC-0005 契约）

- 必须为**正整数数组**，**≤20 个**，不可重复；非法元素返回 40001
- 无课程编辑权限返回 43502
- **fileIds 原样传递**：可重复携带同一 fileIds——服务端侧有指纹去重保证幂等，且重复携带是解析卡顿时触发服务端自动恢复的必要路径

## 注意

新工具 `ai_customer.update` 完整支持 `metadata.fileIds` 透传，文档建课统一用 `ai_customer.update`。
