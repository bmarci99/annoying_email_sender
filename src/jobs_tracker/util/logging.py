from __future__ import annotations

import logging
import os

from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install


def setup_logger(name: str = "jobs_tracker"):
    """Configure Rich-based logging; returns (logger, console)."""
    install(show_locals=False)

    level = os.getenv("LOG_LEVEL", "INFO").upper()

    console = Console(force_terminal=True)

    handler = RichHandler(
        console=console,
        show_time=True,
        show_level=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    logger = logging.getLogger(name)
    return logger, console


def section(console: Console, title: str):
    """Print a bold section divider."""
    console.rule(f"[bold cyan]{title}[/bold cyan]")
