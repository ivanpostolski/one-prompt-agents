---
title: Start, Start and wait, Extensible
order: 7
caption: Orchestrate agents using start vs. start_and_wait and extend workflows.
requirements:
  - Python 3.11
  - OpenAI API key
  - Filesystem MCP server running
supademo: https://app.supademo.com/d/start-wait-extensible-placeholder
---
# Orchestrating Agents with `start_and_wait` – Guide

This guide introduces **StartAndWaitAgent**, an autonomous agent that orchestrates
another agent (AutoFilesystemAgent) via the special `_start_and_wait` tool.  You
will learn how the job queue works and how one agent can block until another
finishes.

---

## 1  Background: start vs. start_and_wait

Every MCP agent exposes two helper tools (see framework code in
`one_prompt_agents/mcp_agent.py`):

* `start_agent_<Target>` – fire-and-forget.  Returns immediately after enqueueing
  a job for `<Target>`.
* `_start_and_wait_<Target>` – submits a job *and* makes the **calling** agent's
  current job wait until the spawned job is done.  This is implemented by adding
  a dependency in the job queue.

The worker only picks up a job when *all* its dependencies are completed, so the
calling agent effectively blocks.

---

## 2  Agent configs recap

* **AutoFilesystemAgent** – summarises every file and writes
  `files_summary.txt` (see previous guide).
* **StartAndWaitAgent** – deletes `files_summary.txt` if present, invokes
  `_start_and_wait_AutoFilesystemAgent`, then verifies the file exists again.

Both agents use the same `filesystem-mcp-server` plus
`AutoFilesystemAgent_mcp`.

---

## 3  Run the demonstration

Prerequisites (if not already running):

```bash
# in project root
echo "Sample" > data/example.txt            # ensure at least one file exists
python mcp_servers/filesystem_mcp_server.py &
export OPENAI_API_KEY="sk-…"
```

Now start **StartAndWaitAgent**:

```bash
run_agent StartAndWaitAgent "Refresh summaries"
```

The expected plan (simplified):

1. Check if `files_summary.txt` exists and delete it.
2. Call `_start_and_wait_AutoFilesystemAgent` with prompt "Summarise every
   file you can access" and this job's `JOB_ID`.
3. Verify the file now exists and report completion.

Because `_start_and_wait_…` adds a dependency, you will see the worker process
pick up the AutoFilesystemAgent job first; only after it finishes will the
StartAndWaitAgent resume, reach 100 % completion and exit.

---

## 4  Inspecting traces

The outer job is traced as:

```
autonomous-chat-StartAndWaitAgent-<JobID>
```

Inside that trace you will find a child run that corresponds to
AutoFilesystemAgent.  Opening that trace lets you inspect both levels of the
workflow.

---

Happy orchestrating! 🎉 