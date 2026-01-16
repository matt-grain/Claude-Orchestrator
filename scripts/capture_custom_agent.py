#!/usr/bin/env python3
"""
Capture Task tool output when invoking a CUSTOM agent (like file-existence-checker).
"""

import json
import subprocess
from pathlib import Path

OUTPUT_FILE = Path(__file__).parent / "custom_agent_output.jsonl"

# Prompt that invokes a custom agent by name
PROMPT = """
You have access to a custom agent called "file-existence-checker".
Use the Task tool to invoke this agent with description "Check files" and ask it to verify that pyproject.toml exists.
After the Task completes, say "Done".
"""


def main():
    print(f"Capturing custom agent Task output to: {OUTPUT_FILE}")

    cmd = [
        "claude",
        "-p",
        PROMPT,
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-turns",
        "3",
        "--model",
        "haiku",
    ]

    events = []
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
        for raw_line in proc.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                events.append(event)

                if event.get("type") == "assistant":
                    for block in event.get("message", {}).get("content", []):
                        if block.get("type") == "tool_use" and block.get("name") == "Task":
                            print("\n=== TASK TOOL_USE ===")
                            print(f"id: {block.get('id')}")
                            inp = block.get("input", {})
                            print(f"subagent_type: {inp.get('subagent_type')}")
                            print(f"description: {inp.get('description')}")
                            print(f"prompt: {inp.get('prompt', '')[:100]}...")

            except json.JSONDecodeError:
                pass

    with OUTPUT_FILE.open("w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    print(f"\nSaved {len(events)} events to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
