"""Unit tests for output module imports."""

import pytest

from audiocore.output import format_json, format_srt, format_text, format_vtt


class TestOutputImports:
    """Tests to verify all output formatters are properly exported."""

    def test_format_text_imported(self) -> None:
        """format_text is importable from audiocore.output."""
        assert callable(format_text)
        assert format_text.__name__ == "format_text"

    def test_format_json_imported(self) -> None:
        """format_json is importable from audiocore.output."""
        assert callable(format_json)
        assert format_json.__name__ == "format_json"

    def test_format_srt_imported(self) -> None:
        """format_srt is importable from audiocore.output."""
        assert callable(format_srt)
        assert format_srt.__name__ == "format_srt"

    def test_format_vtt_imported(self) -> None:
        """format_vtt is importable from audiocore.output."""
        assert callable(format_vtt)
        assert format_vtt.__name__ == "format_vtt"

    def test_all_formatters_in_dunder_all(self) -> None:
        """All formatters are listed in __all__."""
        from audiocore.output import __all__

        assert "format_text" in __all__
        assert "format_json" in __all__
        assert "format_srt" in __all__
        assert "format_vtt" in __all__
        assert len(__all__) == 4

    def test_direct_import(self) -> None:
        """Formatters can be imported directly from module files."""
        # Verify the actual module names work
        import audiocore.output.text as text_mod
        import audiocore.output.json as json_mod
        import audiocore.output.srt as srt_mod
        import audiocore.output.vtt as vtt_mod

        assert hasattr(text_mod, "format_text")
        assert hasattr(json_mod, "format_json")
        assert hasattr(srt_mod, "format_srt")
        assert hasattr(vtt_mod, "format_vtt")

    def test_module_docstring_mentions_formats(self) -> None:
        """Module docstring mentions all output formats."""
        import audiocore.output as output_mod

        docstring = output_mod.__doc__
        assert docstring is not None
        assert "text" in docstring.lower()
        assert "json" in docstring.lower()
        assert "srt" in docstring.lower()
        assert "vtt" in docstring.lower()
