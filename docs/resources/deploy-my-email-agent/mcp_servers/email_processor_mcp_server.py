import os, sys
from agents.mcp import MCPServerSse  # type: ignore
from fastmcp import FastMCP  # type: ignore
from types import MethodType
from email import policy
from email.parser import BytesParser
from email.header import decode_header, make_header
from html.parser import HTMLParser
from pathlib import Path
import asyncio

PORT = 9001

email_processor_server = MCPServerSse(
    params={
        "url": f"http://localhost:{PORT}/sse",
        "timeout": 8,
        "sse_read_timeout": 100,
    },
    cache_tools_list=True,
    client_session_timeout_seconds=120,
    name="email-processor-mcp",
)

mcp = FastMCP(
    name="email-processor-mcp",
    version="0.2.0",
    description="This MCP allows to get all links from an email file path.",
)

@mcp.tool()
def get_eml_email_subject(eml_path: str | Path) -> str:
    eml_path = Path(eml_path).expanduser().resolve(strict=True)
    with eml_path.open("rb") as fp:
        msg = BytesParser(policy=policy.default).parse(fp)
    raw_subj = msg["Subject"]
    if raw_subj is None:
        return ""
    decoded_subject = str(make_header(decode_header(raw_subj)))
    return decoded_subject

class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
    def handle_data(self, data):
        self.parts.append(data)
    def get_text(self) -> str:
        return "".join(self.parts).strip()

@mcp.tool()
def extract_email_body_from_eml(eml_path: str | Path, *, prefer_html: bool = False) -> str:
    eml_path = Path(eml_path).expanduser().resolve(strict=True)
    with eml_path.open("rb") as fp:
        msg = BytesParser(policy=policy.default).parse(fp)
    plain_parts: list[str] = []
    html_parts: list[str] = []
    if msg.get_content_maintype() == "text" and not msg.is_multipart():
        return msg.get_content()
    for part in msg.walk():
        ctype = part.get_content_type()
        disp = part.get_content_disposition()
        if disp == "attachment":
            continue
        if ctype == "text/plain":
            plain_parts.append(part.get_content())
        elif ctype == "text/html":
            html_parts.append(part.get_content())
    if plain_parts and not prefer_html:
        return "\n\n".join(plain_parts).strip()
    if html_parts:
        stripper = _HTMLStripper()
        for html in html_parts:
            stripper.feed(html)
        return stripper.get_text()
    return ""

def main():
    loop = asyncio.get_event_loop()
    return loop.create_task(
        mcp.run_sse_async(host="127.0.0.1", port=PORT, log_level="debug")
    ) 