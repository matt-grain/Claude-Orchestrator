#!/usr/bin/env python3
"""Rename the project from 'orchestrator' to 'debussy'.

This script handles:
1. Renaming src/orchestrator/ to src/debussy/
2. Updating all Python imports
3. Updating pyproject.toml
4. Updating documentation and README
5. Updating CLI references
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

# Project root
ROOT = Path(__file__).parent.parent

# Mappings
OLD_NAME = "orchestrator"
NEW_NAME = "debussy"
OLD_CLI = "orchestrate"
NEW_CLI = "debussy"
OLD_DISPLAY = "Orchestrator"
NEW_DISPLAY = "Debussy"


def rename_directory() -> None:
    """Rename src/orchestrator to src/debussy."""
    old_dir = ROOT / "src" / OLD_NAME
    new_dir = ROOT / "src" / NEW_NAME

    if old_dir.exists():
        print(f"Renaming {old_dir} -> {new_dir}")
        shutil.move(str(old_dir), str(new_dir))
    else:
        print(f"Directory {old_dir} not found, skipping")


def update_imports_in_file(file_path: Path) -> bool:
    """Update imports in a single file. Returns True if file was modified."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        return False

    original = content

    # Update Python imports: from orchestrator -> from debussy
    content = re.sub(r"\bfrom orchestrator\b", f"from {NEW_NAME}", content)
    content = re.sub(r"\bimport orchestrator\b", f"import {NEW_NAME}", content)

    # Update string references to the module
    content = re.sub(r'"orchestrator\.', f'"{NEW_NAME}.', content)
    content = re.sub(r"'orchestrator\.", f"'{NEW_NAME}.", content)

    # Update CLI command references: orchestrate -> debussy
    content = re.sub(r"\borchestrate\b", NEW_CLI, content)

    # Update display name: Orchestrator -> Debussy (careful with case)
    content = re.sub(r"\bOrchestrator\b", NEW_DISPLAY, content)
    content = re.sub(r"\borchestrator\b", NEW_NAME, content)

    # Update project name in pyproject.toml style
    content = re.sub(r'name = "claude-orchestrator"', f'name = "claude-{NEW_NAME}"', content)

    # Update coverage source
    content = re.sub(r'source = \["src/orchestrator"\]', f'source = ["src/{NEW_NAME}"]', content)

    # Update known-first-party
    content = re.sub(
        r'known-first-party = \["orchestrator"\]',
        f'known-first-party = ["{NEW_NAME}"]',
        content,
    )

    if content != original:
        file_path.write_text(content, encoding="utf-8")
        return True
    return False


def update_all_files() -> None:
    """Update all relevant files in the project."""
    # File extensions to process
    extensions = {".py", ".md", ".toml", ".yaml", ".yml", ".txt"}

    # Directories to skip
    skip_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", ".ruff_cache"}

    modified_count = 0

    for file_path in ROOT.rglob("*"):
        # Skip directories
        if file_path.is_dir():
            continue

        # Skip files in excluded directories
        if any(skip in file_path.parts for skip in skip_dirs):
            continue

        # Skip the rename script itself
        if file_path.name == "rename_to_debussy.py":
            continue

        # Only process relevant extensions
        if file_path.suffix not in extensions:
            continue

        if update_imports_in_file(file_path):
            print(f"  Updated: {file_path.relative_to(ROOT)}")
            modified_count += 1

    print(f"\nModified {modified_count} files")


def update_readme_title() -> None:
    """Update the README title and description."""
    readme = ROOT / "README.md"
    if readme.exists():
        content = readme.read_text(encoding="utf-8")
        # Update title
        content = re.sub(
            r"^# Claude Orchestrator",
            "# Claude Debussy",
            content,
            flags=re.MULTILINE,
        )
        # Update description to include the pun
        content = re.sub(
            r"A Python orchestrator for",
            "A Python orchestrator (get it? Claude Debussy, the composer?) for",
            content,
        )
        readme.write_text(content, encoding="utf-8")
        print("  Updated: README.md title")


def main() -> None:
    """Run the rename process."""
    print("=" * 60)
    print("Renaming project: orchestrator -> debussy")
    print("=" * 60)

    print("\n1. Renaming source directory...")
    rename_directory()

    print("\n2. Updating file contents...")
    update_all_files()

    print("\n3. Updating README title...")
    update_readme_title()

    print("\n" + "=" * 60)
    print("Rename complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Update the ASCII banner in cli.py")
    print("  2. Run tests: uv run pytest tests/")
    print("  3. Run linting: uv run ruff check . --fix")
    print("  4. Commit the changes")


if __name__ == "__main__":
    main()
