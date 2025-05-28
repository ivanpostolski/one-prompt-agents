#!/usr/bin/env python3
import sys, subprocess, time
import requests

def ensure_server(agent, prompt):
    """Ensures that the main FastAPI server is running, starting it if necessary.

    It first attempts a health check to "http://127.0.0.1:9000/".
    If the server is not reachable (ConnectionError), it tries to start
    the main application (`run_agent -v --log`) as a background process.
    It then waits and retries the health check for up to 20 seconds.

    Note: The `agent` and `prompt` arguments are not currently used by this function
    but are kept for potential future use or to maintain a consistent signature
    with other related functions.

    Args:
        agent: The name of the agent (currently unused).
        prompt: The prompt for the agent (currently unused).

    Returns:
        bool: True if the server is running or successfully started, False otherwise.
    """
    # health‐check any endpoint
    try:
        requests.get("http://127.0.0.1:9000/")
        return True
    except requests.exceptions.ConnectionError:
        # not up → start main.py in background
        subprocess.Popen(["run_agent", "-v", "--log"])
        # wait for server to spin up
        for i in range(20):
            time.sleep(1)
            try:
                requests.get("http://127.0.0.1:9000/")
                return True
            except:
                continue
        print("Failed to start main.py HTTP server.")
        return False

def trigger(agent, prompt):
    """Triggers a specific agent on the running FastAPI server via an HTTP POST request.

    Sends a POST request to `http://127.0.0.1:9000/{agent}/run` with the
    provided `prompt` in the JSON body.

    Args:
        agent (str): The name of the agent to trigger.
        prompt (str): The prompt to send to the agent.

    Raises:
        requests.exceptions.HTTPError: If the server returns an error status code.
    """
    url = f"http://127.0.0.1:9000/{agent}/run"
    resp = requests.post(url, json={"prompt": prompt})
    resp.raise_for_status()
    print(resp.json())

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: start_agent.py [agent_name] [prompt...]", file=sys.stderr)
        sys.exit(1)

    agent  = sys.argv[1]
    prompt = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
    ensure_server()
    trigger(agent, prompt)
