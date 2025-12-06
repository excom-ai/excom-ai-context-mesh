"""Playbook tools for the telco billing CLI.

These are framework-level tools for loading business rules from local playbook files.
Playbooks are not exposed as API endpoints - they are special tools that read from
the local filesystem.
"""

import json
from pathlib import Path

from contextmesh.parsers.playbook_parser import PlaybookParser


def get_playbook_tools() -> list[dict]:
    """Return static playbook tools for loading business rules."""
    return [
        {
            "name": "list_playbooks",
            "description": "List all available business playbooks with their goals. Use this to find the right playbook for the customer's request.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "get_playbook",
            "description": "Load a specific business playbook to get detailed rules, steps, decision criteria, and thresholds. Use this after identifying which playbook matches the customer's request.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "playbook_name": {
                        "type": "string",
                        "description": "The playbook name (e.g., 'billing_dispute_resolution', 'plan_upgrade')",
                    }
                },
                "required": ["playbook_name"],
            },
        },
    ]


def list_playbooks(playbooks_dir: Path) -> list[dict]:
    """List all available playbooks with their goals."""
    parser = PlaybookParser()
    playbooks_list = []
    for playbook_file in playbooks_dir.glob("*.md"):
        try:
            pb = parser.load_playbook(playbook_file)
            playbooks_list.append({"name": pb.module_name, "goal": pb.goal})
        except Exception:
            pass
    return playbooks_list


def get_playbook(playbooks_dir: Path, playbook_name: str) -> str | None:
    """Load a specific playbook's raw markdown content."""
    parser = PlaybookParser()
    for playbook_file in playbooks_dir.glob("*.md"):
        try:
            pb = parser.load_playbook(playbook_file)
            if pb.module_name == playbook_name or playbook_file.stem == playbook_name:
                return pb.raw_markdown
        except Exception:
            pass
    return None


def execute_playbook_tool(tool_name: str, tool_input: dict, playbooks_dir: Path) -> str | None:
    """Execute a playbook tool and return the result.

    Returns None if the tool_name is not a playbook tool.
    """
    if tool_name == "list_playbooks":
        playbooks = list_playbooks(playbooks_dir)
        return json.dumps({"playbooks": playbooks}, indent=2)

    if tool_name == "get_playbook":
        playbook_name = tool_input.get("playbook_name", "")
        content = get_playbook(playbooks_dir, playbook_name)
        if content:
            return content
        return f"Playbook '{playbook_name}' not found. Use list_playbooks to see available options."

    return None
