"""GitLab Generic Package Registry + Release API 封装（RFC-0006 §5）。

依赖 Python 标准库（urllib / json）+ PyYAML（glab 配置解析）。不引入 requests。
所有方法均为低层 API 封装，不含发布业务逻辑。
"""
import hashlib
import json
import subprocess
import sys
import urllib.error

import yaml
import urllib.request
from pathlib import Path
from typing import Any, NoReturn


def fail(message: str) -> NoReturn:
    sys.exit(f"ERROR: {message}")


class GitLabClient:
    """GitLab 实例的 API 客户端。

    必要环境变量：
        GITLAB_API_URL:   GitLab 实例地址（如 https://gitlab.example.com）
        GITLAB_PROJECT_ID: 项目 ID（数字）
        GITLAB_TOKEN:     具有 api 权限的 PAT 或 CI_JOB_TOKEN

    Registry 路径约定（RFC-0006 §5 步骤④）：
        generic/coachskills-<bundle-id>-<target>/<version>/<zip-name>
    """

    def __init__(self, api_url: str, project_id: str, token: str,
                 token_type: str = "private") -> None:
        self.api_url = api_url.rstrip("/")
        self.project_id = project_id
        self.token = token
        # token_type: "private" → PRIVATE-TOKEN header (PAT)
        #             "job"     → JOB-TOKEN header (CI_JOB_TOKEN)
        self.token_type = token_type

    @property
    def _auth_header(self) -> str:
        """返回认证 header 名称。"""
        return "JOB-TOKEN" if self.token_type == "job" else "PRIVATE-TOKEN"

    @classmethod
    def from_env(cls) -> "GitLabClient":
        """从环境变量或 glab CLI 配置构造；缺失时 sys.exit。

        优先级：
        1. 环境变量（GITLAB_API_URL / GITLAB_PROJECT_ID / GITLAB_TOKEN）→ PRIVATE-TOKEN
        2. GitLab CI 内置变量（CI_API_V4_URL / CI_PROJECT_ID / CI_JOB_TOKEN）→ JOB-TOKEN
        3. glab CLI 配置文件（~/.config/glab-cli/config.yml）+ git remote 自动检测 → PRIVATE-TOKEN
        """
        import os

        # 先尝试自定义环境变量（PAT）
        api_url = os.environ.get("GITLAB_API_URL", "")
        project_id = os.environ.get("GITLAB_PROJECT_ID", "")
        token = os.environ.get("GITLAB_TOKEN", "")
        token_type = "private" if token else ""

        # 回退到 GitLab CI 内置变量（JOB-TOKEN）
        if not api_url:
            api_url = os.environ.get("CI_API_V4_URL", "")
        if not project_id:
            project_id = os.environ.get("CI_PROJECT_ID", "")
        if not token:
            token = os.environ.get("CI_JOB_TOKEN", "")
            if token:
                token_type = "job"

        # 如果仍不完整，尝试从 glab 配置读取（PAT）
        if not all([api_url, project_id, token]):
            glab_config = cls._try_load_glab_config()
            if glab_config:
                if not api_url:
                    api_url = glab_config.get("api_url", "")
                if not token:
                    token = glab_config.get("token", "")
                    token_type = "private"
                if not project_id:
                    # 从 git remote 自动检测 project ID
                    project_id = cls._detect_project_id_from_git(api_url, token)

        missing = [k for k, v in [("GITLAB_API_URL", api_url),
                                   ("GITLAB_PROJECT_ID", project_id),
                                   ("GITLAB_TOKEN", token)] if not v]
        if missing:
            fail(f"缺少配置：{', '.join(missing)}\n"
                 f"请设置环境变量或确保 glab CLI 已认证（glab auth status）")
        return cls(api_url, project_id, token, token_type)

    @classmethod
    def _try_load_glab_config(cls) -> dict[str, str] | None:
        """尝试从 glab CLI 配置文件读取认证信息。

        使用 PyYAML 解析（项目已有依赖），自动处理引号、缩进、注释等边界。
        """
        config_path = Path.home() / ".config" / "glab-cli" / "config.yml"
        if not config_path.exists():
            return None

        try:
            # 先从 git remote 获取 host
            try:
                remote_url = subprocess.check_output(
                    ["git", "remote", "get-url", "origin"],
                    text=True, stderr=subprocess.DEVNULL,
                    timeout=30,
                ).strip()
                # 从 remote URL 提取 host（如 git.mgvai.cn）
                if "://" in remote_url:
                    host = remote_url.split("://")[1].split("/")[0]
                else:
                    # SSH 格式：git@git.mgvai.cn:coach/coachskills.git
                    host = remote_url.split("@")[1].split(":")[0]
            except subprocess.CalledProcessError:
                return None

            with open(config_path) as f:
                config = yaml.safe_load(f)

            if not isinstance(config, dict):
                return None
            token = (config.get("hosts") or {}).get(host, {}).get("token")
            if isinstance(token, str) and token:
                return {
                    "api_url": f"https://{host}/api/v4",
                    "token": token,
                }
        except (OSError, ValueError, subprocess.SubprocessError, yaml.YAMLError):
            # 配置文件不可读 / 格式错误 / git 命令失败 / YAML 解析错误 → 回退到环境变量
            pass

        return None

    @classmethod
    def _detect_project_id_from_git(cls, api_url: str, token: str) -> str:
        """从 git remote 自动检测 GitLab project ID。"""
        try:
            # 获取 remote URL
            remote_url = subprocess.check_output(
                ["git", "remote", "get-url", "origin"],
                text=True, stderr=subprocess.DEVNULL
            ).strip()

            # 解析 project path（如 coach/coachskills）
            if "://" in remote_url:
                # HTTPS: https://git.mgvai.cn/coach/coachskills.git
                path = remote_url.split("://")[1].split("/", 1)[1]
            else:
                # SSH: git@git.mgvai.cn:coach/coachskills.git
                path = remote_url.split(":", 1)[1]

            # 移除 .git 后缀
            if path.endswith(".git"):
                path = path[:-4]

            # URL encode path（/ -> %2F）
            encoded_path = path.replace("/", "%2F")

            # 调用 GitLab API 获取 project ID
            url = f"{api_url}/projects/{encoded_path}"
            req = urllib.request.Request(url)
            req.add_header("PRIVATE-TOKEN", token)

            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
                return str(data["id"])
        except (OSError, subprocess.SubprocessError, ValueError, KeyError):
            # git 不可用 / 网络错误 / JSON 解析失败 / 缺少 id 字段 → 回退
            return ""

    # ── Generic Package Registry ──────────────────────────────────────

    def registry_package_name(self, bundle_id: str, target: str) -> str:
        """Registry 中的包名：coachskills-<bundle-id>-<target>。"""
        return f"coachskills-{bundle_id}-{target}"

    def registry_upload_url(self, package_name: str, version: str, file_name: str) -> str:
        """构造上传 URL。"""
        return (
            f"{self.api_url}/projects/{self.project_id}/packages/generic/"
            f"{package_name}/{version}/{file_name}"
        )

    def registry_download_url(self, package_name: str, version: str, file_name: str) -> str:
        """构造下载 URL。"""
        return (
            f"{self.api_url}/projects/{self.project_id}/packages/generic/"
            f"{package_name}/{version}/{file_name}"
        )

    def upload_package(self, package_name: str, version: str, file_name: str,
                       data: bytes) -> str:
        """上传 ZIP 到 Generic Package Registry，返回 SHA-256。"""
        url = self.registry_upload_url(package_name, version, file_name)
        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header(self._auth_header, self.token)
        req.add_header("Content-Type", "application/zip")
        sha256 = hashlib.sha256(data).hexdigest()
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status not in (200, 201):
                    fail(f"Registry 上传失败：HTTP {resp.status}")
        except urllib.error.HTTPError as e:
            fail(f"Registry 上传失败：{e.code} {e.reason}")
        return sha256

    def download_package(self, package_name: str, version: str, file_name: str) -> bytes:
        """从 Registry 下载文件内容。"""
        url = self.registry_download_url(package_name, version, file_name)
        req = urllib.request.Request(url)
        req.add_header(self._auth_header, self.token)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            fail(f"Registry 下载失败：{e.code} {e.reason}")

    def registry_package_hash(self, package_name: str, version: str, file_name: str) -> str | None:
        """通过 Package Files API 查询已存在包的 SHA-256（元数据查询，不下载文件）。

        两步查找：① 按 package_name + version 查 package_id
                  ② 按 package_id 查 package_files → 匹配 file_name → 取 file_sha256
        不存在返回 None。
        """
        # ① 查 package_id
        from urllib.parse import quote
        url = (
            f"{self.api_url}/projects/{self.project_id}/packages"
            f"?package_name={quote(package_name)}"
            f"&package_type=generic"
            f"&package_version={quote(version)}"
        )
        req = urllib.request.Request(url)
        req.add_header(self._auth_header, self.token)
        try:
            with urllib.request.urlopen(req) as resp:
                packages = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            fail(f"Registry 查询失败：{e.code} {e.reason}")
        except urllib.error.URLError as e:
            fail(f"Registry 查询失败（网络错误）：{e.reason}")

        if not packages:
            return None
        package_id = packages[0]["id"]

        # ② 查 package_files → 按 file_name 匹配 → 取 file_sha256
        url = (
            f"{self.api_url}/projects/{self.project_id}"
            f"/packages/{package_id}/package_files"
        )
        req = urllib.request.Request(url)
        req.add_header(self._auth_header, self.token)
        try:
            with urllib.request.urlopen(req) as resp:
                files = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            fail(f"Registry 查询失败：{e.code} {e.reason}")
        except urllib.error.URLError as e:
            fail(f"Registry 查询失败（网络错误）：{e.reason}")

        for f in files:
            if f.get("file_name") == file_name:
                sha256 = f.get("file_sha256")
                if sha256 is None:
                    fail(f"Registry 文件存在但缺少 SHA-256 元数据：{file_name}")
                return sha256
        return None

    def delete_package_file(self, package_name: str, version: str, file_name: str) -> None:
        """删除 Registry 中的单个文件（用于回滚）。"""
        url = self.registry_download_url(package_name, version, file_name)
        req = urllib.request.Request(url, method="DELETE")
        req.add_header(self._auth_header, self.token)
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status not in (200, 204):
                    fail(f"Registry 删除失败：HTTP {resp.status}")
        except urllib.error.HTTPError as e:
            fail(f"Registry 删除失败：{e.code} {e.reason}")

    # ── Releases ──────────────────────────────────────────────────────

    def create_release(self, tag_name: str, name: str, description: str) -> dict[str, Any]:
        """创建 GitLab Release（如已存在则更新描述）。"""
        url = f"{self.api_url}/projects/{self.project_id}/releases"
        payload = json.dumps({
            "tag_name": tag_name,
            "name": name,
            "description": description,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header(self._auth_header, self.token)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read()
                return json.loads(body)
        except urllib.error.HTTPError as e:
            # 409 = 已存在 → 改为 PATCH 更新
            if e.code == 409:
                return self.update_release(tag_name, description)
            fail(f"Release 创建失败：{e.code} {e.reason}")

    def update_release(self, tag_name: str, description: str) -> dict[str, Any]:
        """更新已存在 Release 的描述。"""
        url = f"{self.api_url}/projects/{self.project_id}/releases/{tag_name}"
        payload = json.dumps({"description": description}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="PUT")
        req.add_header(self._auth_header, self.token)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            fail(f"Release 更新失败：{e.code} {e.reason}")

    # ── Repository files（读取 default branch 的 index.json）────────────

    def read_repo_file(self, file_path: str, ref: str = "main") -> str | None:
        """读取仓库文件内容。不存在返回 None。"""
        from urllib.parse import quote
        encoded = quote(file_path, safe="")
        url = (
            f"{self.api_url}/projects/{self.project_id}/repository/files/{encoded}"
            f"/raw?ref={ref}"
        )
        req = urllib.request.Request(url)
        req.add_header(self._auth_header, self.token)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            fail(f"仓库文件读取失败：{e.code} {e.reason}")


def sha256_of(data: bytes) -> str:
    """计算字节数据的 SHA-256 摘要。"""
    return hashlib.sha256(data).hexdigest()


def sha256_of_file(path: Path) -> str:
    """计算文件的 SHA-256 摘要。"""
    return sha256_of(path.read_bytes())
