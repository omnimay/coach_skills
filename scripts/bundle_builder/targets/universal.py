"""Universal target implementation."""

import json
import sys
from pathlib import Path
from typing import Any, NoReturn

from bundle_builder.workbuddy import generate_mcp_json


def fail(message: str) -> NoReturn:
    """统一错误输出并退出。"""
    sys.exit(f"ERROR: {message}")


class UniversalTarget:
    """Universal target - generates packages for direct download and manual installation."""

    def __init__(self, bundle_dir: Path):
        self.bundle_dir = bundle_dir

    def validate(self, bundle: dict[str, Any]) -> None:
        """Validate bundle for universal target."""
        # Universal target has minimal validation requirements
        # Just ensure basic structure is present
        if "mcp" not in bundle:
            fail("Universal target requires 'mcp' configuration")
        if "servers" not in bundle.get("mcp", {}):
            fail("Universal target requires 'mcp.servers' configuration")

    def build_entries(
        self,
        bundle: dict[str, Any],
        env_vars: dict[str, str],
    ) -> dict[Path, bytes]:
        """Build universal-specific entries.

        Only generates universal-specific files:
        - README.md

        Common files (mcp.json, skills) are handled by build.py.

        Args:
            bundle: Bundle configuration dict
            env_vars: Environment variables for placeholder resolution

        Returns:
            Dict mapping archive path to file contents
        """
        entries: dict[Path, bytes] = {}

        # Generate README.md
        readme_content = self._generate_readme(bundle)
        entries[Path("README.md")] = readme_content.encode("utf-8")

        return entries

    def _generate_readme(self, bundle: dict[str, Any]) -> str:
        """Generate README.md from template."""
        # Load template
        template_path = Path(__file__).parent.parent.parent.parent / "templates" / "universal-readme.md"
        template = template_path.read_text(encoding="utf-8")

        # Prepare template variables
        bundle_name = bundle["presentation"]["locales"][bundle["presentation"]["defaultLocale"]]["name"]
        bundle_description = bundle["presentation"]["locales"][bundle["presentation"]["defaultLocale"]]["description"]

        # Generate skills list (bullet points)
        skills_list_lines = []
        skills_details_lines = []
        for skill_name in sorted(bundle.get("skills", [])):
            skill_path = self.bundle_dir.parent.parent / "skills" / skill_name / "SKILL.md"
            if skill_path.exists():
                # Try to extract description from SKILL.md frontmatter
                content = skill_path.read_text(encoding="utf-8")
                # Simple extraction - look for description in frontmatter
                description = self._extract_skill_description(content)
                skills_list_lines.append(f"- **{skill_name}**: {description}")
                skills_details_lines.append(f"### {skill_name}\n\n{description}")
            else:
                skills_list_lines.append(f"- {skill_name}")
                skills_details_lines.append(f"### {skill_name}\n\n技能描述暂缺")

        skills_list = "\n".join(skills_list_lines)
        skills_details = "\n\n".join(skills_details_lines)

        # Generate mcp.json example
        mcp_config = generate_mcp_json(bundle)
        mcp_json_example = json.dumps({"mcpServers": mcp_config["mcpServers"]}, indent=2, ensure_ascii=False)

        # Fill template
        readme = template.format(
            bundle_name=bundle_name,
            bundle_description=bundle_description,
            skills_list=skills_list,
            skills_details=skills_details,
            mcp_json_example=mcp_json_example,
        )

        return readme

    def _extract_skill_description(self, skill_content: str) -> str:
        """Extract description from SKILL.md frontmatter."""
        # Simple parsing - look for "description:" line in frontmatter
        lines = skill_content.split("\n")
        in_frontmatter = False
        for line in lines:
            if line.strip() == "---":
                if in_frontmatter:
                    break
                in_frontmatter = True
                continue
            if in_frontmatter and line.startswith("description:"):
                return line.split(":", 1)[1].strip()
        return "技能描述暂缺"
