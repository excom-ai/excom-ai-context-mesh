#!/usr/bin/env python3
"""Run the Hotel & Travel guest services CLI.

This is a thin wrapper that configures the generic ContextMesh CLI
with hotel-specific settings (server URL, playbooks, system prompt).

Prerequisites:
    1. Start the hotel mock server (in ../excom-context-mesh-hotel-mock-server):
       poetry run mock-server

    2. Start the northbound server:
       poetry run python examples/hotel/northbound_server.py

    3. Set your API key:
       export ANTHROPIC_API_KEY=your-key-here

Usage:
    poetry run python examples/hotel/run.py
"""

from pathlib import Path

from dotenv import load_dotenv

from contextmesh.cli import ContextMeshCLI

# Load environment variables
load_dotenv()

# Configuration for the hotel example
# Northbound server (enriched context) on port 8054
# Southbound mock server on port 9300
OPENAPI_URL = "http://localhost:8054/openapi.json"
EXAMPLE_DIR = Path(__file__).parent
PLAYBOOKS_DIR = EXAMPLE_DIR / "playbooks"
SYSTEM_PROMPT_FILE = EXAMPLE_DIR / "system_prompt.md"


def main():
    """Run the hotel CLI."""
    cli = ContextMeshCLI(
        openapi_url=OPENAPI_URL,
        playbooks_dir=PLAYBOOKS_DIR,
        system_prompt_file=SYSTEM_PROMPT_FILE,
        title="Hotel & Travel - Guest Services",
    )
    cli.run()


if __name__ == "__main__":
    main()
