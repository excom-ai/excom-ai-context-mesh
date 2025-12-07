#!/usr/bin/env python3
"""Run the Banking customer service CLI.

This is a thin wrapper that configures the generic ContextMesh CLI
with banking-specific settings (server URL, playbooks, system prompt).

Prerequisites:
    1. Start the banking mock server (in ../excom-context-mesh-banking-mock-server):
       poetry run mock-server

    2. Set your API key:
       export ANTHROPIC_API_KEY=your-key-here

Usage:
    poetry run python examples/banking/run.py
"""

from pathlib import Path

from dotenv import load_dotenv

from contextmesh.cli import ContextMeshCLI

# Load environment variables
load_dotenv()

# Configuration for the banking example
# Northbound server (enriched context) on port 8053
# Southbound mock server on port 9200
OPENAPI_URL = "http://localhost:8053/openapi.json"
EXAMPLE_DIR = Path(__file__).parent
PLAYBOOKS_DIR = EXAMPLE_DIR / "playbooks"
SYSTEM_PROMPT_FILE = EXAMPLE_DIR / "system_prompt.md"


def main():
    """Run the banking CLI."""
    cli = ContextMeshCLI(
        openapi_url=OPENAPI_URL,
        playbooks_dir=PLAYBOOKS_DIR,
        system_prompt_file=SYSTEM_PROMPT_FILE,
        title="Banking - Customer Service",
    )
    cli.run()


if __name__ == "__main__":
    main()
