"""Parser for Markdown playbooks."""

import re
from pathlib import Path

from contextmesh.core.models import Playbook, PlaybookVariable
from contextmesh.utils.exceptions import PlaybookParseError


class PlaybookParser:
    """Parser for Markdown playbooks into structured Playbook objects."""

    # Regex patterns for parsing
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    VARIABLE_PATTERN = re.compile(r"logic\.(\w+(?:\.\w+)*)")
    LIST_ITEM_PATTERN = re.compile(r"^[-*]\s+(.+)$", re.MULTILINE)
    NUMBERED_ITEM_PATTERN = re.compile(r"^\d+\.\s+(.+)$", re.MULTILINE)

    def load_playbook(self, file_path: str | Path) -> Playbook:
        """Load and parse a playbook from a file.

        Args:
            file_path: Path to the Markdown playbook file

        Returns:
            Parsed Playbook object

        Raises:
            PlaybookParseError: If file cannot be read or parsed
        """
        path = Path(file_path)

        if not path.exists():
            raise PlaybookParseError(f"Playbook file not found: {file_path}")

        if not path.suffix.lower() == ".md":
            raise PlaybookParseError(f"Playbook must be a Markdown file (.md): {file_path}")

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            raise PlaybookParseError(f"Failed to read playbook file: {e}")

        # Extract module name from filename
        module_name = path.stem

        return self.parse_markdown(content, module_name)

    def parse_markdown(self, content: str, module_name: str = "unknown") -> Playbook:
        """Parse Markdown content into a Playbook object.

        Args:
            content: Raw Markdown content
            module_name: Name of the logic module

        Returns:
            Parsed Playbook object
        """
        sections = self._extract_sections(content)

        return Playbook(
            module_name=module_name,
            goal=self._extract_goal(sections),
            preconditions=self._extract_preconditions(sections),
            steps=self._extract_steps(sections),
            decision_rules=self._extract_decision_rules(sections),
            variables=self._extract_variables(content),
            raw_markdown=content,
        )

    def _extract_sections(self, content: str) -> dict[str, str]:
        """Extract sections by headings."""
        sections: dict[str, str] = {}
        current_heading = "intro"
        current_content: list[str] = []

        lines = content.split("\n")

        for line in lines:
            heading_match = self.HEADING_PATTERN.match(line)
            if heading_match:
                # Save previous section
                if current_content:
                    sections[current_heading.lower()] = "\n".join(current_content).strip()

                # Start new section
                current_heading = heading_match.group(2).strip()
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_heading.lower()] = "\n".join(current_content).strip()

        return sections

    def _extract_goal(self, sections: dict[str, str]) -> str:
        """Extract the goal from sections."""
        # Look for common goal-related section names
        for key in ["goal", "goals", "objective", "objectives", "purpose"]:
            if key in sections:
                return self._clean_text(sections[key])

        # Check intro for goal statement
        if "intro" in sections:
            intro = sections["intro"]
            # Look for "Goal:" prefix
            if "goal:" in intro.lower():
                for line in intro.split("\n"):
                    if line.lower().startswith("goal:"):
                        return self._clean_text(line.split(":", 1)[1])

        return ""

    def _extract_preconditions(self, sections: dict[str, str]) -> list[str]:
        """Extract preconditions as a list."""
        for key in ["preconditions", "prerequisites", "requirements"]:
            if key in sections:
                return self._extract_list_items(sections[key])
        return []

    def _extract_steps(self, sections: dict[str, str]) -> list[str]:
        """Extract steps as a list."""
        for key in ["steps", "procedure", "process", "workflow"]:
            if key in sections:
                return self._extract_list_items(sections[key])
        return []

    def _extract_decision_rules(self, sections: dict[str, str]) -> list[str]:
        """Extract decision rules."""
        rules: list[str] = []

        for key in ["decision rules", "rules", "logic", "conditions"]:
            if key in sections:
                rules.extend(self._extract_list_items(sections[key]))

        # Also look for if/else patterns in steps
        for key in ["steps", "procedure"]:
            if key in sections:
                content = sections[key]
                # Extract lines containing conditional logic
                for line in content.split("\n"):
                    if any(
                        keyword in line.lower()
                        for keyword in ["if ", "else", "when ", "threshold", "< ", "> "]
                    ):
                        cleaned = self._clean_text(line)
                        if cleaned and cleaned not in rules:
                            rules.append(cleaned)

        return rules

    def _extract_variables(self, content: str) -> list[PlaybookVariable]:
        """Extract logic.* variables from content."""
        variables: list[PlaybookVariable] = []
        seen: set[str] = set()

        # Find all logic.* references
        matches = self.VARIABLE_PATTERN.findall(content)

        for var_name in matches:
            full_name = f"logic.{var_name}"
            if full_name not in seen:
                seen.add(full_name)
                variables.append(
                    PlaybookVariable(
                        name=full_name,
                        description=self._find_variable_description(content, var_name),
                    )
                )

        return variables

    def _find_variable_description(self, content: str, var_name: str) -> str:
        """Try to find a description for a variable in nearby text."""
        # Look for lines mentioning the variable
        for line in content.split("\n"):
            if f"logic.{var_name}" in line:
                # Clean up the line as a description
                desc = line.strip()
                # Remove markdown formatting
                desc = re.sub(r"^[-*\d.]+\s*", "", desc)
                desc = re.sub(r"`[^`]+`", "", desc)
                if len(desc) > 10:
                    return desc[:200]  # Limit length
        return ""

    def _extract_list_items(self, content: str) -> list[str]:
        """Extract list items (bulleted or numbered) from content."""
        items: list[str] = []

        # Find bulleted items
        for match in self.LIST_ITEM_PATTERN.finditer(content):
            items.append(self._clean_text(match.group(1)))

        # Find numbered items
        for match in self.NUMBERED_ITEM_PATTERN.finditer(content):
            items.append(self._clean_text(match.group(1)))

        # If no list items found, split by lines
        if not items:
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    items.append(self._clean_text(line))

        return [item for item in items if item]

    def _clean_text(self, text: str) -> str:
        """Clean up text by removing extra whitespace and markdown artifacts."""
        # Remove leading/trailing whitespace
        text = text.strip()
        # Remove multiple spaces
        text = re.sub(r"\s+", " ", text)
        # Remove leading list markers
        text = re.sub(r"^[-*]\s+", "", text)
        text = re.sub(r"^\d+\.\s+", "", text)
        return text


def load_playbook(file_path: str | Path) -> Playbook:
    """Convenience function to load a playbook.

    Args:
        file_path: Path to the playbook file

    Returns:
        Parsed Playbook object
    """
    parser = PlaybookParser()
    return parser.load_playbook(file_path)
