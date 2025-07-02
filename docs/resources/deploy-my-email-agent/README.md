# Deploy-My-Email-Agent Resource

This resource contains two agents plus the required MCP servers for a minimal
email processing pipeline:

1. **EmailProcessorAgent** – interactive/orchestration agent that:
   * Uses `email-processor-mcp` to extract subject & body from a `.eml` file.
   * Starts **EmptyAgent** asynchronously and passes along the extracted
     information.

2. **EmptyAgent** – receives subject/body and can use
   `user-email-send-mcp` to forward the message to you via AWS SES.

MCP Servers included:
* `email_processor_mcp_server.py` runs on port 9001.
* `email_sender_mcp_server.py` runs on port 9002.

Prerequisites
-------------
1. Subscribe to a plan at <https://emailagents.team> and get your **deployment
   key** plus onboarding instructions – **do this first**.
2. Python 3.11 virtual-env with `pip install -r requirements.txt`.
3. Environment variables:
   * `OPENAI_API_KEY` – your OpenAI key.
   * `APIFY_TOKEN` – (if you want to add the Apify agent later).
   * `AWS_REGION`, `USER_EMAIL` and `/etc/agent_email` file holding SOURCE email
     (see email sender MCP for details).

Quick start
-----------
```bash
# 1. install deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. set env vars (adapt to your values)
export OPENAI_API_KEY="sk-..."
export AWS_REGION="us-east-1"
export USER_EMAIL="me@example.com"

# 3. start MCP servers in background shells
python mcp_servers/email_processor_mcp_server.py &
python mcp_servers/email_sender_mcp_server.py   &

# 4. run the orchestrator
run_agent EmailProcessorAgent "Process /path/to/new_message.eml"
```

Files
-----
```
agents_config/
    EmailProcessorAgent/
        config.json
        prompt.md
        return_type.py
    EmptyAgent/
        config.json
        prompt.md
        return_type.py
mcp_servers/
    email_processor_mcp_server.py
    email_sender_mcp_server.py
```

Enjoy hacking and remember to replace the `.eml` path with a real email file! 🎉 