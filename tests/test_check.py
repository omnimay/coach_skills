"""T05-b/T13/T14/T15/T16 + E_base01/02/04/05 静态检查（RFC §3.14/§3.6.1）。

失败/通过用例均通过 --only 选择器运行单项检查，互不牵连；
全量 check.py 的集成绿在 Task 11 Step 3（README 替换后）验证。"""
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
CHECK = [sys.executable, str(SCRIPTS / "check.py")]


def run_check(cwd, *only):
    cmd = CHECK + (["--only", *only] if only else [])
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def _mk_skill(tmp_path, body, frontmatter="name: t\ndescription: 测试"):
    skill = tmp_path / "skills/ai_customer_design"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n{body}")


def test_t05b_banned_host_terms_fail(tmp_path):
    _mk_skill(tmp_path, "在 Claude Code 中运行本技能。\n")
    r = run_check(tmp_path, "host-terms")
    assert r.returncode != 0 and "Claude Code" in r.stderr


def test_t05b_host_term_note_exempt(tmp_path):
    _mk_skill(tmp_path, "正常正文。\n\n"
        "<!-- host-term-note -->\n注意避免 Claude Code 专属字段。\n<!-- /host-term-note -->\n")
    r = run_check(tmp_path, "host-terms")
    assert r.returncode == 0, r.stderr


def test_t13_trigger_phrase_fails(tmp_path):
    _mk_skill(tmp_path, "正文\n", frontmatter='name: t\ndescription: "Use when 用户要建课"')
    r = run_check(tmp_path, "trigger-phrases")
    assert r.returncode != 0 and "Use when" in r.stderr


def test_t14_broken_reference_link_fails(tmp_path):
    _mk_skill(tmp_path, "见 [文档](references/nope.md)\n")
    r = run_check(tmp_path, "references")
    assert r.returncode != 0 and "nope.md" in r.stderr


def test_t14_out_of_bounds_link_fails(tmp_path):
    _mk_skill(tmp_path, "见 [越界](../../../etc/passwd)\n")
    r = run_check(tmp_path, "references")
    assert r.returncode != 0


def test_t05_symlink_in_skill_dir_fails(tmp_path):
    import os
    skill = tmp_path / "skills/ai_customer_design"
    (skill / "references").mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text("---\nname: t\ndescription: d\n---\n正文\n")
    os.symlink("/etc/hosts", skill / "evil_link")
    r = run_check(tmp_path, "references")
    assert r.returncode != 0 and "symlink" in r.stderr


def test_t15_private_mechanism_term_fails(tmp_path):
    _mk_skill(tmp_path, "依赖 _meta.progressToken 与 SessionStart。\n")
    r = run_check(tmp_path, "mechanism-terms")
    assert r.returncode != 0 and "_meta.progressToken" in r.stderr


def test_t16_gitlab_readme_template_fails(tmp_path):
    (tmp_path / "README.md").write_text("# t\n\n## Add your files\n")
    r = run_check(tmp_path, "readme")
    assert r.returncode != 0 and "Add your files" in r.stderr


def test_frontmatter_allowed_tools_written_fails(tmp_path):
    _mk_skill(tmp_path, "正文\n", frontmatter="name: t\ndescription: d\nallowed-tools: Bash")
    r = run_check(tmp_path, "frontmatter")
    assert r.returncode != 0 and "allowed-tools" in r.stderr


def test_frontmatter_whitelist_ok(tmp_path):
    _mk_skill(tmp_path, "QR 生成失败时直接展示原始练习链接。\n",
              frontmatter="name: t\ndescription: d\nlicense: Proprietary\nmetadata:\n  description_zh: 测")
    r = run_check(tmp_path, "frontmatter")
    assert r.returncode == 0, r.stderr


def test_e_base01_required_fields_missing_fails(tmp_path):
    _mk_skill(tmp_path, "正文\n", frontmatter="name: t")  # 缺 description
    r = run_check(tmp_path, "frontmatter")
    assert r.returncode != 0 and "description" in r.stderr


def test_e_base04_qr_fallback_guidance_required(tmp_path):
    _mk_skill(tmp_path, "正文没有降级指引。\n")
    r = run_check(tmp_path, "qr-fallback")
    assert r.returncode != 0 and "QR" in r.stderr


def test_e_base05_oauth_copy_neutral(tmp_path):
    _mk_skill(tmp_path, "认证失败请打开 Claude 设置重连。\n")
    r = run_check(tmp_path, "oauth-copy")
    assert r.returncode != 0
