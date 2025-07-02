"""
MongoDB helper MCP server for card tracking.
Requires `pymongo`.
"""

import os, sys, re, subprocess, asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from pymongo import MongoClient, ASCENDING, TEXT
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from fastmcp import FastMCP  # type: ignore
from agents.mcp import MCPServerSse  # type: ignore

# ─┐ Environment
MONGO_KEYS = os.getenv("MONGO_KEYS")
if not MONGO_KEYS:
    sys.exit("❌  export MONGO_KEYS first (username:password)")

MONGO_URI = (
    f"mongodb+srv://{MONGO_KEYS}@ebaycloud.ube04or.mongodb.net/?retryWrites=true"
    "&w=majority&appName=ebayCloud"
)
DB_NAME = "tcg"
RETENTION_DAYS = 14
PORT = 9003

client = MongoClient(MONGO_URI, uuidRepresentation="standard")
db = client[DB_NAME]

# ─┐ MCP server
cards_db_processor_server = MCPServerSse(
    params={
        "url": f"http://localhost:{PORT}/sse",
        "timeout": 8,
        "sse_read_timeout": 100,
    },
    cache_tools_list=True,
    client_session_timeout_seconds=120,
    name="card-db-mcp",
)

mcp = FastMCP(
    name="card-db-mcp",
    version="0.2.0",
    description="CRUD helpers for the 'cards' collection.",
)

# ─┐ Helpers

def _col(name: str) -> Collection:
    return db[name]


def _ensure_indexes() -> None:
    cards = _col("cards")
    offers = _col("offers")
    cards.create_index([("name", TEXT), ("alt_names", TEXT)], default_language="none")
    offers.create_index([("link", TEXT)], default_language="none")
    cards.create_index([("name_lc", ASCENDING)], unique=True)
    offers.create_index([("link", ASCENDING)], unique=True)
    offers.create_index([("offer_id", ASCENDING)], unique=True)
    expire = timedelta(days=RETENTION_DAYS)
    cards.create_index("created_at", expireAfterSeconds=expire.total_seconds())
    offers.create_index("created_at", expireAfterSeconds=expire.total_seconds())
    cards.create_index([("psa_grade", ASCENDING)])

_ensure_indexes()

def _now() -> datetime:
    return datetime.utcnow()

def _fts_query(q: str) -> str:
    tokens = re.findall(r"\w+", q.lower())
    return " ".join(tokens)

# ─┐ Tools

@mcp.tool()
def quick_search_cards(q: str, *, limit: int = 10) -> list[dict]:
    cur = _col("cards").find(
        {"$text": {"$search": _fts_query(q)}},
        projection={"_id": False, "name": 1, "psa_grade": 1, "created_at": 1,
                    "data": 1, "score": {"$meta": "textScore"}},
    ).sort([("score", {"$meta": "textScore"})]).limit(limit)
    hits = []
    for doc in cur:
        hits.append({
            "name": doc["name"],
            "psa_grade": doc.get("psa_grade"),
            "created_at": doc["created_at"],
            "data_keys": list(doc["data"].keys())
        })
    return hits

@mcp.tool()
def update_card(name: str, *, psa_grade: int = None, data: dict | None = None) -> str:
    cards = _col("cards")
    name_lc = name.lower()
    now = _now()
    incoming = data.copy() if data else {}
    new_alt = incoming.pop("alt_names", [])
    try:
        cur = cards.find_one({"name_lc": name_lc})
        if cur:
            merged_data = cur.get("data", {}).copy()
            if incoming:
                merged_data.update(incoming)
            merged_alt = list({*(cur.get("alt_names", [])), *new_alt})
            upd = {
                "name": name,
                "created_at": now,
                "data": merged_data,
                "alt_names": merged_alt,
            }
            if psa_grade is not None:
                upd["psa_grade"] = psa_grade
            cards.update_one({"name_lc": name_lc}, {"$set": upd})
        else:
            payload = {
                "name": name,
                "name_lc": name_lc,
                "psa_grade": psa_grade,
                "alt_names": list(new_alt),
                "data": incoming,
                "created_at": now,
            }
            cards.insert_one(payload)
        return "success"
    except PyMongoError as exc:
        return f"error: {exc}"

# run server

def main():
    loop = asyncio.get_event_loop()
    return loop.create_task(mcp.run_sse_async(host="127.0.0.1", port=PORT, log_level="debug")) 