"""Test script to isolate terminal output issues on Windows."""

import asyncio
import sys


async def test_subprocess_output():
    """Test if asyncio subprocess output appears in terminal."""
    print("TEST 1: Direct print", flush=True)
    sys.stdout.write("TEST 2: sys.stdout.write\n")
    sys.stdout.flush()
    sys.stderr.write("TEST 3: sys.stderr.write\n")
    sys.stderr.flush()

    print("\nStarting subprocess test...", flush=True)

    # Simple subprocess that echoes lines
    proc = await asyncio.create_subprocess_exec(
        "wsl",
        "-e",
        "sh",
        "-c",
        'for i in 1 2 3 4 5; do echo "SUBPROCESS_LINE_$i"; sleep 0.5; done',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    print("Subprocess started, reading output...", flush=True)

    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        decoded = line.decode().strip()
        print(f"GOT: {decoded}", flush=True)
        sys.stderr.write(f"STDERR: {decoded}\n")
        sys.stderr.flush()

    await proc.wait()
    print(f"\nSubprocess exited with code: {proc.returncode}", flush=True)


if __name__ == "__main__":
    print("=" * 50)
    print("Terminal Output Test")
    print("=" * 50)
    asyncio.run(test_subprocess_output())
    print("\nTest complete!")
