# Filesystem Agent – Interactive Guide

This guide builds upon *Getting Started* and demonstrates how to attach a **local file-system** tool to an agent so you can explore it **interactively**.

---

## 1  Requirements

* Everything from the first guide (Python 3.11, `one-prompt-agents`, …)
* **Node.js ≥ 18** – `npx` is used to run the filesystem tool implementation.

---

## 2  Start the filesystem MCP server

Inside the *getting-started* folder run:

```bash
python mcp_servers/filesystem_mcp_server.py &   # keep this process running
```

This creates a `data/` directory and spawns `npx -y @modelcontextprotocol/server-filesystem data` so that file-system operations become available under the MCP name `filesystem-mcp-server`.

---

## 3  Inspect the FilesystemAgent config

```json title="agents_config/FilesystemAgent/config.json"
{
  "name": "FilesystemAgent",
  "prompt_file": "prompt.md",
  "return_type": "FilesystemAgentResponse",
  "inputs_description": "Agent that demonstrates access to local filesystem via MCP server.",
  "tools": ["filesystem-mcp-server"],
  "model": "gpt-4o-mini"
}
```

The prompt is intentionally **empty** – we will discover the capabilities through conversation.

---

## 4  Talk to the agent

Open another terminal in the same folder:

```bash
run_agent FilesystemAgent
```

Try asking:

```
What tools do you have?

List the files in the root directory.

Create a new file named hello.txt containing "Hello world" and then list the directory again.
```

Watch the `data/` directory change in real time.

## 6  View your traces in the OpenAI dashboard

Every agent turn is automatically wrapped in a trace that you can inspect in
the *OpenAI Platform → Traces* tab.

For interactive runs the trace IDs are built like:

```
User-Chat-<AgentName>  # example: User-Chat-FilesystemAgent_interactive
```

Steps:

1. Go to https://platform.openai.com/traces
2. Use the search bar to look for `FilesystemAgent_interactive` (or any part of
   the workflow-id).
3. Click on the trace to see every tool call and LLM completion in detail.

This is invaluable while developing prompts or debugging unexpected behaviour. 

## 7  Where to go next

* Proceed to the *Filesystem Autonomous* guide to see how to let an agent summarise files on its own.
* Modify the MCP server script to mount a different directory or expose read-only access.

Happy hacking! 🎉 