"""Welcome screen ASCII art."""

from ..config import APP_CREDIT, APP_NAME, APP_VERSION

WELCOME_ART = """[#7aa2f7]
██╗    ██╗██╗███╗   ██╗ ██████╗ ███╗   ███╗ █████╗ ███╗   ██╗
██║    ██║██║████╗  ██║██╔════╝ ████╗ ████║██╔══██╗████╗  ██║
██║ █╗ ██║██║██╔██╗ ██║██║  ███╗██╔████╔██║███████║██╔██╗ ██║
██║███╗██║██║██║╚██╗██║██║   ██║██║╚██╔╝██║██╔══██║██║╚██╗██║
╚███╔███╔╝██║██║ ╚████║╚██████╔╝██║ ╚═╝ ██║██║  ██║██║ ╚████║
 ╚══╝╚══╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝[/]
"""

WELCOME_ART_COMPACT = """[bold #7aa2f7]Wingman[/]"""


def get_welcome_text(compact: bool = False) -> str:
    """Get welcome screen text."""
    art = WELCOME_ART_COMPACT if compact else WELCOME_ART
    return f"""{art}
[dim]v{APP_VERSION} · {APP_CREDIT}[/]

[#565f89]Type to chat · [bold #7aa2f7]/[/] for commands · [bold #7aa2f7]Ctrl+S[/] for sessions[/]"""
