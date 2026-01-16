"""Output formatting for Substack Friend Finder."""

from __future__ import annotations

from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .types import Match

console = Console()


def truncate(text: str, max_length: int = 100) -> str:
    """Truncate text with ellipsis if too long."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def print_header(username: str) -> None:
    """Print the header for the results."""
    console.print()
    console.print(Panel(
        f"[bold blue]Substack Friend Finder[/bold blue]\n"
        f"Finding matches for: [green]@{username}[/green]",
        expand=False,
    ))
    console.print()


def print_progress(message: str) -> None:
    """Print a progress message."""
    console.print(f"[dim]{message}[/dim]")


def print_matches(matches: List[Match], limit: int = 20) -> None:
    """Print the ranked matches."""
    if not matches:
        console.print("[yellow]No matches found.[/yellow]")
        return

    console.print(f"\n[bold green]Found {len(matches)} matches![/bold green]\n")

    for i, match in enumerate(matches[:limit], 1):
        # Build the match display
        user = match.user

        # Header with rank and score
        header = f"#{i} [bold]{user.name or user.username}[/bold]"
        if user.username:
            header += f" (@{user.username})"

        # Score and badges
        badges = []
        if user.has_publication:
            badges.append("[cyan]Writer[/cyan]")
        if user.bio:
            badges.append("[green]Bio[/green]")

        score_text = f"Score: [bold yellow]{match.score:.2f}[/bold yellow]"
        if badges:
            score_text += " | " + " ".join(badges)

        # Shared newsletters
        shared_text = "[dim]Shared:[/dim] "
        shared_names = [n.name for n in match.shared_newsletters[:5]]
        shared_text += ", ".join(shared_names)
        if len(match.shared_newsletters) > 5:
            shared_text += f" [dim](+{len(match.shared_newsletters) - 5} more)[/dim]"

        # Bio snippet
        bio_text = ""
        if user.bio:
            bio_text = f"\n[dim]{truncate(user.bio, 120)}[/dim]"

        # Profile URL
        profile_url = f"https://substack.com/@{user.username}" if user.username else ""

        # Publication URL
        pub_text = ""
        if user.publication_url:
            pub_text = f"\n[blue]Publication:[/blue] {user.publication_url}"

        content = f"{score_text}\n{shared_text}{bio_text}{pub_text}"
        if profile_url:
            content += f"\n[blue]Profile:[/blue] {profile_url}"

        console.print(Panel(
            content,
            title=header,
            title_align="left",
            border_style="blue" if user.has_publication else "white",
            expand=False,
        ))
        console.print()


def print_summary(
    input_username: str,
    num_subscriptions: int,
    num_newsletters_scanned: int,
    num_candidates: int,
    num_matches: int,
) -> None:
    """Print a summary of the search."""
    table = Table(title="Search Summary", show_header=False)
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bold")

    table.add_row("Input user", f"@{input_username}")
    table.add_row("User's subscriptions", str(num_subscriptions))
    table.add_row("Newsletters scanned", str(num_newsletters_scanned))
    table.add_row("Candidates found", str(num_candidates))
    table.add_row("Matches after filtering", str(num_matches))

    console.print(table)
    console.print()


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold red]Error:[/bold red] {message}")
