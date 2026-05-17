from __future__ import annotations

import textwrap

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.theme import Theme


THEME = Theme(
    {
        "title": "bold #ffffff",
        "frame": "bold #00d7ff",
        "section": "bold #ffd75f",
        "label": "bold #00d7ff",
        "value": "bold #ffffff",
        "muted": "#c0c0c0",
        "info": "bold #5fd7ff",
        "success": "bold #00ff66",
        "warning": "bold #ffcc00",
        "error": "bold #ff4d4f",
        "artifact": "bold #ff66ff",
        "menu": "bold #66d9ef",
        "summary_total": "bold #ffffff",
        "summary_passed": "bold #00ff66",
        "summary_failed_ok": "bold #00ff66",
        "summary_failed_bad": "bold #ff4d4f",
    }
)


class ConsoleUI:
    def __init__(self, width: int = 100):
        self.console = Console(width=width, force_terminal=True, soft_wrap=True, color_system="truecolor", theme=THEME)
        self.width = width

    def hr(self, char: str = "─", style: str = "frame") -> None:
        self.console.print(char * self.width, style=style)

    def separator(self) -> None:
        self.console.print(Rule(style="muted"))

    def title(self, text: str) -> None:
        self.console.print()
        self.console.print(Panel.fit(Text(text, style="title"), border_style="frame", padding=(0, 2)))

    def section(self, text: str) -> None:
        self.console.print()
        self.console.print(Rule(Text(text, style="section"), style="muted"))

    def kv(self, key: str, value: str, value_style: str = "value") -> None:
        self.console.print(Text.assemble((key, "label"), (": ", "value"), (str(value), value_style)))

    def paragraph(self, text: str, indent: int = 2, style: str = "value") -> None:
        wrapped = textwrap.fill(
            text,
            width=self.width - indent,
            initial_indent=" " * indent,
            subsequent_indent=" " * indent,
            break_long_words=False,
            break_on_hyphens=False,
        )
        self.console.print(wrapped, style=style)

    def bullet(self, text: str, style: str = "menu", detail: str | None = None) -> None:
        self.console.print(Text.assemble(("• ", style), (text, style)))
        if detail:
            self.paragraph(detail, indent=4, style="value")

    def success(self, text: str) -> None:
        self.console.print(Text.assemble(("✔ ", "success"), (text, "success")))

    def warning(self, text: str) -> None:
        self.console.print(Text.assemble(("▲ ", "warning"), (text, "warning")))

    def error(self, text: str) -> None:
        self.console.print(Text.assemble(("✖ ", "error"), (text, "error")))

    def info(self, text: str) -> None:
        self.console.print(Text.assemble(("➜ ", "info"), (text, "info")))

    def artifact(self, label: str, path: str, style: str = "artifact") -> None:
        self.console.print(Text.assemble(("• ", "label"), (label, "label"), (": ", "value"), (path, style)))

    def scenario_result(self, index: int, total: int, name: str, passed: bool) -> None:
        style = "success" if passed else "error"
        marker = "✔ PASS " if passed else "✖ FAIL "
        self.console.print(Text.assemble((f"{marker}[{index}/{total}] ", style), (name, style)))

    def summary_row(self, label: str, value: str | int, style: str) -> None:
        self.console.print(Text.assemble(("• ", style), (label, style), (": ", "value"), (str(value), style)))

    def note(self, text: str) -> None:
        self.console.print(text, style="muted")
