"""
Rich-based logging and console narration layer for SmartCart.
The console output IS the demo — every log function is designed to look
impressive on-screen for a live audience.
"""

import logging
import time

from rich import box
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.theme import Theme

from config import APP

# ---------------------------------------------------------------------------
# Global console — shared by all log helpers
# ---------------------------------------------------------------------------

_THEME = Theme({
    "agent.name":      "bold magenta",
    "agent.action":    "bold cyan",
    "deal":            "bold green",
    "savings":         "bold yellow",
    "coupon.ok":       "bold green",
    "coupon.fail":     "bold red",
    "cart.header":     "bold cyan",
    "error":           "bold red",
    "muted":           "dim white",
})

_console: Console | None = None


def setup_logger() -> Console:
    """Configure global Rich console + Python logging. Call once at startup."""
    global _console
    _console = Console(theme=_THEME, highlight=False)

    logging.basicConfig(
        level=getattr(logging, APP.log_level, logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=_console, rich_tracebacks=True, markup=True)],
        force=True,
    )
    return _console


def get_logger(name: str) -> logging.Logger:
    """Standard Python logger backed by Rich — used by low-level modules."""
    if _console is None:
        setup_logger()
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _con() -> Console:
    if _console is None:
        setup_logger()
    return _console  # type: ignore[return-value]


def _pause() -> None:
    if APP.demo_mode:
        time.sleep(0.3)


# ---------------------------------------------------------------------------
# Public demo-narration helpers
# ---------------------------------------------------------------------------

def log_agent_thinking(agent_name: str, message: str) -> None:
    """Show the agent's reasoning in a blue panel."""
    _con().print(Panel(
        f"[white]{message}[/white]",
        title=f"[agent.name]🧠  {agent_name}[/agent.name]",
        border_style="blue",
        padding=(0, 1),
    ))
    _pause()


def log_agent_action(agent_name: str, action: str) -> None:
    """Show what the agent is actively doing — inline, no panel."""
    _con().print(f"  [agent.action]▶  {agent_name}:[/agent.action]  [white]{action}[/white]")
    _pause()


def log_deal_found(product: str, deal: str, savings: str) -> None:
    """Highlighted deal alert — stands out visually during the demo."""
    _con().print(Panel(
        f"[white]{product}[/white]\n"
        f"[bold white]{deal}[/bold white]  "
        f"[savings]→ saving {savings}![/savings]",
        title="[deal]💰  DEAL FOUND[/deal]",
        border_style="green",
        padding=(0, 1),
    ))
    _pause()


def log_coupon_result(code: str, success: bool) -> None:
    """Coupon attempt result — green tick or red cross."""
    if success:
        _con().print(
            f"  [coupon.ok]✓  Coupon [bold]{code}[/bold] applied — discount reflected in cart![/coupon.ok]"
        )
    else:
        _con().print(
            f"  [coupon.fail]✗  Coupon [bold]{code}[/bold] was not accepted by the store.[/coupon.fail]"
        )
    _pause()


def log_cart_summary(cart_summary) -> None:
    """Render the final cart as a Rich table, then show totals."""
    c = _con()
    cart = cart_summary.cart

    c.print(Rule("[cart.header]  SmartCart — Ready for Your Approval  [/cart.header]", style="cyan"))

    # Items table
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold white on dark_blue",
        expand=True,
        padding=(0, 1),
    )
    table.add_column("Product",    style="white",      ratio=5)
    table.add_column("Qty",        justify="center",   style="cyan",        ratio=1)
    table.add_column("Unit Price", justify="right",    style="yellow",      ratio=2)
    table.add_column("Deal",       style="green",      ratio=3)
    table.add_column("Line Total", justify="right",    style="bold white",  ratio=2)

    for item in cart.items:
        p = item.product
        name = p.product_name[:52] + ("…" if len(p.product_name) > 52 else "")
        table.add_row(
            name,
            str(item.quantity_added),
            f"${p.price:.2f}",
            p.deal_applied or "[muted]—[/muted]",
            f"${item.line_total:.2f}",
        )

    c.print(table)

    # Coupons
    if cart.coupons_succeeded:
        c.print("[coupon.ok]✓  Coupons applied:[/coupon.ok]")
        for coupon in cart.coupons_succeeded:
            c.print(f"   [green]{coupon.coupon_code}[/green] — {coupon.discount_value}")
    elif cart.coupons_attempted:
        c.print("[yellow]⚠  No coupons were accepted by the store.[/yellow]")

    # Totals panel
    lines = [f"[white]Subtotal:[/white]              [white]${cart.subtotal:.2f}[/white]"]
    if cart.discounts_applied:
        lines.append(
            f"[green]Coupon savings:[/green]        [green]-${cart.discounts_applied:.2f}[/green]"
        )
    if cart_summary.total_savings:
        lines.append(
            f"[savings]Total saved:[/savings]           [savings]${cart_summary.total_savings:.2f}[/savings]"
        )
    lines.append(
        f"[cart.header]Estimated total:[/cart.header]       [cart.header]${cart.estimated_total:.2f}[/cart.header]"
    )
    c.print(Panel("\n".join(lines), title="[bold]Totals[/bold]", box=box.ROUNDED, border_style="cyan"))

    c.print(
        "\n[bold yellow]⏸  Awaiting your approval before checkout.[/bold yellow]  "
        "Review the cart above and confirm to proceed.\n"
    )
    _pause()


def log_error(message: str) -> None:
    """Log an error in red."""
    _con().print(f"  [error]✗  {message}[/error]")
    _pause()
