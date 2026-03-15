"""Auto-commit and git integration at phase boundaries."""
# pyright: reportAttributeAccessIssue=false
# Mixin class — attributes are defined in Orchestrator which inherits this mixin.

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from debussy.core.models import Phase

logger = logging.getLogger(__name__)


class RetryHandlerMixin:
    """Mixin for git auto-commit at phase boundaries.

    Handles committing phase work after completion or failure.
    Mixed into Orchestrator — all methods have access to full self state.
    """

    def _auto_commit_phase(self,phase: Phase, success: bool) -> None:
        """Auto-commit changes at phase boundary.

        Args:
            phase: The phase that completed
            success: Whether the phase completed successfully
        """
        # Check if auto-commit is enabled
        if not self.config.auto_commit:
            logger.debug("Auto-commit disabled, skipping commit")
            self._event_logger.log_commit_skipped(phase.id, "auto-commit disabled")
            return

        # Skip commit on failure unless commit_on_failure is enabled
        if not success and not self.config.commit_on_failure:
            logger.debug("Phase failed and commit_on_failure=False, skipping commit")
            self._event_logger.log_commit_skipped(phase.id, "commit_on_failure disabled")
            return

        # Check for changes using git status
        has_changes = self._git_has_changes()
        if has_changes is None:
            return  # Git error occurred
        if not has_changes:
            logger.debug("No changes to commit, skipping")
            self._event_logger.log_commit_skipped(phase.id, "no changes")
            self.ui.log_raw("[dim]No changes to commit[/dim]")
            return

        # Format and execute commit
        self._execute_git_commit(phase, success)

    def _git_has_changes(self) -> bool | None:
        """Check if there are uncommitted changes.

        Returns:
            True if there are changes, False if clean, None on error.
        """
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=10,
                check=False,
            )
            if result.returncode != 0:
                logger.warning(f"Git status failed: {result.stderr}")
                return None
            return bool(result.stdout.strip())
        except FileNotFoundError:
            logger.warning("Git not found, skipping auto-commit")
            return None
        except subprocess.TimeoutExpired:
            logger.warning("Git status timed out, skipping auto-commit")
            return None

    def _execute_git_commit(self,phase: Phase, success: bool) -> None:
        """Execute git add and commit for a phase.

        Args:
            phase: The phase that completed
            success: Whether the phase completed successfully
        """
        import re

        # Format commit message using template
        status_icon = "✓" if success else "⚠️"
        message = self.config.commit_message_template.format(
            phase_id=phase.id,
            phase_name=phase.title,
            status=status_icon,
        )

        # Get model name for Co-Authored-By
        model_name = self.config.model.capitalize()
        co_author = f"Co-Authored-By: Claude {model_name} <noreply@anthropic.com>"

        full_message = f"{message}\n\n{co_author}"

        # Stage changes and commit
        # Use -u to only stage modified/deleted tracked files, avoiding random untracked files
        # Then explicitly add known phase artifacts (notes, plan status updates)
        try:
            # Stage modified tracked files only
            add_result = subprocess.run(
                ["git", "add", "-u"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=30,
                check=False,
            )
            if add_result.returncode != 0:
                logger.warning(f"Git add -u failed: {add_result.stderr}")
                return

            # Explicitly add phase notes file if it exists
            notes_dir = self.master_plan_path.parent / "notes"
            if notes_dir.exists():
                subprocess.run(
                    ["git", "add", str(notes_dir)],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                    timeout=30,
                    check=False,
                )

            # Commit with message
            commit_result = subprocess.run(
                ["git", "commit", "-m", full_message],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=30,
                check=False,
            )
            if commit_result.returncode != 0:
                # Check if it's just "nothing to commit"
                if "nothing to commit" in commit_result.stdout.lower():
                    logger.debug("Nothing to commit after staging")
                    self._event_logger.log_commit_skipped(phase.id, "nothing to commit after staging")
                    return
                logger.warning(f"Git commit failed: {commit_result.stderr}")
                self.ui.log_raw(f"[yellow]Auto-commit failed: {commit_result.stderr.strip()}[/yellow]")
                return

            # Count files changed from commit output
            files_changed = 0
            match = re.search(r"(\d+) files? changed", commit_result.stdout)
            if match:
                files_changed = int(match.group(1))

            # Log successful commit
            self._event_logger.log_commit(phase.id, message, files_changed)
            logger.info(f"Auto-commit successful: {message}")
            self.ui.log_raw(f"[green]Auto-commit: {message}[/green]")

        except FileNotFoundError:
            logger.warning("Git not found, skipping auto-commit")
        except subprocess.TimeoutExpired:
            logger.warning("Git command timed out during auto-commit")
            self.ui.log_raw("[yellow]Auto-commit timed out[/yellow]")
