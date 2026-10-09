"""WorkBuddy target implementation."""

import json
from pathlib import Path
from typing import Any

from bundle_builder.workbuddy import (
    generate_auth_profile,
    generate_connector_meta,
    validate_workbuddy,
)


class WorkbuddyTarget:
    """WorkBuddy target - generates packages for WorkBuddy platform."""

    def __init__(self, bundle_dir: Path):
        self.bundle_dir = bundle_dir

    def validate(self, bundle: dict[str, Any]) -> None:
        """Validate bundle for WorkBuddy target."""
        validate_workbuddy(bundle)

    def build_entries(
        self,
        bundle: dict[str, Any],
        env_vars: dict[str, str],
    ) -> dict[Path, bytes]:
        """Build WorkBuddy-specific entries.

        Only generates WorkBuddy-specific files:
        - connector-meta.json
        - auth-profile.json
        - icon.svg

        Common files (mcp.json, skills) are handled by build.py.

        Args:
            bundle: Bundle configuration dict
            env_vars: Environment variables for placeholder resolution

        Returns:
            Dict mapping archive path to file contents
        """
        entries: dict[Path, bytes] = {}

        # Generate connector-meta.json
        connector_meta = generate_connector_meta(bundle)
        entries[Path("connector-meta.json")] = (
            json.dumps(connector_meta, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
        )

        # Generate auth-profile.json
        auth_profile = generate_auth_profile(env_vars)
        entries[Path("auth-profile.json")] = (
            json.dumps(auth_profile, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
        )

        # Add icon (already validated by validate_bundle_icon in build.py)
        icon_filename = bundle.get("presentation", {}).get("icon", "icon.svg")
        entries[Path(icon_filename)] = (self.bundle_dir / icon_filename).read_bytes()

        return entries
