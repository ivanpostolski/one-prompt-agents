# MongoDB Agent – Interactive Guide

This guide shows how to spin up **MongoDBAgent** – an interactive agent that
manages a simple Trading Card Game (TCG) collection stored in MongoDB.

---

## 1  Prepare MongoDB Atlas

1. Sign in / create an account at <https://cloud.mongodb.com>.
2. Create a free **Shared Cluster**.
3. In *Database Access* create a user → keep the *Username* and *Password*.
4. In *Network Access* add your current IP address to the allow-list.
   Reference: <https://www.mongodb.com/docs/atlas/security/add-ip-address/>.
5. Export your credentials as one string:
   ```bash
   export MONGO_KEYS="<username>:<password>"
   ```
   The MCP server will build the full `mongodb+srv://…` URI from this.

---

## 2  Install & start the MCP server

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python mcp_servers/card_db_mcp_server.py &   # port 9003
```

---

## 3  Chat with the agent

```bash
export OPENAI_API_KEY="sk-…"

run_agent MongoDBAgent
```

Suggested prompts:

```
What tools do you have?

# insert
Call update_card to create Charizard with psa_grade 9 and data {"set": "Base", "year": 1999}

# search
Search for Charizard.

# update alt names
Update Charizard adding alt_names ["Lizardon"].
```

Every change is immediately persisted in your Atlas cluster.

---

Happy collecting! 🎉 