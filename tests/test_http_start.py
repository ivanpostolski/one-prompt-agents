import pytest
from unittest.mock import patch, MagicMock, call
import sys # For sys.argv and sys.exit
import subprocess # For Popen
import time # For sleep
import requests # For exceptions

# Functions to test
from src.one_prompt_agents.http_start import ensure_server, trigger, main as http_main # aliasing main

# --- 1. Testing ensure_server(agent, prompt) ---

@patch('src.one_prompt_agents.http_start.time.sleep')
@patch('src.one_prompt_agents.http_start.subprocess.Popen')
@patch('src.one_prompt_agents.http_start.requests.get')
def test_ensure_server_already_running(mock_requests_get, mock_popen, mock_sleep):
    """Test ensure_server when the server is already running."""
    mock_response = MagicMock()
    mock_response.status_code = 200 # Unused by current ensure_server, but good practice
    mock_requests_get.return_value = mock_response

    result = ensure_server("TestAgent", "TestPrompt")

    assert result is True
    mock_requests_get.assert_called_once_with("http://127.0.0.1:9000/")
    mock_popen.assert_not_called()
    mock_sleep.assert_not_called()


@patch('src.one_prompt_agents.http_start.time.sleep')
@patch('src.one_prompt_agents.http_start.subprocess.Popen')
@patch('src.one_prompt_agents.http_start.requests.get')
def test_ensure_server_starts_on_first_retry(mock_requests_get, mock_popen, mock_sleep):
    """Test ensure_server when server is not running but starts after Popen and one sleep."""
    mock_successful_response = MagicMock()
    # Simulate: 1. ConnectionError, 2. Popen called, 3. sleep, 4. Successful get
    mock_requests_get.side_effect = [
        requests.exceptions.ConnectionError, # Initial check fails
        mock_successful_response             # Check after sleep succeeds
    ]
    mock_popen_instance = MagicMock()
    mock_popen.return_value = mock_popen_instance # Popen returns a process object

    result = ensure_server("TestAgent", "TestPrompt")

    assert result is True
    assert mock_requests_get.call_count == 2
    mock_requests_get.assert_has_calls([
        call("http://127.0.0.1:9000/"), # Initial
        call("http://127.0.0.1:9000/")  # Retry
    ])
    mock_popen.assert_called_once_with(["run_agent", "-v", "--log"])
    mock_sleep.assert_called_once_with(1)


@patch('src.one_prompt_agents.http_start.time.sleep')
@patch('src.one_prompt_agents.http_start.subprocess.Popen')
@patch('src.one_prompt_agents.http_start.requests.get')
def test_ensure_server_starts_after_multiple_retries(mock_requests_get, mock_popen, mock_sleep):
    """Test ensure_server starting after multiple ConnectionErrors and sleeps."""
    num_failures = 3
    mock_successful_response = MagicMock()
    side_effects = [requests.exceptions.ConnectionError] * (num_failures + 1) # Initial + num_failures during retry
    side_effects[num_failures] = mock_successful_response # Success on the 4th get call (1 initial + 3 retries)
    
    mock_requests_get.side_effect = side_effects

    result = ensure_server("TestAgent", "TestPrompt")

    assert result is True
    assert mock_requests_get.call_count == num_failures + 1 
    mock_popen.assert_called_once_with(["run_agent", "-v", "--log"])
    assert mock_sleep.call_count == num_failures # Sleeps for each retry attempt that fails


@patch('src.one_prompt_agents.http_start.time.sleep')
@patch('src.one_prompt_agents.http_start.subprocess.Popen')
@patch('src.one_prompt_agents.http_start.requests.get')
@patch('src.one_prompt_agents.http_start.print') # To check error print
def test_ensure_server_fails_to_start_all_retries(mock_print, mock_requests_get, mock_popen, mock_sleep):
    """Test ensure_server when server fails to start after all 20 retries."""
    # Max 20 retries + 1 initial check = 21 ConnectionError
    mock_requests_get.side_effect = requests.exceptions.ConnectionError 

    result = ensure_server("TestAgent", "TestPrompt")

    assert result is False
    assert mock_requests_get.call_count == 21 # 1 initial + 20 retries
    mock_popen.assert_called_once_with(["run_agent", "-v", "--log"])
    assert mock_sleep.call_count == 20 # 20 sleeps for 20 retries
    mock_print.assert_called_with("Failed to start main.py HTTP server after multiple retries.", file=sys.stderr)


# --- 2. Testing trigger(agent, prompt) ---

@patch('src.one_prompt_agents.http_start.print') # To check output print
@patch('src.one_prompt_agents.http_start.requests.post')
def test_trigger_successful(mock_requests_post, mock_print):
    """Test successful agent trigger."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "triggered", "agent_id": "Agent1"}
    mock_requests_post.return_value = mock_response

    trigger("Agent1", "Hello Agent1")

    mock_requests_post.assert_called_once_with(
        "http://127.0.0.1:9000/Agent1/run",
        json={"prompt": "Hello Agent1"}
    )
    mock_response.raise_for_status.assert_called_once()
    mock_print.assert_called_once_with({"status": "triggered", "agent_id": "Agent1"})


@patch('src.one_prompt_agents.http_start.print')
@patch('src.one_prompt_agents.http_start.requests.post')
def test_trigger_fails_http_error(mock_requests_post, mock_print):
    """Test trigger when server returns an HTTP error."""
    mock_response = MagicMock()
    http_error = requests.exceptions.HTTPError("Server Error")
    mock_response.raise_for_status.side_effect = http_error
    mock_requests_post.return_value = mock_response

    with pytest.raises(requests.exceptions.HTTPError, match="Server Error"):
        trigger("AgentHttpErr", "Test")
    
    mock_response.raise_for_status.assert_called_once()
    mock_print.assert_not_called() # Should not print JSON if error


@patch('src.one_prompt_agents.http_start.requests.post')
def test_trigger_fails_connection_error(mock_requests_post):
    """Test trigger when a connection error occurs."""
    conn_error = requests.exceptions.ConnectionError("Cannot connect")
    mock_requests_post.side_effect = conn_error

    with pytest.raises(requests.exceptions.ConnectionError, match="Cannot connect"):
        trigger("AgentConnErr", "Test")


# --- 3. Testing main(argv) ---

@patch('src.one_prompt_agents.http_start.sys.exit')
@patch('src.one_prompt_agents.http_start.trigger')
@patch('src.one_prompt_agents.http_start.ensure_server')
def test_main_valid_args_agent_and_prompt(mock_ensure_server, mock_trigger, mock_sys_exit):
    """Test main function with agent name and prompt."""
    mock_ensure_server.return_value = True
    argv = ['http_start.py', 'MyAgent', 'My', 'Prompt']
    
    http_main(argv)

    mock_ensure_server.assert_called_once_with('MyAgent', 'My Prompt')
    mock_trigger.assert_called_once_with('MyAgent', 'My Prompt')
    mock_sys_exit.assert_not_called()


@patch('src.one_prompt_agents.http_start.sys.exit')
@patch('src.one_prompt_agents.http_start.trigger')
@patch('src.one_prompt_agents.http_start.ensure_server')
def test_main_valid_args_agent_only(mock_ensure_server, mock_trigger, mock_sys_exit):
    """Test main function with only agent name (empty prompt)."""
    mock_ensure_server.return_value = True
    argv = ['http_start.py', 'MyAgent']

    http_main(argv)

    mock_ensure_server.assert_called_once_with('MyAgent', '')
    mock_trigger.assert_called_once_with('MyAgent', '')
    mock_sys_exit.assert_not_called()


@patch('src.one_prompt_agents.http_start.print') # To check stderr print
@patch('src.one_prompt_agents.http_start.sys.exit')
@patch('src.one_prompt_agents.http_start.trigger')
@patch('src.one_prompt_agents.http_start.ensure_server')
def test_main_not_enough_args(mock_ensure_server, mock_trigger, mock_sys_exit, mock_print_stderr):
    """Test main function with not enough arguments."""
    argv = ['http_start.py'] # Only script name

    http_main(argv)

    mock_print_stderr.assert_called_once_with("Usage: http_start.py [agent_name] [prompt...]", file=sys.stderr)
    mock_sys_exit.assert_called_once_with(1)
    mock_ensure_server.assert_not_called()
    mock_trigger.assert_not_called()


@patch('src.one_prompt_agents.http_start.sys.exit')
@patch('src.one_prompt_agents.http_start.trigger')
@patch('src.one_prompt_agents.http_start.ensure_server')
def test_main_ensure_server_fails(mock_ensure_server, mock_trigger, mock_sys_exit):
    """Test main function when ensure_server returns False."""
    mock_ensure_server.return_value = False # Simulate server failing to start
    argv = ['http_start.py', 'MyAgent', 'Prompt']

    http_main(argv)

    mock_ensure_server.assert_called_once_with('MyAgent', 'Prompt')
    mock_trigger.assert_not_called() # Trigger should not be called
    mock_sys_exit.assert_called_once_with(1) # Should exit with error


@patch('src.one_prompt_agents.http_start.print') # To check stderr print
@patch('src.one_prompt_agents.http_start.sys.exit')
@patch('src.one_prompt_agents.http_start.trigger')
@patch('src.one_prompt_agents.http_start.ensure_server')
def test_main_trigger_fails_request_exception(mock_ensure_server, mock_trigger, mock_sys_exit, mock_print_stderr):
    """Test main function when trigger raises a RequestException."""
    mock_ensure_server.return_value = True
    trigger_exception = requests.exceptions.ConnectionError("Trigger failed")
    mock_trigger.side_effect = trigger_exception
    argv = ['http_start.py', 'MyAgent', 'Prompt']

    http_main(argv)

    mock_ensure_server.assert_called_once_with('MyAgent', 'Prompt')
    mock_trigger.assert_called_once_with('MyAgent', 'Prompt')
    mock_print_stderr.assert_called_once_with(f"Error triggering agent MyAgent: {trigger_exception}", file=sys.stderr)
    mock_sys_exit.assert_called_once_with(1)
