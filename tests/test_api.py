import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from pydantic import ValidationError # For testing RunRequest directly

# Module to be tested
from src.one_prompt_agents import api as api_module
from src.one_prompt_agents.api import app, RunRequest, set_agents_for_api
# from src.one_prompt_agents.mcp_agent import MCPAgent # For creating mock agent instances if needed

# Fixture to manage and restore the global 'agents' dictionary in api.py
@pytest.fixture(autouse=True)
def manage_api_agents_state():
    """Ensures api.agents is cleared before each test and restored afterwards."""
    original_agents = api_module.agents.copy()
    api_module.agents.clear()  # Start with a clean state
    yield
    api_module.agents = original_agents # Restore original state

@pytest.fixture
def client():
    """Provides a TestClient instance for making requests to the FastAPI app."""
    return TestClient(app)

# --- 1. Testing RunRequest (Pydantic Model) ---

def test_run_request_valid():
    """Test RunRequest with a valid prompt."""
    req = RunRequest(prompt="Hello world")
    assert req.prompt == "Hello world"

def test_run_request_empty_prompt():
    """Test RunRequest with an empty prompt string."""
    req = RunRequest(prompt="")
    assert req.prompt == ""

def test_run_request_missing_prompt_field():
    """Test RunRequest for ValidationError when 'prompt' field is missing."""
    with pytest.raises(ValidationError, match="Field required"):
        RunRequest(**{}) # Empty dict means 'prompt' is missing

def test_run_request_incorrect_data_type():
    """Test RunRequest for ValidationError when 'prompt' has incorrect data type."""
    with pytest.raises(ValidationError, match="Input should be a valid string"):
        RunRequest(prompt=123) # Prompt should be a string

# --- 2. Testing root() endpoint (GET "/") ---

def test_root_endpoint(client: TestClient):
    """Test the root health check endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Server is running"}

# --- 3. Testing run_agent_endpoint(agent_name: str, req: RunRequest) (POST "/{agent_name}/run") ---

@patch('src.one_prompt_agents.api.start_agent', new_callable=AsyncMock)
def test_run_agent_endpoint_successful_run(mock_start_agent: AsyncMock, client: TestClient):
    """Test successful agent run: agent found, valid request, start_agent called."""
    mock_agent_instance = MagicMock()
    # MCPAgent could be used here for spec if more detailed mocking is needed:
    # mock_agent_instance = MagicMock(spec=MCPAgent)
    set_agents_for_api({"test_agent": mock_agent_instance})
    
    mock_start_agent.return_value = None # start_agent is fire-and-forget

    response = client.post("/test_agent/run", json={"prompt": "Test prompt"})

    assert response.status_code == 200
    assert response.json() == {"status": "started", "agent": "test_agent"}
    mock_start_agent.assert_called_once_with(mock_agent_instance, "Test prompt")

@patch('src.one_prompt_agents.api.start_agent', new_callable=AsyncMock)
def test_run_agent_endpoint_agent_not_found(mock_start_agent: AsyncMock, client: TestClient):
    """Test response when the requested agent name is not found."""
    set_agents_for_api({}) # Ensure no agents are loaded

    response = client.post("/unknown_agent/run", json={"prompt": "Test prompt"})

    assert response.status_code == 422 # FastAPI validation error for path param
    # The error message comes from a custom validation in the endpoint now for agent existence
    # Before, it might have been a 404 if not for the custom check.
    # Let's check if the detail contains the agent name.
    # Based on current api.py, it should be a 422 from the dependency if agent_name is not in api.agents
    assert "Unknown agent unknown_agent" in response.json()["detail"][0]["msg"] # Pydantic/FastAPI detail format
    mock_start_agent.assert_not_called()

@patch('src.one_prompt_agents.api.start_agent', new_callable=AsyncMock)
def test_run_agent_endpoint_invalid_request_body(mock_start_agent: AsyncMock, client: TestClient):
    """Test response when the request body is invalid (e.g., missing 'prompt')."""
    set_agents_for_api({"test_agent": MagicMock()})

    response = client.post("/test_agent/run", json={"wrong_field": "data"}) # 'prompt' is missing

    assert response.status_code == 422 # FastAPI/Pydantic validation error
    assert "Field required" in response.json()["detail"][0]["msg"]
    assert "prompt" in response.json()["detail"][0]["loc"]
    mock_start_agent.assert_not_called()

@patch('src.one_prompt_agents.api.start_agent', new_callable=AsyncMock)
def test_run_agent_endpoint_start_agent_raises_exception(mock_start_agent: AsyncMock, client: TestClient):
    """Test 500 response when start_agent function raises an unexpected exception."""
    mock_agent_instance = MagicMock()
    set_agents_for_api({"test_agent": mock_agent_instance})
    
    mock_start_agent.side_effect = Exception("Agent failed spectacularly")

    response = client.post("/test_agent/run", json={"prompt": "Test prompt"})

    assert response.status_code == 500
    assert "Error starting agent test_agent: Agent failed spectacularly" in response.json()["detail"]
    mock_start_agent.assert_called_once_with(mock_agent_instance, "Test prompt")


@patch('src.one_prompt_agents.api.start_agent', new_callable=AsyncMock)
def test_run_agent_endpoint_agent_instance_is_none(mock_start_agent: AsyncMock, client: TestClient):
    """Test 500 response if the looked-up agent instance is None (internal error)."""
    set_agents_for_api({"test_agent": None}) # Agent name exists, but instance is None

    response = client.post("/test_agent/run", json={"prompt": "Test prompt"})

    assert response.status_code == 500
    # This error detail comes from the custom `get_agent_or_raise` dependency
    assert "Internal error retrieving agent test_agent" in response.json()["detail"]
    mock_start_agent.assert_not_called()

# --- 4. Testing set_agents_for_api(loaded_agents: dict) ---

def test_set_agents_for_api_set_new_agents():
    """Test setting new agents into the api.agents dictionary."""
    # The manage_api_agents_state fixture ensures api_module.agents is already empty
    assert api_module.agents == {} 
    
    mock_agent_A = MagicMock()
    new_agents = {"agent1": mock_agent_A}
    set_agents_for_api(new_agents)
    
    assert api_module.agents == new_agents
    assert api_module.agents["agent1"] == mock_agent_A

def test_set_agents_for_api_update_overwrite_agents():
    """Test updating and overwriting agents in api.agents."""
    initial_agent1_mock = MagicMock(name="InitialAgent1")
    set_agents_for_api({"agent1": initial_agent1_mock, "existing_agent": MagicMock()})
    
    updated_agent1_mock = MagicMock(name="UpdatedAgent1")
    agent2_mock = MagicMock(name="Agent2")
    
    update_payload = {"agent1": updated_agent1_mock, "agent2": agent2_mock}
    set_agents_for_api(update_payload)
    
    # Should overwrite agent1 and add agent2, other existing agents removed
    assert len(api_module.agents) == 2
    assert api_module.agents["agent1"] == updated_agent1_mock
    assert api_module.agents["agent2"] == agent2_mock
    assert "existing_agent" not in api_module.agents


def test_set_agents_for_api_clear_agents():
    """Test clearing all agents by setting an empty dictionary."""
    set_agents_for_api({"agent1": MagicMock(), "agent2": MagicMock()})
    assert len(api_module.agents) == 2
    
    set_agents_for_api({}) # Set to empty
    
    assert api_module.agents == {}

# Final checks on imports and mocks:
# - `AsyncMock` is used for `start_agent`.
# - `TestClient` is used for endpoint testing.
# - `api_module.agents` is correctly managed by the fixture and tests.
# - `RunRequest` is correctly imported and tested.
# - Paths for patching are correct.
# - The `manage_api_agents_state` fixture with `autouse=True` should handle setup/teardown for most tests.
#   Tests for `set_agents_for_api` might implicitly rely on this or explicitly clear/set as needed.
#   The current `manage_api_agents_state` clears `api_module.agents` before each test,
#   which is good for isolation.
