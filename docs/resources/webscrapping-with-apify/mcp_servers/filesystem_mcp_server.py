import os
import sys
from pathlib import Path
from agents.mcp import MCPServerStdio  # type: ignore

MOUNT_DIR = Path("data")
MOUNT_DIR.mkdir(exist_ok=True)

NODE_CMD = ["npx", "-y", "@modelcontextprotocol/server-filesystem", str(MOUNT_DIR)]

fs_server = MCPServerStdio(
    params={"command": NODE_CMD[0], "args": NODE_CMD[1:], "timeout": 8, "sse_read_timeout": 60},
    cache_tools_list=True,
    name="filesystem-mcp-server",
) 