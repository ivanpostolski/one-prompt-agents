#!/usr/bin/env python3
"""Main entry point for the One-Prompt Agents application.

This script used to contain the core application logic. After refactoring,
it now serves as a minimal wrapper that simply imports and calls the main
command-line interface function (`main_cli`) from the `cli.py` module.
This maintains the original entry point (`python -m src.one_prompt_agents.main`)
while centralizing the primary logic in `cli.py`.

To ensure compatibility with entry points expecting a `main` function (e.g.,
from pyproject.toml scripts), `main_cli` is also aliased as `main` here.
"""

from one_prompt_agents.cli import main_cli

main = main_cli # Alias main_cli as main for external script compatibility

if __name__ == "__main__":
    main_cli() # Or just main(), since they are the same now