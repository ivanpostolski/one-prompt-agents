# Core Concepts of Agent Building

The fundamental philosophy of One-Prompt Agents is simplicity. An AI agent is primarily defined by two components: a prompt file and a JSON configuration file. This allows for rapid prototyping and deployment.

## Directory Structure

All agents are organized within a main directory named `agents_config`. This directory should be located at the root of your project.

Each agent resides in its own subdirectory within `agents_config`. For example:

```
your-project-root/
├── agents_config/
│   ├── YourAgentName/
│   │   ├── config.json
│   │   ├── prompt.txt
│   │   └── return_type.py
│   └── AnotherAgentName/
│       ├── config.json
│       ├── prompt.md
│       └── return_type.py
└── ... (other project files)
```

- **`agents_config/`**: The top-level directory for all agent definitions.
- **`agents_config/YourAgentName/`**: A dedicated folder for a specific agent. It contains all the files necessary for that agent's operation.

## The `config.json` File

The `config.json` file is the heart of an agent's definition. It specifies the agent's behavior, tools, and output structure. Here are the key fields:

-   **`name` (string):** The unique name of the agent. This name is used to identify and call the agent.
-   **`prompt_file` (string):** The filename of the text file containing the agent's core prompt (e.g., "prompt.txt", "instructions.md").
-   **`return_type` (string):** The name of the Pydantic model class defined in the corresponding `return_type.py` file. This class specifies the expected structure of the agent's output.
-   **`inputs_description` (string):** A human-readable description of what inputs the agent expects. This helps in understanding how to interact with the agent.
-   **`tools` (list of strings):** A list of other agents or pre-defined MCP (Multi-Capability Agent Protocol) server names that this agent can utilize as tools. If the agent doesn't use any tools, this should be an empty list `[]`.
-   **`model` (string, optional):** Specifies the underlying language model to be used (e.g., "o4-mini", "gpt-4"). If omitted, a default model (currently "o4-mini") is used.

## The Prompt File

The prompt file (e.g., `prompt.txt`, `instructions.md`) is a plain text or markdown file. It contains the natural language instructions, persona, and context for the AI agent. The content of this file directly guides the agent's behavior and responses.

## The `return_type.py` File

The `return_type.py` file defines the expected structure of the agent's output. It uses Pydantic models to specify the schema of the data that the agent should return after processing a prompt. This ensures structured and predictable outputs.

The `return_type` field in `config.json` must match the name of a Pydantic model class defined in this file.

For example, if your `config.json` has `"return_type": "AnalysisResult"`, your `return_type.py` might look like this:

```python
from pydantic import BaseModel, Field
from typing import List

class AnalysisResult(BaseModel):
    summary: str = Field(description="A brief summary of the analysis.")
    keywords: List[str] = Field(description="A list of extracted keywords.")
    confidence: float = Field(description="A confidence score for the analysis.")
```
This ensures that the agent's output will be a JSON object conforming to the `AnalysisResult` schema.

# Step-by-Step: Creating a 'GreeterAgent'

Let's walk through creating a simple example agent called `GreeterAgent`. This agent will take a name as input and return a personalized greeting.

## 1. Create the Agent's Directory

First, create a directory for your new agent within the `agents_config` directory:

```
your-project-root/
└── agents_config/
    └── GreeterAgent/  <-- Create this directory
```

Inside `agents_config/GreeterAgent/`, you will create three files: `config.json`, `prompt.md`, and `return_type.py`.

## 2. Create and Populate `config.json`

Create the file `agents_config/GreeterAgent/config.json` with the following content:

```json
{
    "name": "GreeterAgent",
    "prompt_file": "prompt.md",
    "return_type": "GreetingResponse",
    "inputs_description": "A name to greet.",
    "tools": [],
    "model": "o4-mini"
}
```

**Explanation:**
-   `"name": "GreeterAgent"`: Defines the agent's unique identifier.
-   `"prompt_file": "prompt.md"`: Specifies that the agent's instructions are in `prompt.md`.
-   `"return_type": "GreetingResponse"`: Indicates that the agent's output will conform to the `GreetingResponse` Pydantic model defined in `return_type.py`.
-   `"inputs_description": "A name to greet."`: Describes what input the agent expects.
-   `"tools": []`: The GreeterAgent doesn't use any external tools.
-   `"model": "o4-mini"`: Specifies the language model to use.

## 3. Create and Populate `prompt.md`

Create the file `agents_config/GreeterAgent/prompt.md` with the following content:

```markdown
You are a friendly Greeter Agent. Your task is to greet the user by their name.
The user will provide their name as input.
You should respond with a personalized greeting in the 'greeting_message' field.

For example, if the input name is "Alice", your greeting message should be "Hello, Alice! Nice to meet you."
```

**Explanation:**
This prompt clearly defines the agent's persona (friendly), its task (greet by name), how it receives input, and the desired output format (a personalized greeting in the `greeting_message` field). The example clarifies the expected behavior.

## 4. Create and Populate `return_type.py`

Create the file `agents_config/GreeterAgent/return_type.py` with the following content:

```python
from pydantic import BaseModel, Field

class GreetingResponse(BaseModel):
    greeting_message: str = Field(description="The personalized greeting message.")
```

**Explanation:**
-   We import `BaseModel` and `Field` from Pydantic.
-   `class GreetingResponse(BaseModel):` defines a Pydantic model named `GreetingResponse`. This name matches the `return_type` specified in `config.json`.
-   `greeting_message: str = Field(description="The personalized greeting message.")` defines a single field in our response model. It specifies that `greeting_message` will be a string and provides a description for it. This ensures the agent's output will be a JSON object like: `{"greeting_message": "Hello, Bob! Nice to meet you."}`.

# Running Your Agents

Once you have defined your agents in the `agents_config` directory, you can run them using the commands configured in your project (typically via `pyproject.toml`).

**Important:** Ensure that the `agents_config` directory, containing all your agent definitions, is present in the directory from which you execute these commands. Also, make sure your project's virtual environment is activated.

## 1. Interactive REPL Mode

This mode allows you to chat with a specific agent directly in your console. The REPL mode typically looks for a field in the agent's response model that conventionally holds the main textual output (e.g., `content` as recommended in Best Practices, but it can also be other fields like `response` or, as in our `GreeterAgent`'s `GreetingResponse` model, `greeting_message`). The value of this field is then displayed.

-   **Start REPL:**
    ```bash
    run_agent <agent_name>
    ```
    Example with `GreeterAgent`:
    ```bash
    run_agent GreeterAgent
    ```
    The system will prompt you for input. For `GreeterAgent`, you would enter a name. If you enter "Bob", and the REPL is configured to display the `greeting_message` field from `GreetingResponse`, you would see output like:
    `GreeterAgent: Hello, Bob! Nice to meet you.`

## 2. Autonomous Console Mode

This mode runs an agent with a single prompt directly from the command line and prints its full structured output (or a summary, depending on the agent's design and the runner script's implementation).

-   **Run agent:**
    ```bash
    run_agent <agent_name> "<your_prompt_here>"
    ```
    Example with `GreeterAgent` (assuming the input is directly mapped to the prompt context):
    ```bash
    run_agent GreeterAgent "Alice"
    ```
    This would likely output the full JSON response:
    ```json
    {
        "greeting_message": "Hello, Alice! Nice to meet you."
    }
    ```

## 3. HTTP Server Mode

This mode starts a FastAPI server, allowing you to interact with your agents via HTTP requests.

-   **Start the server:**
    ```bash
    run_server
    ```
    By default, the server usually runs on `http://127.0.0.1:9000`. You might see logging options like `run_server --log -v` for more detailed output.

-   **Triggering an agent:**
    Send a `POST` request to the `/{agent_name}/run` endpoint. The body of the request should be a JSON object containing the prompt.

    For example, to run our `GreeterAgent` with the name "Charlie":
    ```bash
    curl -X POST http://127.0.0.1:9000/GreeterAgent/run \
         -H "Content-Type: application/json" \
         -d '{"prompt": "Charlie"}'
    ```
    The agent will process the request. The immediate response might indicate the task was started:
    ```json
    {"status": "started", "agent": "GreeterAgent"}
    ```
    The actual result (the greeting) would be processed by the agent, and how it's delivered depends on the server setup (e.g., it might be logged, sent to a webhook, or available via another endpoint). The `README.md` mentions that the `EchoAgent`'s output is processed in the background.

## Helper Script (`http_start.py`)

The project may include a helper script like `http_start.py` (mentioned in the main `README.md`) that can ensure the server is running (starting it if necessary) and then trigger an agent. This provides a convenient way to launch agents via HTTP from the command line.

Example usage (syntax might vary based on the script's implementation):
```bash
python -m src.one_prompt_agents.http_start GreeterAgent "David"
```
This would typically handle starting the server and sending the prompt "David" to the `GreeterAgent`.

# Advanced Concepts

This section delves into more advanced features for building sophisticated agents.

## Using Tools Within an Agent

Agents can be designed to use other agents or pre-defined MCP (Multi-Capability Agent Protocol) servers as "tools." This allows you to build more complex systems where agents delegate specific tasks to specialized tools or other agents.

To enable this, you configure the `tools` field in an agent's `config.json` file. This field takes a list of strings, where each string is the name of another agent or a known MCP server.

For example, an agent named `MyMainAgent` might be configured to use another agent (`AnotherAgentName`) and an MCP tool (`SomeMCPTool`):

```json
{
    "name": "MyMainAgent",
    "prompt_file": "main_prompt.txt",
    "return_type": "MainResponse",
    "inputs_description": "Input for the main agent.",
    "tools": ["AnotherAgentName", "SomeMCPTool"],
    "model": "o4-mini"
}
```

**Crucially, simply listing tools in `config.json` is not enough.** The agent's prompt (e.g., in `main_prompt.txt` for `MyMainAgent`) must explicitly instruct the agent on how and when to utilize these declared tools. The prompt should guide the agent to understand what each tool does and under what circumstances it should call them.

The framework handles the resolution and communication with these declared tools, whether they are other agents defined within `agents_config` or externally defined MCP servers.

## The "Make a Plan" Strategy

For more complex tasks that require multiple steps or objectives, agents can be designed to first create a plan and then execute it. This strategy enhances the agent's autonomy and allows for better progress tracking, especially in autonomous scenarios.

### Core Idea

Instead of directly trying to solve the entire task with a single response, the agent's initial goal is to outline a series of steps (a plan) to achieve the overall objective.

1.  **Define a Plan-Oriented `return_type`**:
    The agent's `return_type.py` would define Pydantic models representing the plan and its individual tasks. Each task could have attributes like a description and a completion status (e.g., "pending", "completed").

    Example `return_type.py` for a planning agent:
    ```python
    from pydantic import BaseModel, Field
    from typing import List, Optional # Optional was imported as Optional in README

    class Task(BaseModel):
        task_id: int = Field(description="Unique identifier for the task.")
        description: str = Field(description="What needs to be done for this task.")
        status: str = Field(default="pending", description="Status of the task, e.g., 'pending', 'completed'.")

    class PlanResponse(BaseModel):
        plan_summary: str = Field(description="A brief summary of the overall plan.")
        tasks: List[Task] = Field(description="A list of tasks to be executed.")
        next_task_id: Optional[int] = Field(default=None, description="The ID of the next task to be executed.") # Changed from int | None for consistency
    ```
    The agent's `config.json` would then specify `"return_type": "PlanResponse"`.

2.  **Prompt for Planning**:
    The agent's prompt file (e.g., `prompt.txt`) would instruct it to analyze the user's request, break it down into manageable steps, and return this plan using the defined `PlanResponse` structure.

3.  **Interaction Flow**:
    *   **User**: Provides an initial complex prompt (e.g., "Research topic X and write a summary").
    *   **Agent (First Interaction)**: Returns a `PlanResponse` JSON object detailing the steps (e.g., Task 1: Search for sources, Task 2: Read and analyze sources, Task 3: Draft summary, Task 4: Review and finalize summary). Initially, all tasks are "pending".
    *   **User/Orchestrator**: Reviews the plan. Then, in subsequent turns, instructs the agent to execute the plan, often step-by-step (e.g., "Proceed with the next step", "Execute task 2").
    *   **Agent (Subsequent Interactions)**: Executes the indicated task. It might return an updated `PlanResponse` showing the completed task and potentially the output of that specific task, or a simpler status update. It might also update the `next_task_id`.

### Benefits

*   **Handles Complex Goals**: Breaks down large tasks into smaller, manageable parts.
*   **Transparency & Control**: Users can see the agent's plan before execution and guide the process.
*   **Progress Tracking**: Easy to see which steps have been completed and what's next.
*   **Flexibility**: Allows for iterative execution and potential plan adjustments if needed.

This "make a plan" strategy is particularly effective for autonomous agents designed to perform multi-stage operations.

## Extending with Custom MCP Servers

Beyond using other agents as tools, the framework supports the integration of custom MCP (Multi-Capability Agent Protocol) servers. This allows you to connect specialized, independently running services or capabilities that adhere to the MCP standard.

### How it Works

1.  **Directory for MCP Servers**:
    *   Create a directory in your project, conventionally named `mcp_servers/`. This directory will house your custom MCP server definitions. The actual search directory might be configurable in the framework (e.g., via `SEARCH_DIR` in a loader module).

2.  **MCP Server Definition Files**:
    *   Inside the `mcp_servers/` directory, create Python files for each of your custom MCP servers.
    *   These files must have a specific suffix, by default `_mcp_server.py` (this might also be configurable, e.g., via `MODULE_SUFFIX`). For example, `my_custom_tool_mcp_server.py`.

3.  **Defining MCP Server Instances**:
    *   Within each such Python file, define one or more module-level instances of `MCPServerSse` or `MCPServerStdio` (imported from a relevant framework module like `agents.mcp`). These classes represent your MCP server's client-side interface.
    *   **Each instance must have a unique `name` attribute.** This name is how agents will refer to this MCP server in their `tools` list in `config.json`.

    Example (conceptual, based on `apify_example_mcp_server.py` from `README.md`):
    ```python
    import os
    from agents.mcp import MCPServerSse # Assuming MCPServerSse is in agents.mcp

    # Example: Defining an Apify MCP Server Client
    APIFY_TOKEN = os.getenv("APIFY_TOKEN")
    # Ensure APIFY_TOKEN is set, or handle error

    apify_mcp_client = MCPServerSse(
        params={
            "url": f"https://actors-mcp-server.apify.actor/sse?enableAddingActors=true",
            "headers": {
                "Authorization": f"Bearer {APIFY_TOKEN}",
            },
            "timeout": 180,
            "sse_read_timeout": 300,
        },
        client_session_timeout_seconds=60,
        cache_tools_list=True,
        name="apify-mcp-server", # Crucial: This name is used in agent's config.json
    )
    ```

4.  **Automatic Discovery and Loading**:
    *   When the main application starts, a loader mechanism (e.g., `collect_servers()` from `mcp_servers_loader.py` mentioned in `README.md`) typically scans the designated `SEARCH_DIR` for files matching the `MODULE_SUFFIX`.
    *   It dynamically imports these modules.
    *   It collects all top-level instances of `MCPServerSse` or `MCPServerStdio` found in these modules. These are then made available to agents.

5.  **Server-Side Logic (Optional `main()` hook)**:
    *   The `MCPServerSse`/`MCPServerStdio` instances are *clients* that allow agents to communicate with your MCP-compliant service.
    *   If the actual service (the server part of your MCP tool) needs to be started or managed by the One-Prompt Agents framework, you can implement this logic within an optional `main()` function in your `*_mcp_server.py` file.
    *   For example, `main()` could start a local FastAPI server that implements your tool's functionality, and the `MCPServerSse` instance would point to this local server's URL. Any `asyncio.Task` returned by `main()` might be collected and managed by the main application loop.

6.  **Agent Integration**:
    *   Once an MCP server client is defined and loaded, any agent can list its `name` (e.g., `"apify-mcp-server"`) in its `tools` array within its `config.json`. The framework will then inject this pre-configured `MCPServerSse` or `MCPServerStdio` instance into the agent, allowing the agent's prompt to delegate tasks to it.

This mechanism provides a flexible way to extend your agents' capabilities by integrating them with external or custom-built MCP-compliant tools and services.

# Best Practices and Tips

Here are some recommendations to help you build effective and robust agents:

## Writing Clear and Effective Prompts

The prompt is the core instruction for your agent. A well-crafted prompt is essential for desired behavior.

*   **Be Specific:** Clearly define the agent's persona (e.g., "You are a helpful assistant," "You are a terse summarizer"), its specific task, any constraints, and the exact format you expect for the output.
*   **Use Examples:** If the task or output format is complex, provide one or more examples directly in the prompt. For instance, "If the input is X, the output should be Y."
*   **Explicitly State Output Fields:** If your `return_type.py` defines specific fields, ensure your prompt instructs the agent to populate these fields correctly. For example, "Place the summary in the 'summary_text' field and any keywords in the 'keywords_list' field."

## Designing Useful `return_type` Models

Pydantic models in `return_type.py` ensure your agent's output is structured and predictable.

*   **Embrace Structured Output:** Even for simple responses, using a Pydantic model is good practice. It makes the agent's output reliable and easier to integrate with other systems or agents.
*   **Interactive Agent Convention (`content` field):** For agents primarily designed for interactive use (e.g., in the REPL or a chat interface), it's a common convention to include a `content: str` field in your Pydantic model. Many REPL implementations will look for this field by default to display a direct textual response to the user.
    ```python
    # Example for an interactive agent
    class InteractiveResponse(BaseModel):
        content: str = Field(description="The direct textual response for the user.")
        # ... other fields if needed
    ```
*   **Autonomous/Planning Agent Fields:** For autonomous agents, especially those using the "Make a Plan" strategy, ensure your task descriptions within the plan are clear and trackable. Consider including fields like:
    *   `step_name: str`: A concise name for the step.
    *   `status: str`: (e.g., "pending", "in_progress", "completed", "failed") or `checked: bool` to indicate completion.
    This helps in monitoring and managing the agent's execution flow.
    ```python
    # Example Task model for a planning agent
    class Task(BaseModel):
        task_id: int
        step_name: str = Field(description="A short name for this task step.")
        description: str
        status: str = Field(default="pending", description="e.g., pending, completed, failed")
        # ... other relevant fields like input_parameters, results, etc.
    ```

## Iterative Testing and Development

Building agents is often an iterative process.

*   **Start Simple:** Begin with a basic version of your agent and gradually add complexity.
*   **Test Frequently:** Use the various running modes (REPL, console, HTTP server) to test your agent at each stage of development. This helps catch issues early. The REPL mode is particularly useful for quick prompt and response validation.

## Breaking Down Complex Tasks

If an agent's task becomes too complex, it can lead to unreliable behavior or overly complicated prompts.

*   **Multiple Specialized Agents:** Consider breaking down the complex task into smaller sub-tasks, each handled by a more specialized agent. These agents can then be orchestrated by a primary agent.
*   **Leverage Tools:** If a sub-task involves a common operation or an external service, use the `tools` mechanism to integrate another agent or an MCP server.

## Custom MCP Server Development

When developing your own MCP (Multi-Capability Agent Protocol) servers:

*   **Port Selection:** Be mindful when selecting network ports for your custom MCP servers if they involve starting their own HTTP services (e.g., via the optional `main()` function). Choose ports that do not conflict with the main One-Prompt Agents server (often on port 9000) or any other services running on your system. Check for port availability to avoid startup failures.
*   **Clear Naming:** Ensure the `name` attribute of your `MCPServerSse` or `MCPServerStdio` instance is unique and descriptive, as this is how agents will identify and use it.
