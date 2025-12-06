#!/usr/bin/env python3
"""Interactive CLI for testing ContextMesh billing dispute scenarios.

Run the northbound server first:
    poetry run python examples/telco_billing/northbound_server.py

Then run this CLI:
    poetry run python examples/telco_billing/cli.py
"""

import os
import sys
from pathlib import Path

# Add the example directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from anthropic import Anthropic
from dotenv import load_dotenv

from playbook_tools import list_playbooks
from tools import get_chat_tools, execute_tool

# Load environment variables
load_dotenv()

# ANSI colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_header(playbook_names: list[str] | None = None):
    """Print welcome header."""
    playbook_list = ""
    if playbook_names:
        playbook_list = f"\n{BOLD}Available Playbooks:{RESET}\n"
        for pb in playbook_names:
            playbook_list += f"  {GREEN}•{RESET} {pb}\n"

    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════════╗
║              ContextMesh - Customer Service CLI                  ║
╚══════════════════════════════════════════════════════════════════╝{RESET}
{playbook_list}
{BOLD}Chat Mode:{RESET} Describe what you need help with.
           The AI will guide you through the process.

{BOLD}Commands:{RESET}
  {GREEN}/new{RESET}      - Start a new conversation
  {GREEN}/help{RESET}     - Show this help
  {GREEN}/quit{RESET}     - Exit

{DIM}Just type your message to chat with the AI assistant.{RESET}
""")


def print_prompt():
    """Print input prompt."""
    print(f"{CYAN}You:{RESET} ", end="", flush=True)


def print_ai_response(text: str):
    """Print AI response with formatting."""
    print(f"{MAGENTA}Assistant:{RESET} {text}\n")


def create_anthropic_client():
    """Create Anthropic client for chat."""
    return Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))


def chat_with_ai(
    client: Anthropic,
    messages: list,
    user_input: str,
    playbooks_dir: Path,
    system_prompt: str,
) -> str:
    """Send message to AI and get response."""
    messages.append({"role": "user", "content": user_input})

    # Get available tools for chat
    tools = get_chat_tools()

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
        tools=tools,
    )

    # Handle tool use loop
    while response.stop_reason == "tool_use":
        # Find all tool use blocks
        tool_uses = [block for block in response.content if block.type == "tool_use"]

        # Execute tools and collect results
        tool_results = []
        for tool_use in tool_uses:
            print(f"{DIM}  → Calling {tool_use.name}({tool_use.input})...{RESET}")
            result = execute_tool(tool_use.name, tool_use.input, playbooks_dir)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result
            })

        # Add assistant response (with tool use) and tool results to messages
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        # Get next response
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
            tools=tools,
        )

    # Extract text from final response
    text_blocks = [block.text for block in response.content if hasattr(block, "text")]
    assistant_message = "\n".join(text_blocks)

    messages.append({"role": "assistant", "content": assistant_message})

    return assistant_message


def main():
    """Run the interactive CLI."""
    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(f"{RED}Error: ANTHROPIC_API_KEY not set{RESET}")
        print("Run: export ANTHROPIC_API_KEY=your-key-here\n")
        sys.exit(1)

    # Load system prompt and playbooks
    example_dir = Path(__file__).parent
    playbooks_dir = example_dir / "playbooks"
    system_prompt_file = example_dir / "system_prompt.md"

    # Load system prompt from markdown file
    system_prompt = system_prompt_file.read_text()

    # Load playbook names for display
    playbooks = list_playbooks(playbooks_dir)
    playbook_names = [pb["name"].replace('_', ' ').title() for pb in playbooks]

    # Print header with discovered playbooks
    print_header(playbook_names)
    print(f"{GREEN}✓ Loaded {len(playbook_names)} playbook(s){RESET}")

    # Create AI client
    try:
        ai_client = create_anthropic_client()
        print(f"{GREEN}✓ AI assistant ready{RESET}\n")
    except Exception as e:
        print(f"{RED}Error initializing: {e}{RESET}\n")
        sys.exit(1)

    chat_messages = []

    # Initial greeting based on available playbooks
    greeting = "Hello! I'm here to help you with "
    if len(playbook_names) > 1:
        greeting += ", ".join(playbook_names[:-1]).lower() + f" and {playbook_names[-1].lower()}"
    elif playbook_names:
        greeting += playbook_names[0].lower()
    else:
        greeting += "your requests"
    greeting += ". How can I help you today?"

    print_ai_response(greeting)

    while True:
        print_prompt()
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
                print_header(playbook_names)

            elif cmd == "new":
                chat_messages = []
                print(f"\n{GREEN}✓ Started new conversation{RESET}\n")
                print_ai_response(
                    "Let's start fresh! How can I help you today?"
                )

            else:
                print(f"{YELLOW}Unknown command: /{cmd}. Type /help for options.{RESET}\n")

        else:
            # Chat with AI
            try:
                response = chat_with_ai(
                    ai_client, chat_messages, user_input, playbooks_dir, system_prompt
                )
                print_ai_response(response)

            except Exception as e:
                print(f"{RED}Error communicating with AI: {e}{RESET}\n")


if __name__ == "__main__":
    main()
