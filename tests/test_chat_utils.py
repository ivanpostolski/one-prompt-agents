import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import io
import logging # For checking log messages

from src.one_prompt_agents.chat_utils import (
    spinner,
    CaptureLastAssistant,
    connect_mcps,
    SPINNER_FRAMES,
)
from agents.hooks import RunHooks # Base class for CaptureLastAssistant


# --- 1. Testing spinner(text: str = "") (async context manager) ---

@pytest.mark.asyncio
@patch('src.one_prompt_agents.chat_utils.sys.stdout', new_callable=io.StringIO)
async def test_spinner_displays_text_animates_and_cleans_up(mock_stdout):
    """Test spinner displays text, shows frames (mocked animation), and cleans up."""
    stop_event = asyncio.Event()
    
    async def mock_wait_for(fut, timeout):
        # Simulate a few animation cycles then stop
        if mock_wait_for.call_count < 3: # Allow 2 frames to print
            mock_wait_for.call_count += 1
            raise asyncio.TimeoutError # To cycle the spinner's internal loop
        else:
            # Allow the spinner to exit its loop naturally
            # This requires the future being waited on (stop_event.wait()) to complete.
            # We achieve this by setting the event from outside or by modifying this mock.
            # For this test, we'll let it proceed after a few timeouts.
            # The spinner's stop_event.wait() will eventually complete if stop_event is set.
            # Or, if the spinner's main task is cancelled, it also stops.
            # Here, we'll just let the original future (stop.wait()) proceed.
            # If the spinner's loop condition depends on `not stop.is_set()`,
            # then we'd need to arrange for `stop.set()` to be called.
            # The spinner implementation uses `asyncio.wait_for(stop.wait(), timeout=0.1)`
            # so we need `stop.wait()` to eventually complete.
            # We can simulate this by making `stop.wait()` return after some calls.
            # Let's assume the context manager sets the stop event.
            await asyncio.sleep(0.001) # Simulate work within the context
            return await fut # Allow original future to proceed
    mock_wait_for.call_count = 0

    with patch('src.one_prompt_agents.chat_utils.asyncio.wait_for', side_effect=mock_wait_for) as mock_async_wait_for:
        async with spinner("Loading..."):
            await asyncio.sleep(0.01) # Simulate some work being done
            # The spinner's stop event is set upon exiting the 'async with' block.

    output = mock_stdout.getvalue()
    
    # Check for initial text and spinner frame
    assert f"\r{SPINNER_FRAMES[0]} Loading..." in output
    # Check for subsequent spinner frame (depends on mock_wait_for call_count)
    assert f"\r{SPINNER_FRAMES[1]} Loading..." in output
    # Check for cleanup
    assert output.endswith("\r\033[2K\r")
    # Ensure wait_for was called multiple times (for animation)
    assert mock_async_wait_for.call_count >= 2


@pytest.mark.asyncio
@patch('src.one_prompt_agents.chat_utils.sys.stdout', new_callable=io.StringIO)
async def test_spinner_with_empty_text(mock_stdout):
    """Test spinner with empty text, ensuring correct formatting."""
    with patch('src.one_prompt_agents.chat_utils.asyncio.wait_for') as mock_async_wait_for:
        # Make wait_for behave as if it times out once, then allows stop.wait()
        mock_async_wait_for.side_effect = [asyncio.TimeoutError, None] # Timeout, then stop
        
        async with spinner(""): # Empty text
            await asyncio.sleep(0.01)

    output = mock_stdout.getvalue()
    assert f"\r{SPINNER_FRAMES[0]} " in output # Note the space after frame if text is empty
    assert output.endswith("\r\033[2K\r")


@pytest.mark.asyncio
@patch('src.one_prompt_agents.chat_utils.sys.stdout', new_callable=io.StringIO)
async def test_spinner_handles_exception_in_context(mock_stdout):
    """Test that spinner cleans up stdout even if an exception occurs in its context."""
    with patch('src.one_prompt_agents.chat_utils.asyncio.wait_for', side_effect=asyncio.TimeoutError): # Keep spinning
        with pytest.raises(ValueError, match="Test exception"):
            async with spinner("Working..."):
                await asyncio.sleep(0.01)
                raise ValueError("Test exception")

    output = mock_stdout.getvalue()
    assert output.endswith("\r\033[2K\r") # Crucial: cleanup must happen

# --- 2. Testing CaptureLastAssistant(RunHooks) (Class) ---

def test_capture_last_assistant_init():
    """Test CaptureLastAssistant initialization."""
    hook = CaptureLastAssistant()
    assert hook.history == []
    assert isinstance(hook, RunHooks) # Check inheritance

@pytest.mark.asyncio
async def test_capture_last_assistant_on_generation_end_with_content():
    """Test on_generation_end captures messages with .output.content."""
    hook = CaptureLastAssistant()
    mock_item = MagicMock()
    mock_item.output.content = "Assistant response"
    
    with patch('src.one_prompt_agents.chat_utils.logger.info') as mock_logger_info:
        await hook.on_generation_end(mock_item, None)
    
    assert len(hook.history) == 1
    assert hook.history[0] == "Assistant response"
    mock_logger_info.assert_called_with("[CAPTURE HOOK] Generation ended.")

@pytest.mark.asyncio
async def test_capture_last_assistant_on_generation_end_simple_output():
    """Test on_generation_end captures messages with simple .output string."""
    hook = CaptureLastAssistant()
    mock_item = MagicMock()
    mock_item.output = "Simple string output" # No .content attribute

    with patch('src.one_prompt_agents.chat_utils.logger.info') as mock_logger_info:
        await hook.on_generation_end(mock_item, None)

    assert len(hook.history) == 1
    assert hook.history[0] == "Simple string output"
    mock_logger_info.assert_called_with("[CAPTURE HOOK] Generation ended.")


@pytest.mark.asyncio
async def test_capture_last_assistant_on_tool_start():
    """Test on_tool_start logs tool name."""
    hook = CaptureLastAssistant()
    mock_tool = MagicMock()
    mock_tool.name = "calculator_tool"

    # Patch the logger specifically in the chat_utils module
    with patch('src.one_prompt_agents.chat_utils.logger.info') as mock_chat_utils_logger_info:
        await hook.on_tool_start(MagicMock(), MagicMock(), mock_tool) # agent_run and tool_input are not used by this hook

    mock_chat_utils_logger_info.assert_any_call("[CAPTURE HOOK] Tool started: calculator_tool")


# --- 3. Testing connect_mcps(agent: Any, retries: int = 3) (async function) ---

@pytest.mark.asyncio
@patch('src.one_prompt_agents.chat_utils.logger') # Patch the logger object
@patch('src.one_prompt_agents.chat_utils.asyncio.sleep', new_callable=AsyncMock) # Mock sleep
async def test_connect_mcps_no_servers(mock_sleep: AsyncMock, mock_logger: MagicMock):
    """Test connect_mcps when the agent has no MCP servers listed."""
    mock_agent = MagicMock()
    mock_agent.name = "TestAgentNoServers"
    mock_agent.mcp_servers = []

    await connect_mcps(mock_agent, retries=3)
    
    mock_logger.info.assert_any_call("Agent TestAgentNoServers has no MCP servers to connect.")
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
@patch('src.one_prompt_agents.chat_utils.logger')
@patch('src.one_prompt_agents.chat_utils.asyncio.sleep', new_callable=AsyncMock)
async def test_connect_mcps_one_server_connects_first_try(mock_sleep: AsyncMock, mock_logger: MagicMock):
    """Test one server connecting on the first attempt."""
    mock_agent = MagicMock()
    mock_agent.name = "TestAgentOneServer"
    mock_mcp_server = MagicMock()
    mock_mcp_server.name = "ServerA"
    mock_mcp_server.connect = AsyncMock(return_value=None) # Successful connection
    mock_agent.mcp_servers = [mock_mcp_server]

    await connect_mcps(mock_agent, retries=3)

    mock_mcp_server.connect.assert_called_once()
    mock_logger.info.assert_any_call("Connecting to MCP server ServerA for agent TestAgentOneServer...")
    mock_logger.info.assert_any_call("Successfully connected to ServerA for TestAgentOneServer.")
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
@patch('src.one_prompt_agents.chat_utils.logger')
@patch('src.one_prompt_agents.chat_utils.asyncio.sleep', new_callable=AsyncMock)
async def test_connect_mcps_one_server_connects_after_retries(mock_sleep: AsyncMock, mock_logger: MagicMock):
    """Test a server connecting successfully after a few retries."""
    mock_agent = MagicMock()
    mock_agent.name = "TestAgentRetrySuccess"
    mock_mcp_server = MagicMock()
    mock_mcp_server.name = "ServerB"
    mock_mcp_server.connect = AsyncMock(side_effect=[
        Exception("Connection failed 1"), 
        Exception("Connection failed 2"), 
        None # Success on 3rd try
    ])
    mock_agent.mcp_servers = [mock_mcp_server]

    await connect_mcps(mock_agent, retries=3)

    assert mock_mcp_server.connect.call_count == 3
    assert mock_sleep.call_count == 2 # Sleep after 1st and 2nd failures
    mock_logger.warning.assert_any_call("Failed to connect to ServerB (attempt 1/3) for TestAgentRetrySuccess. Retrying in 1s... Error: Connection failed 1")
    mock_logger.warning.assert_any_call("Failed to connect to ServerB (attempt 2/3) for TestAgentRetrySuccess. Retrying in 1s... Error: Connection failed 2")
    mock_logger.info.assert_any_call("Successfully connected to ServerB for TestAgentRetrySuccess.")


@pytest.mark.asyncio
@patch('src.one_prompt_agents.chat_utils.logger')
@patch('src.one_prompt_agents.chat_utils.asyncio.sleep', new_callable=AsyncMock)
async def test_connect_mcps_one_server_all_retries_fail(mock_sleep: AsyncMock, mock_logger: MagicMock):
    """Test a server failing to connect after all retries."""
    mock_agent = MagicMock()
    mock_agent.name = "TestAgentRetryFail"
    mock_mcp_server = MagicMock()
    mock_mcp_server.name = "ServerC"
    final_exception = Exception("Connection failed definitively")
    mock_mcp_server.connect = AsyncMock(side_effect=[
        Exception("Fail1"), Exception("Fail2"), final_exception
    ])
    mock_agent.mcp_servers = [mock_mcp_server]

    with pytest.raises(Exception, match="Connection failed definitively"):
        await connect_mcps(mock_agent, retries=3)

    assert mock_mcp_server.connect.call_count == 3
    assert mock_sleep.call_count == 2
    mock_logger.error.assert_any_call("Failed to connect to ServerC for TestAgentRetryFail after 3 attempts. Last error: Connection failed definitively")


@pytest.mark.asyncio
@patch('src.one_prompt_agents.chat_utils.logger')
@patch('src.one_prompt_agents.chat_utils.asyncio.sleep', new_callable=AsyncMock)
async def test_connect_mcps_multiple_servers_all_connect(mock_sleep: AsyncMock, mock_logger: MagicMock):
    """Test multiple MCP servers, all connecting successfully."""
    mock_agent = MagicMock()
    mock_agent.name = "TestAgentMultiSuccess"
    
    server1 = MagicMock()
    server1.name = "ServerX"
    server1.connect = AsyncMock(return_value=None)
    
    server2 = MagicMock()
    server2.name = "ServerY"
    server2.connect = AsyncMock(return_value=None)
    
    mock_agent.mcp_servers = [server1, server2]

    await connect_mcps(mock_agent, retries=2)

    server1.connect.assert_called_once()
    server2.connect.assert_called_once()
    mock_logger.info.assert_any_call("Successfully connected to ServerX for TestAgentMultiSuccess.")
    mock_logger.info.assert_any_call("Successfully connected to ServerY for TestAgentMultiSuccess.")
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
@patch('src.one_prompt_agents.chat_utils.logger')
@patch('src.one_prompt_agents.chat_utils.asyncio.sleep', new_callable=AsyncMock)
async def test_connect_mcps_multiple_servers_one_fails_all_retries(mock_sleep: AsyncMock, mock_logger: MagicMock):
    """Test with multiple servers where one fails all connection retries."""
    mock_agent = MagicMock()
    mock_agent.name = "TestAgentMultiOneFails"

    server_ok = MagicMock()
    server_ok.name = "ServerOK"
    server_ok.connect = AsyncMock(return_value=None)

    server_fail = MagicMock()
    server_fail.name = "ServerFAIL"
    final_exception = Exception("ServerFAIL ultimate connection error")
    server_fail.connect = AsyncMock(side_effect=[Exception("f1"), final_exception])
    
    mock_agent.mcp_servers = [server_ok, server_fail]

    with pytest.raises(Exception, match="ServerFAIL ultimate connection error"):
        await connect_mcps(mock_agent, retries=2) # server_fail will try twice

    server_ok.connect.assert_called_once() # Should still try to connect to this one
    mock_logger.info.assert_any_call("Successfully connected to ServerOK for TestAgentMultiOneFails.")
    assert server_fail.connect.call_count == 2
    mock_logger.error.assert_any_call("Failed to connect to ServerFAIL for TestAgentMultiOneFails after 2 attempts. Last error: ServerFAIL ultimate connection error")
    # Sleep would be called for server_fail's retry
    mock_sleep.assert_called_once()


@pytest.mark.asyncio
@patch('src.one_prompt_agents.chat_utils.logger')
@patch('src.one_prompt_agents.chat_utils.asyncio.sleep', new_callable=AsyncMock)
async def test_connect_mcps_connect_timeout(mock_sleep: AsyncMock, mock_logger: MagicMock):
    """Test connection attempt timing out (simulated by asyncio.TimeoutError from connect)."""
    mock_agent = MagicMock()
    mock_agent.name = "TestAgentTimeout"
    mock_mcp_server = MagicMock()
    mock_mcp_server.name = "ServerTimeout"
    # The actual asyncio.TimeoutError would be raised by `asyncio.wait_for` within `connect_mcps`
    # if `mcp_server.connect()` itself hangs. Here, we directly make `connect` raise it.
    mock_mcp_server.connect = AsyncMock(side_effect=[
        asyncio.TimeoutError("Connect timed out 1"),
        asyncio.TimeoutError("Connect timed out 2")
    ])
    mock_agent.mcp_servers = [mock_mcp_server]

    with pytest.raises(asyncio.TimeoutError, match="Connect timed out 2"): # Expect the last error to propagate
        await connect_mcps(mock_agent, retries=2)

    assert mock_mcp_server.connect.call_count == 2
    assert mock_sleep.call_count == 1 # Sleep after the first timeout
    mock_logger.warning.assert_any_call("Failed to connect to ServerTimeout (attempt 1/2) for TestAgentTimeout. Retrying in 1s... Error: Connect timed out 1")
    mock_logger.error.assert_any_call("Failed to connect to ServerTimeout for TestAgentTimeout after 2 attempts. Last error: Connect timed out 2")

# Ensure that RunHooks is a suitable base if it has abstract methods (it doesn't seem to)
# class TestRunHooks(RunHooks):
#     async def on_generation_start(self, agent_run, prompt): pass
#     async def on_generation_end(self, agent_run, item): pass
#     async def on_tool_start(self, agent_run, tool_input, tool): pass
#     async def on_tool_end(self, agent_run, item, tool_result): pass
# This check is mostly for completeness; CaptureLastAssistant only implements what it needs.
# The `agents` library's RunHooks is designed for selective overriding.
# CaptureLastAssistant doesn't call super().__init__(), which is fine if RunHooks.__init__ is empty or not critical.
# Assuming RunHooks is a simple interface/grouping class.
