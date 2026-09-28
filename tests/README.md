# 测试文件说明

## 已禁用的测试

- `test_mcp_diagnose.py.disabled` - 该测试文件会导致 pytest 崩溃（pytest capture 模块 I/O 错误）。
  测试本身可以正常运行（`python3 tests/test_mcp_diagnose.py`），但 pytest 无法正确收集。
  禁用原因：pytest 9.1.1 在处理该文件的导入时出现 capture 模块bug。

## 运行测试

```bash
# 运行所有启用的测试（70 个）
python3 -m pytest tests/ -v

# 手动运行被禁用的测试
python3 tests/test_mcp_diagnose.py.disabled
```
