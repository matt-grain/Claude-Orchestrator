"""HUD header widget showing phase info, status, timer, and token usage."""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class HUDHeader(Static):
    """Fixed header widget showing phase info, status, timer, and token usage."""

    phase_info = reactive("Phase 0/0: Starting...")
    status = reactive("Running")
    status_style = reactive("green")
    elapsed = reactive("00:00:00")
    context_pct = reactive(0)
    total_tokens = reactive(0)
    cost_usd = reactive(0.0)
    active_agent = reactive("Debussy")  # Current agent (Debussy, Explore, etc.)
    model = reactive("")  # Current Claude model (e.g., "opus", "sonnet", "haiku")

    def render(self) -> Text:
        """Render the HUD header."""
        text = Text()

        # Phase info
        text.append("Phase ", style="dim")
        text.append(self.phase_info, style="bold cyan")
        text.append("  |  ", style="dim")

        # Status indicator
        text.append(f"● {self.status}", style=self.status_style)
        text.append("  |  ", style="dim")

        # Active agent with model (highlighted when not Debussy)
        agent = self.active_agent
        model_suffix = f" ({self.model})" if self.model else ""
        if agent == "Debussy":
            text.append(f"🎹 {agent}{model_suffix}", style="dim")
        else:
            text.append(f"🤖 {agent}", style="bold magenta")
            if model_suffix:
                text.append(model_suffix, style="dim")
        text.append("  |  ", style="dim")

        # Timer
        text.append(f"⏱ {self.elapsed}", style="dim")
        text.append("  |  ", style="dim")

        # Context window usage (color-coded)
        pct = self.context_pct
        if pct < 50:
            pct_style = "green"
        elif pct < 80:
            pct_style = "yellow"
        else:
            pct_style = "red bold"
        text.append(f"📊 {pct}%", style=pct_style)
        text.append("  |  ", style="dim")

        # Total tokens (formatted with K suffix)
        tokens_str = self._format_tokens(self.total_tokens)
        text.append(f"🔤 {tokens_str}", style="dim")
        text.append("  |  ", style="dim")

        # Cost
        text.append(f"💰 ${self.cost_usd:.2f}", style="dim")

        return text

    @staticmethod
    def _format_tokens(tokens: int) -> str:
        """Format token count with K/M suffix."""
        if tokens >= 1_000_000:
            return f"{tokens / 1_000_000:.1f}M"
        if tokens >= 1_000:
            return f"{tokens / 1_000:.1f}K"
        return str(tokens)
