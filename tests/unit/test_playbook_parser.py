"""Unit tests for PlaybookParser."""

from pathlib import Path

import pytest

from contextmesh.parsers.playbook_parser import PlaybookParser, load_playbook
from contextmesh.utils.exceptions import PlaybookParseError


class TestPlaybookParser:
    """Tests for PlaybookParser."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return PlaybookParser()

    def test_parse_markdown_extracts_module_name(self, parser, sample_playbook_markdown):
        """Test that module name is set correctly."""
        playbook = parser.parse_markdown(sample_playbook_markdown, "my_module")
        assert playbook.module_name == "my_module"

    def test_parse_markdown_extracts_goal(self, parser, sample_playbook_markdown):
        """Test that goal is extracted from content."""
        playbook = parser.parse_markdown(sample_playbook_markdown, "test")
        assert "Resolve customer issues" in playbook.goal

    def test_parse_markdown_extracts_preconditions(self, parser, sample_playbook_markdown):
        """Test that preconditions are extracted."""
        playbook = parser.parse_markdown(sample_playbook_markdown, "test")
        assert len(playbook.preconditions) >= 1
        assert any("Customer exists" in p for p in playbook.preconditions)

    def test_parse_markdown_extracts_steps(self, parser, sample_playbook_markdown):
        """Test that steps are extracted."""
        playbook = parser.parse_markdown(sample_playbook_markdown, "test")
        assert len(playbook.steps) >= 3
        assert any("Check customer" in s for s in playbook.steps)

    def test_parse_markdown_extracts_variables(self, parser, sample_playbook_markdown):
        """Test that logic.* variables are extracted."""
        playbook = parser.parse_markdown(sample_playbook_markdown, "test")
        var_names = [v.name for v in playbook.variables]
        assert "logic.recommended_amount" in var_names or "logic.escalation_required" in var_names

    def test_parse_markdown_preserves_raw(self, parser, sample_playbook_markdown):
        """Test that raw markdown is preserved."""
        playbook = parser.parse_markdown(sample_playbook_markdown, "test")
        assert playbook.raw_markdown == sample_playbook_markdown

    def test_parse_markdown_extracts_decision_rules(self, parser, sample_playbook_markdown):
        """Test that decision rules are extracted."""
        playbook = parser.parse_markdown(sample_playbook_markdown, "test")
        # Decision rules should include if/else patterns
        assert len(playbook.decision_rules) >= 1

    def test_load_playbook_from_file(self, parser, fixtures_dir):
        """Test loading playbook from file."""
        playbook_path = fixtures_dir / "test_billing_resolution.md"
        playbook = parser.load_playbook(playbook_path)
        assert playbook.module_name == "test_billing_resolution"
        assert "billing disputes" in playbook.goal.lower()

    def test_load_playbook_file_not_found(self, parser):
        """Test that missing file raises error."""
        with pytest.raises(PlaybookParseError) as exc_info:
            parser.load_playbook("/nonexistent/path.md")
        assert "not found" in str(exc_info.value)

    def test_load_playbook_invalid_extension(self, parser, tmp_path):
        """Test that non-markdown file raises error."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("content")
        with pytest.raises(PlaybookParseError) as exc_info:
            parser.load_playbook(txt_file)
        assert "Markdown" in str(exc_info.value)

    def test_convenience_function(self, fixtures_dir):
        """Test the load_playbook convenience function."""
        playbook_path = fixtures_dir / "test_billing_resolution.md"
        playbook = load_playbook(playbook_path)
        assert playbook.module_name == "test_billing_resolution"

    def test_extract_variables_finds_logic_prefix(self, parser):
        """Test that only logic.* variables are extracted."""
        content = """
        Some text with logic.amount and logic.status variables.
        Also mentions db.customer.id which should not be included.
        """
        playbook = parser.parse_markdown(content, "test")
        var_names = [v.name for v in playbook.variables]
        assert "logic.amount" in var_names
        assert "logic.status" in var_names
        assert "db.customer.id" not in var_names

    def test_extract_nested_variables(self, parser):
        """Test extraction of nested variable names."""
        content = "Set logic.recommendation.amount to 100"
        playbook = parser.parse_markdown(content, "test")
        var_names = [v.name for v in playbook.variables]
        assert "logic.recommendation.amount" in var_names

    def test_parse_empty_sections(self, parser):
        """Test parsing with minimal content."""
        content = "# Simple Playbook\n\nJust some text."
        playbook = parser.parse_markdown(content, "simple")
        assert playbook.module_name == "simple"
        assert playbook.raw_markdown == content

    def test_parse_bullet_list(self, parser):
        """Test parsing bullet list items."""
        content = """
## Steps

- First step
- Second step
- Third step
"""
        playbook = parser.parse_markdown(content, "test")
        assert len(playbook.steps) == 3

    def test_parse_numbered_list(self, parser):
        """Test parsing numbered list items."""
        content = """
## Steps

1. First step
2. Second step
3. Third step
"""
        playbook = parser.parse_markdown(content, "test")
        assert len(playbook.steps) == 3
