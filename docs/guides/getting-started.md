---
title: Getting Started
order: 1
caption: Zero to running agents in minutes using one-prompt-agents.
requirements:
  - Python 3.11
  - OpenAI API key
  - git (optional)
supademo: https://app.supademo.com/d/getting-started-placeholder
---
# Getting Started with one-prompt-agents

Welcome! This guide will take you from **zero to running an agent** in just a few minutes.  We will

1. Install the framework from PyPI.
2. Create a fresh Python 3.11 virtual-environment.
3. Clone & run the ready-made *Getting-Started* sample project.
4. Explore the most common CLI commands.

---

## 1  Requirements

* **Python 3.11** (tested on 3.11.x)
* macOS/Linux/WSL/Windows
* `git` – only needed if you want to clone the sample repo.
* An **OpenAI API key** stored in the environment variable `OPENAI_API_KEY`.

> The framework itself is pure-python and has no other system wide dependencies.

---

## 2  Create & activate an environment

```bash
# Install python 3.11 if you don't have it – see https://www.python.org/downloads/

# Inside *any* folder where you want to work:
python3.11 -m venv .venv              # create the venv
source .venv/bin/activate             # Linux / macOS
# .venv\Scripts\activate             # Windows-PowerShell

python -m pip install --upgrade pip   # always a good idea
```

---

## 3  Install the framework

```bash
pip install one-prompt-agents
```

That is it – all of the core code (plus FastAPI, pydantic, uvicorn, …) is now available in your environment.

---

## 4  Grab the *Getting-Started* sample project

```bash
git clone --depth=1 --filter=blob:none --no-checkout https://github.com/ivanpostolski/one-prompt-agents
cd one-prompt-agents 
git sparse-checkout set docs
git checkout main
cd docs/resources/getting-started
```


After these commands the current directory contains:

```text
getting-started/
 ├─ agents_config/
 │   └─ InteractiveAgent/
 │       ├─ config.json
 │       ├─ prompt.md
 │       └─ return_type.py
 ├─ README.md
 └─ requirements.txt
```

> Feel free to move the folder anywhere you like – the framework only cares about relative paths.

---

## 5  Run the agent interactively (REPL)

```bash
export OPENAI_API_KEY="sk-…"

run_agent InteractiveAgent
```

With **only** the agent name `InteractiveAgent` the CLI launches an interactive REPL.  Type a
message, press <kbd>↩︎</kbd> and the agent will answer.

### Why interactive first?

Running an agent in interactive mode is the **fastest feedback loop** for development:

* Prompt tuning – tweak `prompt.md`, rerun and instantly see the effect.
* Tools discovery – ask the agent `What tools do you have?` to verify the
  configuration.
* Rapid iteration – there's no need to restart a server or craft HTTP payloads.

Because the `tools` array in `agents_config/InteractiveAgent/config.json` is empty, the
agent will reply that it currently has **no tools available**.  You can add tools later
and immediately test them in the same REPL.

---

## 6 Choosing the OpenAI model

By default, each agent uses the model specified in its `config.json`. If the `model` field is omitted, the framework falls back to `"o4-mini"`.

Edit your sample agent config:

```json title="agents_config/InteractiveAgent/config.json"
{
  "name": "InteractiveAgent",
  "prompt_file": "prompt.md",
  "return_type": "InteractiveAgentResponse",
  "inputs_description": "Interactive example agent used in the getting-started guide.",
  "tools": [],
  "model": "gpt-4.1"
}
```

Notes:
- You can switch to a faster/cheaper model like `o4-mini` for quick iteration.
- Higher-capability models like `gpt-4.1` cost more but are often more robust.
- Make sure `OPENAI_API_KEY` is set in your environment.

---

## 7 Set-up the agent prompt

The agent’s instructions live in `agents_config/InteractiveAgent/prompt.md`. Open the file and tailor it to your use case. For example:

```md title="agents_config/InteractiveAgent/prompt.md"
You are a helpful assistant. Keep replies concise and actionable.
When the user asks a question, answer directly. If clarification is needed, ask one short follow-up question.
```

Tips:
- Keep the first paragraph as the high-level role/instructions.
- Add rules or examples below as bullet points to guide style and formatting.
- Rerun the REPL after edits to compare results quickly.

---

## 8 View the agent logs in OpenAI Platform

Follow these steps to inspect runs in the OpenAI web Platform Monitor:


1. Open `https://platform.openai.com/traces` in your browser.
2. Ensure you are in the correct Project/Workspace that matches the API key you used. Switch projects from the top-left project selector if needed.
3. Use the search bar:
   - For interactive REPL runs, search for `User-Chat-InteractiveAgent`.
   - For autonomous runs, copy the Trace URL printed in the console (e.g. `https://platform.openai.com/traces/<trace_id>`) or search for `autonomous-chat-InteractiveAgent-<JobID>`.
4. Click the trace to open it. Expand individual steps to see prompts, tool calls, model responses, and timing.
5. (Optional) Adjust the time range and environment filters to narrow down results.

Tip: If you enabled `--log`, you can also cross-check with the local file in `logs/run_YYYYMMDD_HHMMSS.log` for the printed trace URL and job IDs.
```bash
run_agent -v InteractiveAgent
```

---

## 9 Try out different configurations
For example, instruct the interactive agent prompt to return the user input backwards (word by word, letter by letter). 
  
## 10  Next steps

* Explore the second guide – *Filesystem Agent – Interactive* – to learn how to add a tool
  that grants the agent access to the local file-system.
* Check out the third guide – *Filesystem Agent – Autonomous* – to see how an agent can plan and execute a multi-step task on its own.
* Browse the rest of the documentation in the `docs/` folder.

Happy hacking! 🎉