#!/usr/bin/env python3
"""
Prototype to investigate what subagent output looks like in stream-json.

Run with:
    uv run python scripts/investigate_task_output.py

This spawns a Claude session that uses the Task tool, captures the raw JSON,
and saves it for analysis.
"""

import json
import subprocess
from pathlib import Path

OUTPUT_FILE = Path(__file__).parent / "task_tool_output.jsonl"

# A prompt that will definitely trigger Task tool usage
PROMPT = """
You MUST use the Task tool with subagent_type=Explore to find any Python files in the current directory.
This is mandatory - do not skip using the Task tool.
After the Task completes, say "Done" and nothing else.
"""


def main():
    print(f"🔍 Capturing Task tool output to: {OUTPUT_FILE}")
    print("=" * 60)

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
        "haiku",  # Use haiku for speed/cost
    ]

    print(f"Running: {' '.join(cmd[:4])}...")

    events = []
    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    ) as proc:
        for raw_line in proc.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                events.append(event)

                # Print interesting events
                event_type = event.get("type", "unknown")

                if event_type == "assistant":
                    content = event.get("message", {}).get("content", [])
                    for block in content:
                        if block.get("type") == "tool_use":
                            tool_name = block.get("name", "?")
                            print(f"\n📤 TOOL_USE: {tool_name}")
                            if tool_name == "Task":
                                inp = block.get("input", {})
                                print(f"   subagent_type: {inp.get('subagent_type')}")
                                print(f"   description: {inp.get('description')}")
                        elif block.get("type") == "text":
                            text = block.get("text", "")[:100]
                            if text.strip():
                                print(f"\n💬 TEXT: {text}...")

                elif event_type == "user":
                    content = event.get("message", {}).get("content", [])
                    for block in content:
                        if block.get("type") == "tool_result":
                            tool_id = block.get("tool_use_id", "?")
                            result_content = block.get("content", "")
                            print(f"\n📥 TOOL_RESULT for {tool_id[:20]}...")
                            print(f"   Length: {len(result_content)} chars")
                            # Print first 500 chars to see structure
                            preview = result_content[:500] if isinstance(result_content, str) else str(result_content)[:500]
                            print(f"   Preview:\n{preview}")
                            print("   ...")

                elif event_type == "result":
                    print(f"\n✅ RESULT: {event.get('subtype')}")

            except json.JSONDecodeError:
                print(f"⚠️ Non-JSON: {line[:80]}")

    # Save all events
    with OUTPUT_FILE.open("w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    print("\n" + "=" * 60)
    print(f"📁 Saved {len(events)} events to {OUTPUT_FILE}")
    print("\nNow analyze with:")
    print(f"  cat {OUTPUT_FILE} | jq 'select(.type==\"user\")' ")


if __name__ == "__main__":
    main()
