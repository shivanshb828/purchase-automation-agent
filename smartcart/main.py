"""
Entry point for SmartCart — orchestrates the full 3-feature purchase automation flow.
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv
from rich import box
from rich.panel import Panel
from rich.text import Text

from agents.orchestrator import SmartCartOrchestrator
from utils.logger import _con, setup_logger

_DEFAULT_REQUEST = (
    "I need paper towels, hand soap, and snack crackers for my daycare"
)


def _startup_banner() -> None:
    con = _con()
    con.print()
    con.print(Panel(
        Text.assemble(
            ("  🛒  SmartCart — AI Procurement Agent\n", "bold cyan"),
            ("  Intelligent purchasing for small businesses  ", "dim white"),
        ),
        box=box.DOUBLE,
        border_style="cyan",
        expand=False,
        padding=(0, 2),
    ))
    con.print()


def _approval_panel(summary) -> None:
    con = _con()
    cart = summary.cart
    n = len(cart.items)
    total = cart.estimated_total
    savings = summary.total_savings
    pct = (savings / (total + savings) * 100) if (total + savings) > 0 else 0.0

    lines = Text()
    lines.append(f"  Items: {n}  |  Estimated Total: ${total:.2f}\n", style="bold white")
    if savings > 0:
        lines.append(
            f"  💰  You saved: ${savings:.2f}  ({pct:.0f}%)\n",
            style="bold yellow",
        )
    lines.append(
        "  Review the cart above, then confirm to proceed to checkout.",
        style="dim white",
    )

    con.print(Panel(
        lines,
        title="[bold green]✅  SmartCart Order Ready for Approval[/bold green]",
        border_style="green",
        box=box.ROUNDED,
        padding=(0, 1),
    ))
    con.print()


async def main() -> None:
    load_dotenv()
    setup_logger()
    con = _con()

    # Parse CLI arg
    request = sys.argv[1] if len(sys.argv) > 1 else _DEFAULT_REQUEST

    _startup_banner()
    con.print(f"[dim]Request:[/dim] [bold white]{request}[/bold white]\n")

    try:
        orchestrator = SmartCartOrchestrator()
        summary = await orchestrator.run(request)
        _approval_panel(summary)

    except KeyboardInterrupt:
        con.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(0)

    except Exception as exc:
        con.print(Panel(
            f"[red]{exc}[/red]",
            title="[bold red]✗  Unexpected Error[/bold red]",
            border_style="red",
            box=box.ROUNDED,
        ))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
