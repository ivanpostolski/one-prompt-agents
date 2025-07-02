# Mongo-DB Agent Resource

This resource demonstrates how to plug a MongoDB database into an interactive
agent via the Model Context Protocol (MCP).

Contents
--------
* `mcp_servers/card_db_mcp_server.py` – exposes CRUD tools for the `cards`
  collection (port 9003).
* `agents_config/MongoDBAgent/` – agent config with an **empty prompt** so you
  can experiment live.
* `requirements.txt` – runtime deps (`pymongo`, `one-prompt-agents`).

Prerequisites
-------------
1. Create a free MongoDB Atlas cluster (or use an existing deployment).
2. Generate **Database Access credentials** (username:password pair).
3. Allow your IP address to connect – Atlas → Network Access → *Add IP Address*.
   See <https://www.mongodb.com/docs/atlas/security/add-ip-address/>.
4. Build the `MONGO_KEYS` variable as `username:password` and export it:
   ```bash
   export MONGO_KEYS="agentUser:agentPass"
   ```
   (The MCP server derives the full URI from this string.)

Setup & quick test
------------------
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# start the MongoDB MCP
python mcp_servers/card_db_mcp_server.py &

# interactive chat
run_agent MongoDBAgent
```

Suggested session
-----------------
```
What tools do you have?

Create a new card named "Charizard" PSA 9 with data {"set": "Base", "year": 1999}.

Search for Charizard.

Update Charizard adding alt_names ["Lizardon"].
```

Happy hacking! 🎉 