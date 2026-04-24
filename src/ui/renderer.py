from __future__ import annotations

import textwrap

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule


class ConsoleUI:
    def __init__(self, width: int = 100):
        self.console = Console(width=width, soft_wrap=True, color_system="256")
        self.width = width

    def hr(self, char: str = "─", style: str = "white", bold: bool = False) -> None:
        text = char * self.width
        prefix = "bold " if bold else ""
        self.console.print(f"[{prefix}{style}]{text}[/{prefix}{style}]")

    def separator(self) -> None:
        self.console.print(Rule(style="grey70"))

    def title(self, text: str) -> None:
        self.console.print()
        self.console.print(
            Panel.fit(
                f"[bold white]{text}[/bold white]",
                border_style="bright_cyan",
                padding=(0, 2),
            )
        )

    def section(self, text: str) -> None:
        self.console.print()
        self.console.print(Rule(f"[bold bright_yellow]{text}[/bold bright_yellow]", style="white"))

    def kv(self, key: str, value: str, value_style: str = "bold white") -> None:
        self.console.print(
            f"[bold bright_cyan]{key}[/bold bright_cyan]"
            f"[bold white]:[/bold white] "
            f"[{value_style}]{value}[/{value_style}]"
        )

    def paragraph(self, text: str, indent: int = 2, style: str = "white") -> None:
        wrapped = textwrap.fill(
            text,
            width=self.width - indent,
            initial_indent=" " * indent,
            subsequent_indent=" " * indent,
            break_long_words=False,
            break_on_hyphens=False,
        )
        self.console.print(f"[{style}]{wrapped}[/{style}]")

    def bullet(self, text: str, style: str = "bold bright_cyan", detail: str | None = None) -> None:
        self.console.print(f"[{style}]• {text}[/{style}]")
        if detail:
            self.paragraph(detail, indent=4, style="white")

    def step(self, index: int, total: int, text: str) -> None:
        self.console.print()
        self.console.print(
            f"[bold bright_blue][{index}/{total}][/bold bright_blue] "
            f"[bold bright_yellow]{text}[/bold bright_yellow]"
        )
        self.separator()

    def success(self, text: str) -> None:
        self.console.print(f"[bold bright_green]✔ {text}[/bold bright_green]")

    def warning(self, text: str) -> None:
        self.console.print(f"[bold bright_yellow]▲ {text}[/bold bright_yellow]")

    def error(self, text: str) -> None:
        self.console.print(f"[bold bright_red]✖ {text}[/bold bright_red]")

    def info(self, text: str) -> None:
        self.console.print(f"[bold bright_blue]➜ {text}[/bold bright_blue]")

    def artifact(self, label: str, path: str, style: str = "bold bright_magenta") -> None:
        self.console.print(
            f"[bold bright_cyan]• {label}[/bold bright_cyan]"
            f"[bold white]:[/bold white] "
            f"[{style}]{path}[/{style}]"
        )

    def scenario_plan_item(self, index: int, total: int, name: str, cycles: int, description: str = "") -> None:
        self.console.print(
            f"[bold bright_cyan][{index}/{total}] {name}[/bold bright_cyan] "
            f"[bold bright_white]({cycles} cycles)[/bold bright_white]"
        )
        if description:
            self.paragraph(description, indent=4, style="white")

    def scenario_result(self, index: int, total: int, name: str, passed: bool) -> None:
        if passed:
            self.console.print(f"[bold bright_green]✔ PASS [{index}/{total}] {name}[/bold bright_green]")
        else:
            self.console.print(f"[bold bright_red]✖ FAIL [{index}/{total}] {name}[/bold bright_red]")

    def summary_row(self, label: str, value: str | int, style: str) -> None:
        self.console.print(
            f"[bold {style}]• {label}[/bold {style}]"
            f"[bold white]:[/bold white] "
            f"[bold {style}]{value}[/bold {style}]"
        )

    def note(self, text: str) -> None:
        self.console.print(f"[grey70]{text}[/grey70]")