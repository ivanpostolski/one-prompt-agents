# Web-Scraping with Apify – Example Project

This folder contains everything you need to run an **interactive** agent that
controls Apify actors via the Model Context Protocol (MCP).

Prerequisites:

1. `pip install one-prompt-agents`
2. Obtain an **Apify API token** (https://console.apify.com/account/integrations).
3. Export it once in your shell:
   ```bash
   export APIFY_TOKEN="apify_…"
   ```
4. Start the MCP server:
   ```bash
   python mcp_servers/apify_mcp_server.py &
   ```
5. Open a second terminal and chat with the agent:
   ```bash
   run_agent ApifyScraperAgent
   ```

Try asking:

```
What tools do you have?

Use the generic web-scraper to grab the title of https://finance.yahoo.com and return it.
```

Because the prompt is intentionally **empty**, you can iterate quickly and learn
what actors are available or add new ones on the fly. 