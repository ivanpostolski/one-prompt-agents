import os
import sys
from agents.mcp import MCPServerSse  # type: ignore
from types import MethodType

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
if not APIFY_TOKEN:
    sys.exit("❌  export APIFY_TOKEN first")

apify_server = MCPServerSse(
    params={
        "url": "https://actors-mcp-server.apify.actor/sse?enableAddingActors=true",
        "headers": {
            "Authorization": f"Bearer {APIFY_TOKEN}",
        },
        "timeout": 180,
        "sse_read_timeout": 300,
    },
    client_session_timeout_seconds=60,
    cache_tools_list=True,
    name="apify-mcp-server",
)

# ---- Remove default actors we don't need ----
_original_connect = apify_server.connect
async def _wrapped_connect(self, *args, **kwargs):  # noqa: D401
    result = await _original_connect(*args, **kwargs)
    # Customize the configuration of the apify actor (if needed)
    return result

apify_server.connect = MethodType(_wrapped_connect, apify_server) 