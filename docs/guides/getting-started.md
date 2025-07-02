# Getting Started with one-prompt-agents

Welcome! This guide will take you from **zero to running agents** in just a few minutes.  We will

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

If you cloned this repository you already have the sample in
`docs/resources/getting-started`.  Otherwise simply pull it straight from GitHub:

```bash
# clone only the sample directory using sparse-checkout (Git ≥ 2.25):
REPO=https://github.com/<your-org>/one-prompt-agents
mkdir getting-started && cd getting-started

git init -q

git remote add origin "$REPO"

git sparse-checkout init --cone

git sparse-checkout set docs/resources/getting-started

git pull -q origin main

# move the files one level up and tidy:
mv docs/resources/getting-started/* .
rm -rf docs
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

## 6  Next steps

* Explore the second guide – *Filesystem Agent – Interactive* – to learn how to add a tool
  that grants the agent access to the local file-system.
* Check out the third guide – *Filesystem Agent – Autonomous* – to see how an agent can plan and execute a multi-step task on its own.
* Browse the rest of the documentation in the `docs/` folder.

Happy hacking! 🎉