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


def _mk_bundle_repo(tmp_path, bundle_json_extra=None, release_plan=None, envs=None):
    """创建最小 bundle 仓库结构（用于 release-plan/distribution 检查）。"""
    import json as json_mod
    # skills/
    skill = tmp_path / "skills" / "test-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: test\ndescription: test\n---\nbody")
    # bundles/test-bundle/
    bp = tmp_path / "bundles" / "test-bundle"
    bp.mkdir(parents=True)
    (bp / "icon.svg").write_text("<svg></svg>")
    bundle = {
        "schemaVersion": 1, "id": "test-bundle", "version": "1.0.0",
        "skills": ["test-skill"],
        "presentation": {"defaultLocale": "zh-CN",
                         "locales": {"zh-CN": {"name": "T", "description": "d", "examples": []}},
                         "icon": "icon.svg"},
        "mcp": {"servers": {"s": {"transport": "streamable-http", "url": "https://mcp.test/mcp"}}},
        "targets": {"workbuddy": {"source": "test-bundle", "type": "mcp", "minVersion": "4.24.0"}},
    }
    if bundle_json_extra:
        bundle_json_extra(bundle)
    (bp / "bundle.json").write_text(json_mod.dumps(bundle, ensure_ascii=False))
    if release_plan is not None:
        (bp / "release-plan.json").write_text(json_mod.dumps(release_plan, ensure_ascii=False))
    # environments.json（默认包含 test 和 coach 环境）
    if envs is None:
        envs = {"test": {}, "coach": {}}
    (tmp_path / "environments.json").write_text(json_mod.dumps(envs, ensure_ascii=False))


def test_release_plan_missing(tmp_path):
    """缺少 release-plan.json → FAIL"""
    _mk_bundle_repo(tmp_path)
    r = run_check(tmp_path, "release-plan")
    assert r.returncode != 0 and "release-plan.json 缺失" in r.stderr


def test_release_plan_version_mismatch(tmp_path):
    """release-plan 版本与 bundle.json 不匹配 → FAIL"""
    _mk_bundle_repo(tmp_path, release_plan={"version": "2.0.0", "targets": {"workbuddy": ["test"]}})
    r = run_check(tmp_path, "release-plan")
    assert r.returncode != 0 and "不一致" in r.stderr


def test_release_plan_valid(tmp_path):
    """合法 release-plan.json → PASS"""
    _mk_bundle_repo(tmp_path, release_plan={"version": "1.0.0", "targets": {"workbuddy": ["test", "coach"]}})
    r = run_check(tmp_path, "release-plan")
    assert r.returncode == 0, r.stderr


def test_release_plan_duplicate_variants(tmp_path):
    """变体重复 → FAIL"""
    _mk_bundle_repo(tmp_path, release_plan={"version": "1.0.0", "targets": {"workbuddy": ["test", "test"]}})
    r = run_check(tmp_path, "release-plan")
    assert r.returncode != 0 and "重复" in r.stderr


def test_release_plan_unregistered_variant(tmp_path):
    """变体未在 environments.json 中注册 → FAIL"""
    _mk_bundle_repo(
        tmp_path,
        release_plan={"version": "1.0.0", "targets": {"workbuddy": ["invalid_env"]}},
        envs={"test": {}, "coach": {}}
    )
    r = run_check(tmp_path, "release-plan")
    assert r.returncode != 0
    assert "invalid_env" in r.stderr
    assert "未在 environments.json 中注册" in r.stderr


def test_release_plan_empty_environments(tmp_path):
    """空 environments.json → 所有变体失败"""
    _mk_bundle_repo(
        tmp_path,
        release_plan={"version": "1.0.0", "targets": {"workbuddy": ["test"]}},
        envs={}
    )
    r = run_check(tmp_path, "release-plan")
    assert r.returncode != 0
    assert "test" in r.stderr
    assert "未在 environments.json 中注册" in r.stderr


def test_release_plan_unknown_target(tmp_path):
    """未知 target → FAIL"""
    _mk_bundle_repo(tmp_path, release_plan={"version": "1.0.0", "targets": {"unknown": ["x"]}})
    r = run_check(tmp_path, "release-plan")
    assert r.returncode != 0 and "未知 target" in r.stderr


def test_distribution_valid(tmp_path):
    """合法 distributionName → PASS"""
    _mk_bundle_repo(
        tmp_path,
        bundle_json_extra=lambda b: b["targets"]["workbuddy"].update({"distributionName": "ai-customer"}),
        release_plan={"version": "1.0.0", "targets": {"workbuddy": ["test"]}},
    )
    r = run_check(tmp_path, "distribution")
    assert r.returncode == 0, r.stderr


def test_distribution_invalid_chars(tmp_path):
    """distributionName 含非法字符 → FAIL"""
    _mk_bundle_repo(
        tmp_path,
        bundle_json_extra=lambda b: b["targets"]["workbuddy"].update({"distributionName": "../evil"}),
        release_plan={"version": "1.0.0", "targets": {"workbuddy": ["test"]}},
    )
    r = run_check(tmp_path, "distribution")
    assert r.returncode != 0 and "只能是字母" in r.stderr


def test_distribution_omitted_ok(tmp_path):
    """不声明 distributionName（默认等于 id） → PASS"""
    _mk_bundle_repo(tmp_path, release_plan={"version": "1.0.0", "targets": {"workbuddy": ["test"]}})
    r = run_check(tmp_path, "distribution")
    assert r.returncode == 0, r.stderr


def test_distribution_multi_target_no_collision(tmp_path):
    """同一 bundle 的 workbuddy 和 universal target 不碰撞（各自独立的 latest/ 目录）。"""
    _mk_bundle_repo(
        tmp_path,
        release_plan={"version": "1.0.0", "targets": {
            "workbuddy": ["test", "coach"],
            "universal": ["test", "coach"],
        }},
    )
    r = run_check(tmp_path, "distribution")
    assert r.returncode == 0, r.stderr


def test_distribution_multi_target_per_target_name(tmp_path):
    """不同 target 可声明不同的 distributionName。"""
    _mk_bundle_repo(
        tmp_path,
        bundle_json_extra=lambda b: {
            b["targets"].setdefault("universal", {}).update({"distributionName": "my-coach-universal"}),
        },
        release_plan={"version": "1.0.0", "targets": {
            "workbuddy": ["test"],
            "universal": ["test"],
        }},
    )
    r = run_check(tmp_path, "distribution")
    assert r.returncode == 0, r.stderr
