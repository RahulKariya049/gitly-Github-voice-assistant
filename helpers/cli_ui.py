from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from typing import List, Tuple, Optional
from time import sleep
import os
console = Console()

def animate(message: str, delay: float = 0.03):
    """Simulate a typing effect for visual feedback."""
    for char in message:
        print(char, end='', flush=True)
        sleep(delay)
    print()  # move to next line after animation


def show_banner():
    """Displays the welcome banner at Gitly startup."""
    console.print(Panel.fit(
        "[bold magenta] Welcome to Gitly CLI Assistant \nYour personal Git helper!",
        title="Gitly",
        subtitle="v1.0",
        border_style="magenta"
    ))


def log_step(message: str):
    """Logs a standard processing step."""
    console.print(f"[bold blue]→ {message}[/bold blue]")


def log_success(message: str):
    """Logs a successful step or confirmation."""
    console.print(f"[bold green]✓ {message}[/bold green]")


def log_warning(message: str):
    """Logs a warning during processing."""
    console.print(f"[bold yellow]⚠ {message}[/bold yellow]")


def log_error(message: str):
    """Logs a critical error or failure."""
    console.print(f"[bold red]✖ {message}[/bold red]")


def live_waiting_feedback(initial_msg: str = "Listening for user...", final_msg: Optional[str] = None):
    """Shows a dynamic loading line while Gitly waits for something (e.g., STT response)."""
    with Live(Text(f"→ {initial_msg}"), refresh_per_second=4) as live:
        sleep(2.5)  # Simulation; you can remove or adjust dynamically
        if final_msg:
            live.update(Text(f"✓ {final_msg}", style="bold green"))


def log_file_status(file_status_list: List[Tuple[str, str]]):
    """Log file status like git status summary using plain rows."""
    console.print("\n[bold magenta]📊 Git Status Summary:[/bold magenta]")
    for file, status in file_status_list:
        console.print(f" • [cyan]{file}[/cyan] → [yellow]{status}[/yellow]")



def show_final_plan(intent: str, files: list = None, msg: str = None, repo: str = None, branch : str = None):
    """Displays the final interpreted command plan before execution."""
    console.print("\n[bold magenta]📊 Final Plan:[/bold magenta]")
    if intent:
        console.print(f"• Intent: [bold blue]{intent}[/bold blue]")
    if files:
        console.print(f"• Files: [bold green]{files}[/bold green]")
    if msg:
        console.print(f"• Message: [yellow]{msg}[/yellow]")
    if repo:
        console.print(f"• Repo: [cyan]{repo}[/cyan]")
    if branch:
        console.print(f"• Target Branch: [cyan]{branch}[/cyan]")


def show_info(message: str):
    """Generic Gitly info message."""
    console.print(f"[bold cyan][Gitly][/bold cyan] {message}")


def show_success(message: str):
    """Generic Gitly success message."""
    console.print(f"[bold green][Success][/bold green] {message}")

def clear_screen():
    pass