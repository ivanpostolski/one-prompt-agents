"""
Collect every `MCPServerSse` instance defined at *module level* in every
file that matches *_mcp_server.py* inside a chosen directory.

* The key of the resulting dict is `srv.name`
* If a module exposes a top-level `main()` function, it is executed
  *after* the instances have been collected (so `main()` can rely on them).
"""

from __future__ import annotations
from pathlib import Path
import importlib.util
import inspect
import sys
from typing import Dict, Type, Any, Tuple, List
from agents.mcp import MCPServerStdio, MCPServerSse


# ── CONFIG ────────────────────────────────────────────────────────────────
SEARCH_DIR      = Path("mcp_servers")                # or Path("services")
MODULE_SUFFIX   = "_mcp_server.py"
TARGET_CLS: Type[Any] = MCPServerSse | MCPServerStdio      # import / define this first
# ──────────────────────────────────────────────────────────────────────────

def import_module_from_path(path: Path):
    """Dynamically imports a Python module from a given file path.

    This utility function is used to load MCP server definition files.

    Args:
        path (Path): The absolute or relative path to the Python file.

    Returns:
        module: The imported module object.
    """
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module        # supports intra-module imports
    spec.loader.exec_module(module)        # run the code
    return module

def collect_servers() -> Tuple[Dict[str, MCPServerSse | MCPServerStdio], List[Any]]:
    """Discovers and collects MCP server instances from specified modules.

    This function scans the `SEARCH_DIR` for Python files ending with `MODULE_SUFFIX`.
    For each matching file, it:
    1. Dynamically imports the module.
    2. Inspects the module for top-level instances of `TARGET_CLS` (MCPServerSse or MCPServerStdio).
       These instances are collected into a dictionary keyed by their `name` attribute.
    3. If the module defines a callable `main()` function, it is executed. Any task returned
       by `main()` (presumably an asyncio.Task for running the server) is collected.

    This allows for a plugin-like architecture where MCP servers can be defined in separate
    files and automatically discovered and loaded.

    Returns:
        Tuple[Dict[str, MCPServerSse | MCPServerStdio], List[Any]]:
            A tuple containing:
            - A dictionary mapping server names to their `MCPServerSse` or `MCPServerStdio` instances.
            - A list of asyncio tasks returned by the `main()` functions of the discovered server modules.
    """
    servers: Dict[str, MCPServerSse | MCPServerStdio] = {}
    tasks_list = []

    for file in SEARCH_DIR.glob(f"*{MODULE_SUFFIX}"):
        mod = import_module_from_path(file)

        # 1️⃣ gather every top-level instance of TARGET_CLS
        for _, obj in inspect.getmembers(mod, lambda x: isinstance(x, TARGET_CLS)):
            servers[obj.name] = obj        # duplicates overwrite silently

        # 2️⃣ call `main()` if present and callable
        main = getattr(mod, "main", None)
        if callable(main):
            try:
                server_task = main()
                tasks_list.append(server_task)                     # you may want to pass *servers* in
            except Exception as exc:       # don't bomb the whole script
                print(f"[WARN] {mod.__name__}.main() raised {exc!r}")

    return servers, tasks_list

# ── USAGE ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    servers_by_name = collect_servers()
    print("Loaded servers:", list(servers_by_name))

    import asyncio
    loop = asyncio.get_event_loop()
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

