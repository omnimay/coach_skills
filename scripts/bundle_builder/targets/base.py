"""Target builder protocol definition."""

from pathlib import Path
from typing import Any, Protocol


class TargetBuilder(Protocol):
    """Target builder protocol.

    Each target (workbuddy, universal, etc.) must implement this interface.
    The target is only responsible for target-specific files.
    Common files (mcp.json, skills) are handled by build.py.
    """

    def validate(self, bundle: dict[str, Any]) -> None:
        """Validate bundle for this target.

        Args:
            bundle: Bundle configuration dict

        Raises:
            ValueError: If validation fails
        """
        ...

    def build_entries(
        self,
        bundle: dict[str, Any],
        env_vars: dict[str, str],
    ) -> dict[Path, bytes]:
        """Build target-specific entries.

        This method should only return files that are specific to this target.
        Common files (mcp.json, skills) are handled by build.py.

        Args:
            bundle: Bundle configuration dict
            env_vars: Environment variables for placeholder resolution

        Returns:
            Dict mapping archive path to file contents
        """
        ...
