import logging
import requests
import sys

logger = logging.getLogger(__name__) 

def uvicorn_log_level() -> str | None:
    """Determines the appropriate log level string for Uvicorn based on the current root logger settings.

    This function checks the global logging configuration of the application.
    If logging is completely disabled (e.g., `logging.disable(logging.CRITICAL)` has been called),
    it returns `None`.
    Otherwise, it gets the effective logging level of the root logger, converts it to a lowercase
    string (e.g., "debug", "info"), and returns it if it's a Uvicorn-recognized level.
    If the current level is not directly recognized by Uvicorn (e.g., custom levels), it defaults
    to returning "warning".

    This utility is useful for synchronizing Uvicorn's internal logging level with the
    application's overall logging configuration, ensuring consistent log verbosity.

    Returns:
        str | None: A Uvicorn-compatible log level string (e.g., "debug", "info", "warning", "error", "critical", "trace"),
                    or `None` if logging is globally disabled. Defaults to "warning" for unrecognized levels.
    """
    root = logging.getLogger()
    if root.manager.disable >= logging.CRITICAL:
        return None                      # logging globally disabled

    name = logging.getLevelName(root.getEffectiveLevel()).lower()
    return name if name in {"critical","error","warning","info","debug","trace"} else "warning"

def shutdown_server_command():
    """Command-line utility to shutdown the FastAPI server.
    
    This function sends a POST request to the /shutdown endpoint of the running server.
    It's designed to be used as a console script entry point.
    """
    server_url = "http://127.0.0.1:9000/shutdown"
    
    try:
        print("Sending shutdown request to server...")
        response = requests.post(server_url, timeout=5)
        response.raise_for_status()
        
        result = response.json()
        print(f"✓ {result.get('message', 'Shutdown initiated')}")
        print("Server should shut down shortly.")
        
    except requests.exceptions.ConnectionError:
        print("✗ Error: Could not connect to server. Is it running on http://127.0.0.1:9000?")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("✗ Error: Request timed out. Server may already be shutting down.")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"✗ Error: Server returned an error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        sys.exit(1)