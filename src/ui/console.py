from __future__ import annotations

import textwrap


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    BLACK = "\033[30m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    GRAY = "\033[37m"


def color(text: str, *styles: str) -> str:
    return "".join(styles) + text + C.RESET


def line(char: str = "─", width: int = 88) -> str:
    return char * width


def wrap_block(text: str, indent: str = "", width: int = 88) -> str:
    return textwrap.fill(
        text,
        width=width,
        initial_indent=indent,
        subsequent_indent=indent,
        break_long_words=False,
        break_on_hyphens=False,
    )


def section(title: str) -> None:
    print()
    print(color(line("═"), C.BOLD, C.CYAN))
    print(color(title, C.BOLD, C.WHITE))
    print(color(line("═"), C.BOLD, C.CYAN))


def subsection(title: str) -> None:
    print()
    print(color(title, C.BOLD, C.YELLOW))
    print(color(line("─"), C.WHITE))


def kv(label: str, value: str) -> None:
    print(color(label, C.BOLD, C.CYAN) + color(":", C.BOLD, C.WHITE) + f" {value}")


def ok(text: str) -> str:
    return color(text, C.BOLD, C.GREEN)


def warn(text: str) -> str:
    return color(text, C.BOLD, C.YELLOW)


def err(text: str) -> str:
    return color(text, C.BOLD, C.RED)


def info(text: str) -> str:
    return color(text, C.BOLD, C.BLUE)