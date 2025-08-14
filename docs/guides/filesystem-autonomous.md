---
title: Filesystem Autonomous
order: 3
caption: Run an autonomous agent to summarise files and keep a server alive.
requirements:
  - Python 3.11
  - OpenAI API key
  - Filesystem MCP server running
supademo: https://app.supademo.com/d/filesystem-autonomous-placeholder
---
# Filesystem Agent – Autonomous Guide

This guide shows how to run **AutoFilesystemAgent** which reads every file it
can access, writes one-line summaries to `files_summary.txt` and keeps the HTTP
server alive for further tasks.

---

## 1  Prerequisites

1. Follow the *Interactive* guide to start the filesystem MCP server:
   ```bash
   python mcp_servers/filesystem_mcp_server.py &   # keep this running
   ```
2. Create a few sample files inside the mounted `data/` directory:
   ```bash
   mkdir -p data
   echo "Apples are red."         > data/fruits.txt
   echo "Dogs are loyal mammals." > data/animals.txt
   echo "Mars is the 4th planet." > data/planets.txt
   ```
3. Export your OpenAI key:
   ```bash
   export OPENAI_API_KEY="sk-…"
   ```

---

## 2  Run the autonomous agent

```bash
run_agent AutoFilesystemAgent "Summarise every file you can access"
```

What happens:

1. The agent plans one step per file, reads the file and appends a summary to
   `data/files_summary.txt`.
2. When all steps are finished the CLI **automatically starts** an HTTP server
   on `http://127.0.0.1:9000`.

---

## 3  Monitor the run

The recommended way to monitor the agent execution is the OpenAI Trace Logs. Essentially because one prompt agents are designed to run autonomously on the cloud (triggering them using emails).  

There is easy to follow which tools were used by an agent, the plan that an agent creates for it's execution and the interaction with other agents.  
 
Autonomous runs receive a different trace ID pattern:

```
autonomous-chat-<AgentName>-<JobID>
# example: autonomous-chat-AutoFilesystemAgent-8923b34c
```

Follow the same steps:
1. Open https://platform.openai.com/traces
2. Search for `AutoFilesystemAgent`.
3. Open the trace to inspect each step, tool invocation and model output.

Comparing traces from interactive (`User-Chat-…`) and autonomous runs is a
quick way to verify that the agent executed your plan exactly as intended.


---

## 4  Send additional tasks via HTTP

Because the server is still running you can keep asking for more work.  For
example, append summaries of all Markdown files:

```bash
curl -X POST "http://127.0.0.1:9000/agents/AutoFilesystemAgent" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Append a summary for all .md files."}'
```

When you are finished, shut down the server:

```bash
shutdown_server
```

---

Happy hacking! 🎉 