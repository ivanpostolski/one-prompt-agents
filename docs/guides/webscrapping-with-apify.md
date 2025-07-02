# Web-Scraping with Apify – Interactive Guide

This guide walks you through running **ApifyScraperAgent**, an interactive agent
that controls Apify actors via the Model Context Protocol (MCP).

---

## 1  Prerequisites

* Python 3.11 environment with `one-prompt-agents` installed.
* An Apify API token.

Get your token from https://console.apify.com/account/integrations and export
it once:

```bash
export APIFY_TOKEN="apify_…"
```

---

## 2  Start the Apify MCP server

```bash
python mcp_servers/apify_mcp_server.py &   # keep this running
```

The script will:

* Connect to Apify's cloud SSE endpoint.
* Remove a few demo actors we don't need.
* Register itself under the tool name **apify-mcp-server**.

---

## 3  Inspect the agent config

```json title="agents_config/ApifyScraperAgent/config.json"
{
  "name": "ApifyScraperAgent",
  "prompt_file": "prompt.md",
  "return_type": "ApifyScraperAgentResponse",
  "inputs_description": "Interactive agent to run Apify actors.",
  "tools": ["apify-mcp-server"],
  "model": "o4_mini"
}
```

Note the empty `prompt.md` – perfect for quick iterative exploration.

---

## 4  Talk to the agent

```bash
run_agent ApifyScraperAgent
```

Suggested session:

```
What tools do you have?

Use the generic web-scraper to fetch the title of https://finance.yahoo.com and return it.
```

Behind the scenes the agent will choose an Apify actor (e.g.
`apify/web-scraper`) and stream its output back to you.

---

## 5  Next steps

* Try different actors – list them with `What tools do you have?`.
* Chain the filesystem tool from previous guides to store scraped data locally.

Happy scraping! 🎉 