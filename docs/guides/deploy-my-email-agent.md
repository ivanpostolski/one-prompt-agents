# Deploy-My-Email-Agent Guide

> 🚧 Deployment instructions will be added here – follow your
> `https://emailagents.team` onboarding docs for now.

---

## Quick functional test

Once deployed, try the full round-trip:

1. Compose a new email **to your agent address** (provided by the platform).
2. Subject: `tools`
3. Body:
   ```
   Please send me an email listing your available tools.
   ```

What happens behind the scenes:

1. The platform saves the `.eml` file and triggers **EmailProcessorAgent** with the file path.
2. EmailProcessorAgent extracts subject/body, then starts **EmptyAgent** asynchronously via the `start_agent_EmptyAgent` tool.
3. EmptyAgent calls `user-email-send-mcp.send_email`, composing a message that lists its available tools (you should see at least `send_email`).
4. You receive the reply in your inbox – success! 🎉

If nothing arrives, check:
* Both MCP servers are running (`email_processor_mcp_server.py` on 9001 and `email_sender_mcp_server.py` on 9002).
* Environment variables `AWS_REGION`, `USER_EMAIL`, `/etc/agent_email` are set correctly.
* Traces for `autonomous-chat-EmailProcessorAgent-…` and `autonomous-chat-EmptyAgent-…` in the OpenAI dashboard. 