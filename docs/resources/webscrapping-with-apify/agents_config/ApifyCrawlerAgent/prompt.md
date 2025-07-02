# ApifyCrawlerAgent Prompt

You have two toolboxes:
1. `apify-mcp-server` – lets you run Apify actors (web scrapers, crawlers,…).
2. `filesystem-mcp-server` – gives you read/write access to the local `data/` directory.

Task: autonomously create a file `data/yahoo_summary.txt` that contains a short
paragraph for each of the **top 5 most-active stocks** on https://finance.yahoo.com.
Each paragraph should include the ticker symbol and a one-line description of the
company's business.

Plan template:
* Use an Apify actor (e.g. `apify/web-scraper`) to fetch the main page and
  extract the ticker symbols.
* For each ticker, scrape its Yahoo Finance page and extract the *Company
  Profile* paragraph.
* Append a summary line to `data/yahoo_summary.txt` in the format:
  `AAPL – Designs and sells consumer electronics.`
* After all five tickers are processed set `plan_completion_percentage` to 100.0
  and return a confirmation message.

Output JSON must match `ApifyCrawlerAgentResponse` schema (see docstring). 