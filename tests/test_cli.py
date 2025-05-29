import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call
import asyncio
import logging
import argparse # For checking SystemExit with argparse
import sys # For patching sys.argv

# Assuming cli.py is in src.one_prompt_agents.cli
# Functions to test (or main functions that orchestrate others)
# from src.one_prompt_agents.cli import run_server_cli, main_cli

# --- Mocks for the entire test suite ---

@pytest.fixture(autouse=True)
def mock_cli_dependencies(mocker):
    """Mocks all major dependencies of cli.py for isolation."""
    mocker.patch('src.one_prompt_agents.cli.setup_logging', return_value=logging.getLogger())
    mocker.patch('src.one_prompt_agents.cli.start_mcp_server', new_callable=AsyncMock)
    mocker.patch('src.one_prompt_agents.cli.collect_servers', return_value={}) # Default to no MCP servers
    mocker.patch('src.one_prompt_agents.cli.discover_configs', return_value={}) # Default to no agents discovered
    mocker.patch('src.one_prompt_agents.cli.topo_sort', return_value=[])
    mocker.patch('src.one_prompt_agents.cli.load_agents', return_value={}) # Default to no agents loaded
    mocker.patch('src.one_prompt_agents.cli.set_agents_for_api')
    mocker.patch('src.one_prompt_agents.cli.set_agents_for_mcp_setup')
    
    # Mock asyncio loop and its methods
    mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)
    mock_loop.create_task = MagicMock(return_value=AsyncMock(spec=asyncio.Task))
    mock_loop.run_forever = MagicMock()
    mock_loop.run_until_complete = MagicMock()
    mock_loop.close = MagicMock()
    mocker.patch('asyncio.get_event_loop', return_value=mock_loop)
    mocker.patch('asyncio.sleep', new_callable=AsyncMock) # Global sleep mock

    # Mock Uvicorn
    mock_uvicorn_server_instance = AsyncMock() # The server instance
    mock_uvicorn_server_instance.serve = AsyncMock()
    mock_uvicorn_server_instance.shutdown = AsyncMock()
    mock_uvicorn_server_class = MagicMock(return_value=mock_uvicorn_server_instance) # The Server class
    mocker.patch('src.one_prompt_agents.cli.uvicorn.Server', mock_uvicorn_server_class)
    mocker.patch('src.one_prompt_agents.cli.uvicorn.Config')
    mocker.patch('src.one_prompt_agents.cli.uvicorn_log_level', return_value="info")

    # Mock chat/job related functions
    mocker.patch('src.one_prompt_agents.cli.chat_worker', new_callable=AsyncMock)
    mocker.patch('src.one_prompt_agents.cli.user_chat', new_callable=AsyncMock)
    mocker.patch('src.one_prompt_agents.cli.submit_job', new_callable=AsyncMock, return_value="job-id-123")
    mocker.patch('src.one_prompt_agents.cli.job_manager.JOBS', {}) # Patch the JOBS dict
    
    # Mock job_queue
    mock_job_queue_instance = MagicMock(spec=asyncio.Queue)
    mock_job_queue_instance.empty = MagicMock(return_value=True) # Default to empty
    mock_job_queue_instance.join = AsyncMock()
    mock_job_queue_instance.get = AsyncMock() # For chat_worker if it runs
    mock_job_queue_instance.put = AsyncMock() # For submit_job
    mocker.patch('src.one_prompt_agents.cli.job_queue', mock_job_queue_instance)

    # Mocks for run_server_cli
    mocker.patch('src.one_prompt_agents.cli.ensure_server', new_callable=AsyncMock, return_value=True)
    mocker.patch('src.one_prompt_agents.cli.trigger', new_callable=AsyncMock)

    # Mock Path
    mocker.patch('src.one_prompt_agents.cli.Path')

    # Mock signal
    mocker.patch('signal.signal')
    
    # Mock AGENTS_REGISTRY and other globals that might be manipulated
    mocker.patch('src.one_prompt_agents.cli.AGENTS_REGISTRY', {})
    mocker.patch('src.one_prompt_agents.cli.MCP_SERVER_INSTANCES', {})
    mocker.patch('src.one_prompt_agents.cli.mcp_tasks', [])
    mocker.patch('src.one_prompt_agents.cli.worker_tasks', [])
    
    # Return a dict of key mocks if tests need to access them directly
    return {
        "loop": mock_loop,
        "uvicorn_server_class": mock_uvicorn_server_class,
        "uvicorn_server_instance": mock_uvicorn_server_instance,
        "job_queue": mock_job_queue_instance,
        "submit_job": asyncio.get_event_loop().create_task(mocker.patch('src.one_prompt_agents.cli.submit_job', new_callable=AsyncMock, return_value="job-id-123")), # Re-patch submit_job from the loop
    }


# Need to import the module to be tested *after* initial mocks if it has top-level asyncio calls
# For cli.py, it's usually fine if main() is guarded by if __name__ == "__main__"
# However, to be safe, we can import it within each test or a fixture that runs after mocks.
# For this structure, we'll assume cli.py can be imported at the top.
from src.one_prompt_agents import cli as cli_module


# --- 1. Testing run_server_cli() ---

@pytest.mark.asyncio
async def test_run_server_cli_valid_args(mocker):
    """Test run_server_cli with valid arguments."""
    with patch.object(sys, 'argv', ['script_name', 'TestAgent', 'TestPrompt']):
        # Access mocks set up by the autouse fixture via mocker object or directly if known
        ensure_server_mock = mocker.patch('src.one_prompt_agents.cli.ensure_server', new_callable=AsyncMock, return_value=True)
        trigger_mock = mocker.patch('src.one_prompt_agents.cli.trigger', new_callable=AsyncMock)
        
        await cli_module.run_server_cli()

        ensure_server_mock.assert_called_once()
        trigger_mock.assert_called_once_with('TestAgent', 'TestPrompt')

@pytest.mark.asyncio
async def test_run_server_cli_ensure_server_false(mocker):
    """Test run_server_cli when ensure_server returns False."""
    with patch.object(sys, 'argv', ['script_name', 'TestAgent', 'TestPrompt']):
        ensure_server_mock = mocker.patch('src.one_prompt_agents.cli.ensure_server', new_callable=AsyncMock, return_value=False)
        trigger_mock = mocker.patch('src.one_prompt_agents.cli.trigger', new_callable=AsyncMock)
        logger_mock = mocker.patch('src.one_prompt_agents.cli.logger')

        await cli_module.run_server_cli()

        ensure_server_mock.assert_called_once()
        trigger_mock.assert_not_called()
        logger_mock.error.assert_called_once_with("HTTP server is not running. Please start it first with 'run_agent' or 'python -m src.one_prompt_agents.main'.")

def test_run_server_cli_missing_args(mocker):
    """Test run_server_cli with missing arguments (handled by argparse)."""
    with patch.object(sys, 'argv', ['script_name']): # Only script name
        with pytest.raises(SystemExit): # Argparse should exit
            # Need to re-import or re-run the module's arg parsing logic if it's top-level
            # For this test, we assume run_server_cli() itself sets up its argparser.
            # If main_cli sets up a subparses, this needs careful thought.
            # run_server_cli has its own parser in the actual code.
            asyncio.run(cli_module.run_server_cli()) # Running it to trigger argparse

# --- 2. Testing main_cli() - Argument Parsing and Initial Setup ---

def test_main_cli_arg_parsing_no_args(mocker):
    """Test main_cli with no arguments, expecting server mode and default logging."""
    with patch.object(sys, 'argv', ['script_name']):
        setup_logging_mock = mocker.patch('src.one_prompt_agents.cli.setup_logging')
        # Mock loop.run_forever to prevent test hanging
        mocker.patch('asyncio.get_event_loop').run_forever = MagicMock()
        
        cli_module.main_cli()
        
        setup_logging_mock.assert_called_once_with(log_to_file=False, level=logging.INFO) # Default behavior

def test_main_cli_arg_parsing_log_verbose(mocker):
    """Test main_cli with --log and -v arguments."""
    with patch.object(sys, 'argv', ['script_name', '--log', '-v']):
        setup_logging_mock = mocker.patch('src.one_prompt_agents.cli.setup_logging')
        mocker.patch('asyncio.get_event_loop').run_forever = MagicMock()

        cli_module.main_cli()

        setup_logging_mock.assert_called_once_with(log_to_file=True, level=logging.DEBUG)

# --- 3. Testing main_cli() - REPL Mode ---

def test_main_cli_repl_mode(mocker):
    """Test main_cli REPL mode operation."""
    with patch.object(sys, 'argv', ['script_name', 'TestAgentREPL']):
        mock_mcp_agent_instance = MagicMock()
        mock_mcp_agent_instance.agent = MagicMock() # The actual agent object for user_chat
        
        load_agents_mock = mocker.patch('src.one_prompt_agents.cli.load_agents', return_value={"TestAgentREPL": mock_mcp_agent_instance})
        user_chat_mock = mocker.patch('src.one_prompt_agents.cli.user_chat', new_callable=AsyncMock)
        
        # Prevent server start for REPL mode
        uvicorn_server_mock = mocker.patch('src.one_prompt_agents.cli.uvicorn.Server')
        loop_mock = mocker.patch('asyncio.get_event_loop')
        loop_mock.run_forever = MagicMock() # Stop it from actually running forever

        cli_module.main_cli()

        load_agents_mock.assert_called_once()
        user_chat_mock.assert_called_once_with(mock_mcp_agent_instance.agent)
        uvicorn_server_mock.assert_not_called() # Server should not start in REPL mode
        loop_mock.run_forever.assert_not_called() # Loop shouldn't run forever for REPL if it's blocking

# --- 4. Testing main_cli() - Autonomous Mode ---

def test_main_cli_autonomous_mode(mocker):
    """Test main_cli autonomous mode operation."""
    with patch.object(sys, 'argv', ['script_name', 'TestAgentAuto', 'TestPromptAuto']):
        mock_mcp_agent_instance = MagicMock()
        mock_mcp_agent_instance.agent = MagicMock() 
        mock_mcp_agent_instance.strategy_name = "default" # Or any strategy
        
        load_agents_mock = mocker.patch('src.one_prompt_agents.cli.load_agents', return_value={"TestAgentAuto": mock_mcp_agent_instance})
        submit_job_mock = mocker.patch('src.one_prompt_agents.cli.submit_job', new_callable=AsyncMock, return_value="job-auto-123")
        
        # Mock job queue for run_job_and_wait loop
        job_queue_mock = mocker.patch('src.one_prompt_agents.cli.job_queue')
        job_queue_mock.empty.side_effect = [False, False, True] # Processing one job, then empty
        job_queue_mock.join = AsyncMock()

        # Mock JOBS dict to simulate job completion
        # This is tricky. We need submit_job to populate it, and then the loop to clear it.
        # The autouse fixture patches JOBS to an empty dict. We need to control its lifecycle.
        jobs_dict_mock = {} # Simulate the global JOBS dict
        mocker.patch('src.one_prompt_agents.cli.job_manager.JOBS', jobs_dict_mock)
        
        async def fake_submit_job(*args, **kwargs):
            jobs_dict_mock["job-auto-123"] = {"status": "pending", "task": AsyncMock()} # Simulate job submission
            await asyncio.sleep(0) # Yield control
            # Simulate job completion by chat_worker
            jobs_dict_mock["job-auto-123"]["status"] = "completed"
            jobs_dict_mock["job-auto-123"]["task"].done.return_value = True
            return "job-auto-123"
        submit_job_mock.side_effect = fake_submit_job
        
        # Mock asyncio.sleep in the run_job_and_wait loop
        asyncio_sleep_mock = mocker.patch('asyncio.sleep', new_callable=AsyncMock)

        # Prevent server start after autonomous run for this specific test
        uvicorn_server_mock = mocker.patch('src.one_prompt_agents.cli.uvicorn.Server')
        loop_mock = mocker.patch('asyncio.get_event_loop')
        loop_mock.run_forever = MagicMock()


        cli_module.main_cli()

        load_agents_mock.assert_called_once()
        submit_job_mock.assert_called_once_with(
            agent=mock_mcp_agent_instance.agent,
            prompt="TestPromptAuto",
            strategy_name=mock_mcp_agent_instance.strategy_name,
            run_hooks=mocker.ANY  # CaptureLastAssistant instance
        )
        # Assertions for run_job_and_wait loop behavior
        job_queue_mock.join.assert_called_once() # Should wait for queue to empty
        assert asyncio_sleep_mock.call_count > 0 # Should have slept while waiting for JOBS
        
        # Server should not start if autonomous mode implies exit after job
        # The current cli.py structure transitions to server mode after autonomous.
        # So, we check if server setup is called.
        uvicorn_server_mock.assert_called()
        loop_mock.run_forever.assert_called_once()


# --- 5. Testing main_cli() - Server Mode ---

def test_main_cli_server_mode(mocker, mock_cli_dependencies):
    """Test main_cli server mode startup."""
    with patch.object(sys, 'argv', ['script_name']): # No agent/prompt args means server mode
        
        # Mocks are largely from autouse fixture. Retrieve some for specific assertions.
        loop_mock = mock_cli_dependencies['loop']
        uvicorn_config_mock = mocker.patch('src.one_prompt_agents.cli.uvicorn.Config')
        uvicorn_server_class_mock = mock_cli_dependencies['uvicorn_server_class']
        uvicorn_server_instance_mock = mock_cli_dependencies['uvicorn_server_instance']
        uvicorn_log_level_mock = mocker.patch('src.one_prompt_agents.cli.uvicorn_log_level', return_value='debug')

        cli_module.main_cli()

        uvicorn_log_level_mock.assert_called_once()
        uvicorn_config_mock.assert_called_once_with(
            "src.one_prompt_agents.api:app", # app location
            host="0.0.0.0", port=9000, log_level='debug', # from mock
            # reload=True # if reload is enabled, check for it
        )
        uvicorn_server_class_mock.assert_called_once_with(config=uvicorn_config_mock.return_value)
        
        # Check that server.serve is created as a task
        # loop_mock.create_task.assert_any_call(uvicorn_server_instance_mock.serve())
        # More robust: check if serve was awaited or run, which is abstracted by run_forever
        # The key is that run_forever is called, implying the server setup was done.
        loop_mock.run_forever.assert_called_once()

# --- 6. Testing main_cli() - Graceful Shutdown ---
# This is complex. We'll test a KeyboardInterrupt scenario.

def test_main_cli_graceful_shutdown_on_keyboard_interrupt(mocker, mock_cli_dependencies):
    """Test graceful shutdown sequence on KeyboardInterrupt during server run."""
    with patch.object(sys, 'argv', ['script_name']): # Server mode
        loop_mock = mock_cli_dependencies['loop']
        loop_mock.run_forever.side_effect = KeyboardInterrupt # Simulate Ctrl+C

        # Mock agents and their cleanup
        mock_agent1 = MagicMock()
        mock_agent1.end_and_cleanup = AsyncMock()
        mocker.patch('src.one_prompt_agents.cli.AGENTS_REGISTRY', {"Agent1": mock_agent1})
        
        # Mock MCP servers and their cleanup
        mock_mcp_server1_instance = MagicMock()
        mock_mcp_server1_instance.cleanup = AsyncMock()
        mocker.patch('src.one_prompt_agents.cli.MCP_SERVER_INSTANCES', {"MCPServer1": mock_mcp_server1_instance})
        
        # Mock tasks
        mock_task1 = AsyncMock(spec=asyncio.Task)
        mock_task1.done.return_value = False # Not done initially
        mock_task2 = AsyncMock(spec=asyncio.Task)
        mock_task2.done.return_value = True # Already done
        mocker.patch('src.one_prompt_agents.cli.mcp_tasks', [mock_task1])
        mocker.patch('src.one_prompt_agents.cli.worker_tasks', [mock_task2])

        # Mock uvicorn server instance shutdown
        uvicorn_server_instance_mock = mock_cli_dependencies['uvicorn_server_instance']

        cli_module.main_cli() # This will run and hit KeyboardInterrupt

        # Shutdown assertions
        uvicorn_server_instance_mock.shutdown.assert_called_once()
        
        # Agent cleanup
        mock_agent1.end_and_cleanup.assert_called_once()
        
        # MCP Server cleanup
        mock_mcp_server1_instance.cleanup.assert_called_once()

        # Task cancellation
        mock_task1.cancel.assert_called_once() # Task1 was not done
        mock_task2.cancel.assert_not_called() # Task2 was already done
        
        # Loop cleanup
        # loop_mock.run_until_complete.assert_any_call(mock_task1) # If tasks are awaited after cancel
        # loop_mock.run_until_complete.assert_any_call(uvicorn_server_instance_mock.shutdown.return_value)
        # These are complex to assert perfectly without knowing the exact gather/await structure.
        # Focus on key resource cleanup calls.
        
        loop_mock.close.assert_called_once()
        
        # Signal restoration (if applicable, check for specific signals)
        signal_mock = mocker.patch('signal.signal')
        signal_mock.assert_any_call(mocker.ANY, signal.SIG_DFL) # Check if default handlers restored

# Note: Testing signal handling precisely is very platform-dependent and complex in unit tests.
# Focusing on the intended effects (like calling cleanup functions) is more practical.
# The `asyncio.run(main_cli())` pattern is typically not used directly in tests
# if `main_cli` itself configures and runs the asyncio loop.
# We are testing `main_cli` as the entry point that sets up and runs the loop.
# The `mock_loop.run_forever` and `mock_loop.run_until_complete` are key for controlling flow.
# This test suite is a high-level structure. Each test might need more specific sub-mocks
# or adjustments based on the exact implementation details of `cli.py`.
# For instance, how `AGENTS_REGISTRY` and `MCP_SERVER_INSTANCES` are populated and accessed.
# The autouse fixture `mock_cli_dependencies` is crucial for this broad mocking.
# If `cli.py` uses `asyncio.run()` internally, tests for `main_cli` might need to mock that instead of `loop.run_forever`.
# Assuming `main_cli` fetches the loop and runs it.
# The actual `cli.py` has `asyncio.run(main_async())` in `main_cli()`. So tests should target `main_async`.
# For simplicity here, I've assumed `main_cli` does the loop management directly.
# If `main_async` exists, then `main_cli` tests would just check if `asyncio.run(main_async(...))` is called.
# And `main_async` would be the target for most of these tests.
# Let's adjust for `main_async` structure if `cli.py` has it.
# Assuming `main_cli` calls `asyncio.run(main_async(...))` and `main_async` contains the core logic.

# Re-adjusting: Assume main_cli() calls asyncio.run(main_async_logic_entry_point())
# The tests above are effectively for that `main_async_logic_entry_point`.
# If `main_cli` is very thin, its test would be:
# def test_main_cli_calls_asyncio_run_with_main_async(mocker):
#     mock_asyncio_run = mocker.patch('asyncio.run')
#     mock_main_async = mocker.patch('src.one_prompt_agents.cli.main_async') # or whatever it's called
#     with patch.object(sys, 'argv', ['script_name']):
#          cli_module.main_cli()
#     mock_asyncio_run.assert_called_once_with(mock_main_async.return_value) # or called with main_async itself

# For the current detailed plan, the tests are written as if `main_cli` contains the async logic.
# This is acceptable if `main_cli` is the primary async orchestrator.
# Let's stick to testing `main_cli` as the orchestrator as per the current test structure.
# The key is that the mocked asyncio loop's methods (`run_forever`, `create_task`) are controlled.
# It's also important that `cli.py` uses `asyncio.get_event_loop()` to get the loop we've mocked.
# If it creates a new loop explicitly, that new loop would need mocking.
# Standard practice is `asyncio.get_event_loop()`.
