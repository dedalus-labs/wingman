"""CLI entry point for wingman.

Parses arguments and launches either headless mode or the interactive TUI.

"""

from .config import APP_VERSION


def main() -> None:
    """Entry point for the ``wingman`` command."""
    import argparse
    import sys

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(
        prog="wingman",
        description="Wingman - AI coding assistant for the terminal",
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {APP_VERSION}")
    parser.add_argument(
        "-p",
        "--print",
        dest="prompt",
        metavar="PROMPT",
        help="Run in headless mode with the given prompt (non-interactive)",
    )
    parser.add_argument("-m", "--model", help="Model to use (e.g., anthropic/claude-sonnet-4-20250514)")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output in headless mode")
    parser.add_argument("--allowed-tools", help="Comma-separated list of allowed tools")
    parser.add_argument("-C", "--working-dir", help="Working directory for file operations")

    args = parser.parse_args()

    if args.prompt:
        import asyncio
        from pathlib import Path

        from .headless import run_headless

        working_dir = Path(args.working_dir) if args.working_dir else None
        allowed_tools = args.allowed_tools.split(",") if args.allowed_tools else None

        exit_code = asyncio.run(
            run_headless(
                prompt=args.prompt,
                model=args.model,
                working_dir=working_dir,
                allowed_tools=allowed_tools,
                verbose=args.verbose,
            )
        )
        sys.exit(exit_code)

    from .app import WingmanApp

    app = WingmanApp()
    app.run()


if __name__ == "__main__":
    main()
