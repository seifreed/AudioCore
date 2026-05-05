"""Selection policy enum for automatic backend selection."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Self


class SelectionPolicy(StrEnum):
    """Policy for automatic backend selection.

    Inherits from str and Enum for JSON serialization support.
    """

    PREFER_LOCAL = "prefer_local"
    PREFER_CLOUD = "prefer_cloud"
    AUTO = "auto"

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse a string to SelectionPolicy case-insensitively.

        Args:
            value: String to parse (e.g., "prefer_local", "PreferLocal", "PREFER_LOCAL")

        Returns:
            SelectionPolicy enum member

        Raises:
            ValueError: If value is not a valid selection policy
        """
        # Handle camelCase or PascalCase: insert underscore before uppercase letters
        # "PreferLocal" → "Prefer_Local", then lowercase
        normalized = re.sub(r"([a-z])([A-Z])", r"\1_\2", value.strip())
        # Now normalize: lowercase and replace spaces/hyphens with underscores
        normalized = normalized.lower().replace("-", "_").replace(" ", "_")

        try:
            return cls(normalized)
        except ValueError:
            valid_options = ", ".join(f"'{m.value}'" for m in cls)
            raise ValueError(
                f"Invalid selection policy '{value}'. Valid options: {valid_options}"
            ) from None
