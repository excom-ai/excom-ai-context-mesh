#!/usr/bin/env python3
"""Generic interactive CLI for ContextMesh agents.

This CLI connects to an OpenAPI server and uses playbooks to guide
AI-powered customer service interactions.

Usage:
    from contextmesh.cli import ContextMeshCLI

    cli = ContextMeshCLI(
        openapi_url="http://localhost:8052/openapi.json",
        playbooks_dir=Path("./playbooks"),
        system_prompt_file=Path("./system_prompt.md"),
    )
    cli.run()
"""

import os
import sys
from pathlib import Path

from anthropic import Anthropic

from contextmesh.tools import (
    OpenAPIToolkit,
    execute_playbook_tool,
    get_playbook_tools,
    list_playbooks,
)

# ANSI colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


class ContextMeshCLI:
    """Interactive CLI for ContextMesh-powered agents."""

    def __init__(
        self,
        openapi_url: str,
        playbooks_dir: Path,
        system_prompt_file: Path,
        model: str = "claude-haiku-4-5-20251001",
        title: str = "ContextMesh CLI",
    ):
        """Initialize the CLI.

        Args:
            openapi_url: URL to the OpenAPI specification (e.g., http://localhost:8052/openapi.json)
            playbooks_dir: Directory containing playbook markdown files
            system_prompt_file: Path to the system prompt markdown file
            model: Anthropic model to use
            title: Title to display in the CLI header
        """
        self.openapi_url = openapi_url
        self.playbooks_dir = playbooks_dir
        self.system_prompt_file = system_prompt_file
        self.model = model
        self.title = title

        # Initialize toolkit and client
        self.api_toolkit = OpenAPIToolkit(openapi_url)
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        self.messages: list = []

        # Load system prompt
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Load system prompt from file."""
        if self.system_prompt_file.exists():
            return self.system_prompt_file.read_text()
        return "You are a helpful assistant."

    def _get_tools(self) -> list[dict]:
        """Get all available tools (API + playbook tools)."""
        api_tools = self.api_toolkit.get_tools()
        playbook_tools = get_playbook_tools()
        return api_tools + playbook_tools

    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool and return the result."""
        # Try playbook tools first
        playbook_result = execute_playbook_tool(
            tool_name, tool_input, self.playbooks_dir
        )
        if playbook_result is not None:
            return playbook_result

        # Try API tools
        return self.api_toolkit.execute(tool_name, tool_input)

    def _print_header(self, playbook_names: list[str] | None = None):
        """Print welcome header."""
        playbook_list = ""
        if playbook_names:
            playbook_list = f"\n{BOLD}Available Playbooks:{RESET}\n"
            for pb in playbook_names:
                playbook_list += f"  {GREEN}•{RESET} {pb}\n"

        print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════════╗
║              {self.title:^44}║
╚══════════════════════════════════════════════════════════════════╝{RESET}
{playbook_list}
{BOLD}Commands:{RESET}
  {GREEN}/new{RESET}      - Start a new conversation
  {GREEN}/help{RESET}     - Show this help
  {GREEN}/quit{RESET}     - Exit

{DIM}Just type your message to chat with the AI assistant.{RESET}
""")

    def _chat(self, user_input: str) -> str:
        """Send message to AI and get response."""
        self.messages.append({"role": "user", "content": user_input})

        tools = self._get_tools()

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=self.system_prompt,
            messages=self.messages,
            tools=tools,
        )

        # Handle tool use loop
        while response.stop_reason == "tool_use":
            tool_uses = [
                block for block in response.content if block.type == "tool_use"
            ]

            tool_results = []
            for tool_use in tool_uses:
                print(f"{DIM}  → Calling {tool_use.name}({tool_use.input})...{RESET}")
                result = self._execute_tool(tool_use.name, tool_use.input)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result,
                })

            self.messages.append({"role": "assistant", "content": response.content})
            self.messages.append({"role": "user", "content": tool_results})

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.system_prompt,
                messages=self.messages,
                tools=tools,
            )

        # Extract text from final response
        text_blocks = [
            block.text for block in response.content if hasattr(block, "text")
        ]
        assistant_message = "\n".join(text_blocks)

        self.messages.append({"role": "assistant", "content": assistant_message})

        return assistant_message

    def run(self):
        """Run the interactive CLI."""
        # Check for API key
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print(f"{RED}Error: ANTHROPIC_API_KEY not set{RESET}")
            print("Run: export ANTHROPIC_API_KEY=your-key-here\n")
            sys.exit(1)

        # Load playbook names for display
        playbooks = list_playbooks(self.playbooks_dir)
        playbook_names = [pb["name"].replace("_", " ").title() for pb in playbooks]

        # Print header
        self._print_header(playbook_names)
        print(f"{GREEN}✓ Loaded {len(playbook_names)} playbook(s){RESET}")
        print(f"{GREEN}✓ AI assistant ready{RESET}\n")

        # Initial greeting
        greeting = "Hello! I'm here to help you with "
        if len(playbook_names) > 1:
            greeting += (
                ", ".join(playbook_names[:-1]).lower()
                + f" and {playbook_names[-1].lower()}"
            )
        elif playbook_names:
            greeting += playbook_names[0].lower()
        else:
            greeting += "your requests"
        greeting += ". How can I help you today?"

        print(f"{MAGENTA}Assistant:{RESET} {greeting}\n")

        while True:
            print(f"{CYAN}You:{RESET} ", end="", flush=True)
            try:
                user_input = input().strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                cmd = user_input[1:].lower().split()[0]

                if cmd in ("quit", "exit", "q"):
                    print("Goodbye!")
                    break

                elif cmd == "help":
                    self._print_header(playbook_names)

                elif cmd == "new":
                    self.messages = []
                    print(f"\n{GREEN}✓ Started new conversation{RESET}\n")
                    print(
                        f"{MAGENTA}Assistant:{RESET} Let's start fresh! "
                        "How can I help you today?\n"
                    )

                else:
                    print(
                        f"{YELLOW}Unknown command: /{cmd}. "
                        f"Type /help for options.{RESET}\n"
                    )

            else:
                # Chat with AI
                try:
                    response = self._chat(user_input)
                    print(f"{MAGENTA}Assistant:{RESET} {response}\n")
                except Exception as e:
                    print(f"{RED}Error communicating with AI: {e}{RESET}\n")
