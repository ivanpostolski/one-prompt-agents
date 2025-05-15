#!/usr/bin/env python3
import sys, subprocess, time
import requests

def ensure_server(agent, prompt):
    # health‐check any endpoint
    try:
        return requests.get("http://127.0.0.1:9000/")
    except requests.exceptions.ConnectionError:
        # not up → start main.py in background
        subprocess.Popen(["run_agent", "-v"])
        # wait for server to spin up
        for i in range(20):
            time.sleep(0.5)
            try:
                requests.get("http://127.0.0.1:9000/")
                return
            except:
                continue
        print("Failed to start main.py HTTP server.", file=sys.stderr)
        sys.exit(1)

def trigger(agent, prompt):
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
