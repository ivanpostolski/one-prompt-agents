# Getting-Started example

This small folder is **self-contained** – you can copy it anywhere and immediately run the agent as long as the `one-prompt-agents` package is installed and the `OPENAI_API_KEY` environment variable is set.

```bash
pip install one-prompt-agents
export OPENAI_API_KEY="sk-..."

run_agent InteractiveAgent                # interactive REPL
```

The agent lives in `agents_config/InteractiveAgent/` and returns a minimal JSON payload whose single field `content` is a free-form string.

Feel free to duplicate the folder and start hacking on your own agent!

---

## FilesystemAgent (with local MCP server)

```bash
# start the filesystem MCP server (requires Node.js ≥ 18 and npx)
python mcp_servers/filesystem_mcp_server.py &

# in a second shell – still inside this folder – run the agent
run_agent FilesystemAgent
```

When prompted you can ask:

```
What tools do you have?

List the files in the root directory.
```

The MCP server mounts the local `data/` directory (created automatically) and exposes
standard file-system tools (read, write, list, etc.). 

## AutoFilesystemAgent

```bash
run_agent AutoFilesystemAgent
```

After it finishes the CLI will start an HTTP server on `http://127.0.0.1:9000`. You
can send more jobs with:

```bash
curl -X POST "http://127.0.0.1:9000/agents/AutoFilesystemAgent" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Append a summary for all .md files."}'
``` 