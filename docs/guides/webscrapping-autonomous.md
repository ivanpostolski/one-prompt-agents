# Web-Scraping with Apify – Autonomous Guide

This guide extends the interactive project by adding **ApifyCrawlerAgent** which
crawls Yahoo Finance autonomously, writes summaries to a local file, and returns
a structured plan.

---

## 1  Start both MCP servers

```bash
# Apify cloud
python mcp_servers/apify_mcp_server.py &

# Local filesystem (creates data/ directory)
python mcp_servers/filesystem_mcp_server.py &
```

Make sure `APIFY_TOKEN` is exported beforehand.

---

## 2  Run the autonomous agent

```bash
export OPENAI_API_KEY="sk-…"

run_agent ApifyCrawlerAgent "Summarise top movers"
```

The agent should:

1. Fetch the list of **top 5 most active** tickers from Yahoo Finance.
2. Scrape each individual ticker page to extract the Company Profile snippet.
3. Write the results to `data/yahoo_summary.txt`.

---

## 3  Monitor progress

While running you can tail the output file:

```bash
tail -f data/yahoo_summary.txt | cat
```

Check the traces:

```
autonomous-chat-ApifyCrawlerAgent-<JobID>
```

in https://platform.openai.com/traces to inspect every Apify actor invocation.

---

## 4  Try start_and_wait orchestration

Using techniques from the *StartAndWait* guide you could create another agent
that deletes the file and blocks until ApifyCrawlerAgent finishes.

Happy crawling! 🎉 