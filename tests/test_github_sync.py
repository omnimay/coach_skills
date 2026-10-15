"""用真实 Git 和虚拟 PAT 验证 Runner 禁用交互时的 CI 认证，无网络请求。"""

import os
from pathlib import Path
import shlex
import subprocess

import pytest
import yaml


CI_CONFIG = Path(__file__).resolve().parents[1] / ".gitlab-ci.yml"
FAKE_PAT = "fixture-not-a-real-pat"


@pytest.fixture(params=[False, True], ids=["no-helper", "inherited-helper"])
def runner_repo(tmp_path, request):
    # 隔离开发者的 Git 配置和凭证，只使用测试 PAT。
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "CI_PROJECT_DIR": str(tmp_path),
        "GITHUB_SYNC_TOKEN": FAKE_PAT,
    }
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], env=env, check=True)
    subprocess.run(
        ["git", "config", "credential.interactive", "never"],
        cwd=tmp_path, env=env, check=True,
    )
    if request.param:
        # 继承的 helper 不应替换 GitHub PAT，也不应收到保存凭证的请求。
        helper = '!f() { printf "username=runner-user\\npassword=runner-credential\\n"; }; f'
        subprocess.run(
            ["git", "config", "credential.helper", helper],
            cwd=tmp_path, env=env, check=True,
        )
    return tmp_path, env


@pytest.mark.parametrize("operation", ["fetch", "push"])
def test_ci_delivers_pat_despite_runner_disabling_interactive_auth(runner_repo, operation):
    repo, env = runner_repo
    job = yaml.safe_load(CI_CONFIG.read_text())["sync-github"]
    # 使用 CI 中真正生效的 Git 选项，通过 credential fill 验证认证；不访问远端。
    args = next(
        shlex.split(command) for command in job["script"]
        if operation in shlex.split(command)
    )
    probe = shlex.join(args[:args.index(operation)] + ["credential", "fill"])
    result = subprocess.run(
        ["sh", "-eu", "-c", "\n".join(job["before_script"] + [probe])],
        input="protocol=https\nhost=github.com\n\n",
        cwd=repo, env=env, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "username=x-access-token\n" in result.stdout
    assert f"password={FAKE_PAT}\n" in result.stdout
    # PAT 不写入配置和 askpass 文件，覆盖设置仅作用于当前 Git 命令。
    assert FAKE_PAT not in (repo / ".git/config").read_text()
    assert FAKE_PAT not in (repo / ".github-askpass.sh").read_text()
    config = subprocess.check_output(
        ["git", "config", "credential.interactive"], cwd=repo, env=env, text=True,
    )
    assert config.strip() == "never"
