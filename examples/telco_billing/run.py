#!/usr/bin/env python3
"""Run the Telco Billing customer service CLI.

This is a thin wrapper that configures the generic ContextMesh CLI
with telco-specific settings (server URL, playbooks, system prompt).

Prerequisites:
    1. Start the northbound server:
       poetry run python examples/telco_billing/northbound_server.py

    2. Set your API key:
       export ANTHROPIC_API_KEY=your-key-here

Usage:
    poetry run python examples/telco_billing/run.py
"""

from pathlib import Path

from dotenv import load_dotenv

from contextmesh.cli import ContextMeshCLI

# Load environment variables
load_dotenv()

# Configuration for the telco billing example
OPENAPI_URL = "http://localhost:8052/openapi.json"
EXAMPLE_DIR = Path(__file__).parent
PLAYBOOKS_DIR = EXAMPLE_DIR / "playbooks"
SYSTEM_PROMPT_FILE = EXAMPLE_DIR / "system_prompt.md"


def main():
    """Run the telco billing CLI."""
    cli = ContextMeshCLI(
        openapi_url=OPENAPI_URL,
        playbooks_dir=PLAYBOOKS_DIR,
        system_prompt_file=SYSTEM_PROMPT_FILE,
        title="Telco Billing - Customer Service",
    )
    cli.run()


if __name__ == "__main__":
    main()
