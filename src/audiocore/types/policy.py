"""Selection policy enum for automatic backend selection."""

from enum import Enum


class SelectionPolicy(str, Enum):
    """Policy for automatic backend selection.

    Inherits from str and Enum for JSON serialization support.
    """

    PREFER_LOCAL = "prefer_local"
    PREFER_CLOUD = "prefer_cloud"
    AUTO = "auto"

    @classmethod
    def parse(cls, value: str) -> "SelectionPolicy":
        """Parse a string to SelectionPolicy case-insensitively.

        Args:
            value: String to parse (e.g., "PreferLocal", "prefer_local", "PREFER_LOCAL")

        Returns:
            SelectionPolicy enum member

        Raises:
            ValueError: If value is not a valid selection policy
        """
        normalized = value.lower().replace("-", "_").replace(" ", "_")
        try:
            return cls(normalized)
        except ValueError:
            valid_options = ", ".join(f"'{m.value}'" for m in cls)
            raise ValueError(f"Invalid selection policy '{value}'. Valid options: {valid_options}")
