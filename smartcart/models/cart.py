"""
Pydantic models for the final cart state presented to the user for approval.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator
import io

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from models.product import SelectedProduct
from models.coupon import Coupon


class CartItem(BaseModel):
    model_config = {"from_attributes": True}

    product: SelectedProduct
    quantity_added: int
    coupon_applied: Coupon | None = None
    line_total: float

    @model_validator(mode="after")
    def set_line_total_default(self) -> CartItem:
        if self.line_total == 0.0:
            self.line_total = self.product.price * self.quantity_added
        return self


class Cart(BaseModel):
    model_config = {"from_attributes": True}

    items: list[CartItem] = []
    subtotal: float = 0.0
    discounts_applied: float = 0.0
    estimated_total: float = 0.0
    coupons_attempted: list[Coupon] = []
    coupons_succeeded: list[Coupon] = []

    @model_validator(mode="after")
    def compute_totals(self) -> Cart:
        if self.subtotal == 0.0 and self.items:
            self.subtotal = sum(i.line_total for i in self.items)
        if self.estimated_total == 0.0:
            self.estimated_total = max(0.0, self.subtotal - self.discounts_applied)
        return self


class CartSummary(BaseModel):
    model_config = {"from_attributes": True}

    cart: Cart
    total_savings: float = 0.0
    summary_text: str = ""

    @model_validator(mode="after")
    def compute_savings(self) -> CartSummary:
        if self.total_savings == 0.0:
            savings_from_deals = sum(
                i.product.estimated_savings * i.quantity_added for i in self.cart.items
            )
            self.total_savings = savings_from_deals + self.cart.discounts_applied
        return self

    def display(self) -> str:
        """Return a Rich-formatted string suitable for printing to the console."""
        buf = io.StringIO()
        console = Console(file=buf, width=88)

        # --- Items table ---
        table = Table(
            title="[bold cyan]SmartCart — Order Summary[/bold cyan]",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold white",
            expand=True,
        )
        table.add_column("Product", style="white", ratio=4)
        table.add_column("Qty", justify="center", style="cyan", ratio=1)
        table.add_column("Unit Price", justify="right", style="yellow", ratio=2)
        table.add_column("Deal", style="green", ratio=2)
        table.add_column("Line Total", justify="right", style="bold white", ratio=2)

        for item in self.cart.items:
            p = item.product
            table.add_row(
                p.product_name[:55] + ("…" if len(p.product_name) > 55 else ""),
                str(item.quantity_added),
                f"${p.price:.2f}",
                p.deal_applied or "—",
                f"${item.line_total:.2f}",
            )

        console.print(table)

        # --- Coupon rows ---
        if self.cart.coupons_succeeded:
            console.print("[bold green]✓ Coupons applied:[/bold green]")
            for c in self.cart.coupons_succeeded:
                console.print(f"  [green]{c.coupon_code}[/green] — {c.discount_value}")
        if self.cart.coupons_attempted and not self.cart.coupons_succeeded:
            console.print("[yellow]⚠  No coupons were accepted by the store.[/yellow]")

        # --- Totals panel ---
        lines = [
            f"[white]Subtotal:[/white]              [white]${self.cart.subtotal:.2f}[/white]",
        ]
        if self.cart.discounts_applied:
            lines.append(
                f"[green]Coupon savings:[/green]        [green]-${self.cart.discounts_applied:.2f}[/green]"
            )
        if self.total_savings:
            lines.append(
                f"[bold green]Total saved:[/bold green]           [bold green]${self.total_savings:.2f}[/bold green]"
            )
        lines.append(
            f"[bold cyan]Estimated total:[/bold cyan]       [bold cyan]${self.cart.estimated_total:.2f}[/bold cyan]"
        )
        console.print(Panel("\n".join(lines), title="[bold]Totals[/bold]", box=box.ROUNDED))

        # --- Approval prompt ---
        console.print(
            "\n[bold yellow]⏸  Awaiting your approval before checkout.[/bold yellow]  "
            "Review the cart above and confirm to proceed.\n"
        )

        return buf.getvalue()
