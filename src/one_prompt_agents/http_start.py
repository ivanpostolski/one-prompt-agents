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
        # Ensure Popen is called with arguments that make sense if the script is installed/runnable directly
        subprocess.Popen(["run_agent", "-v", "--log"]) # Assuming run_agent is in PATH or an alias
        # wait for server to spin up
        for i in range(20): # Max 20 retries
            time.sleep(1) # Wait 1 second between retries
            try:
                requests.get("http://127.0.0.1:9000/")
                return True
            except requests.exceptions.ConnectionError: # Explicitly catch ConnectionError
                continue
            except Exception as e: # Catch other potential errors during health check
                print(f"Health check attempt {i+1} failed with unexpected error: {e}", file=sys.stderr)
                continue # Or decide to stop retrying for unexpected errors
        print("Failed to start main.py HTTP server after multiple retries.", file=sys.stderr)
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
        requests.exceptions.ConnectionError: If the server is not reachable.
    """
    url = f"http://127.0.0.1:9000/{agent}/run"
    resp = requests.post(url, json={"prompt": prompt})
    resp.raise_for_status()
    print(resp.json()) # Output the response from the server

def main(argv):
    """Main function to parse arguments and orchestrate server check and agent trigger.

    Args:
        argv (list[str]): Command line arguments (including script name).
    """
    if len(argv) < 2:
        print("Usage: http_start.py [agent_name] [prompt...]", file=sys.stderr)
        sys.exit(1)

    agent  = argv[1]
    prompt = " ".join(argv[2:]) if len(argv) > 2 else ""
    
    # ensure_server doesn't actually use agent/prompt, but we pass them for signature consistency
    if ensure_server(agent, prompt):
        try:
            trigger(agent, prompt)
        except requests.exceptions.RequestException as e:
            print(f"Error triggering agent {agent}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # ensure_server already prints a message if it fails
        sys.exit(1)

if __name__ == "__main__":
    main(sys.argv)
