import pytest
import json
from pathlib import Path
from pydantic import ValidationError
from unittest.mock import patch, MagicMock, mock_open

# Import functions and classes from the module to be tested
from src.one_prompt_agents.agents_loader import (
    AgentConfig,
    discover_configs,
    topo_sort,
    import_module_from_path,
    load_agents,
)
# We might need to mock MCPAgent later in load_agents tests
# from src.one_prompt_agents.mcp_agent import MCPAgent


# --- 1. Testing AgentConfig (Pydantic Model) ---

def test_agent_config_valid_minimal():
    data = {
        "name": "TestAgent",
        "prompt_file": "prompt.txt",
        "return_type": "TestReturn",
        "inputs_description": "Some input",
        "tools": []
    }
    config = AgentConfig(**data)
    assert config.name == "TestAgent"
    assert config.prompt_file == "prompt.txt"
    assert config.return_type == "TestReturn"
    assert config.inputs_description == "Some input"
    assert config.tools == []
    assert config.model is None # Optional, should be None if not provided
    assert config.strategy_name == "default" # Default value

def test_agent_config_valid_all_fields():
    data = {
        "name": "FullAgent",
        "prompt_file": "full_prompt.md",
        "return_type": "FullReturn",
        "inputs_description": "Detailed input",
        "tools": ["ToolA", "ToolB"],
        "model": "gpt-4",
        "strategy_name": "custom_strategy"
    }
    config = AgentConfig(**data)
    assert config.name == "FullAgent"
    assert config.prompt_file == "full_prompt.md"
    assert config.return_type == "FullReturn"
    assert config.inputs_description == "Detailed input"
    assert config.tools == ["ToolA", "ToolB"]
    assert config.model == "gpt-4"
    assert config.strategy_name == "custom_strategy"

def test_agent_config_missing_required_fields():
    required_fields = ["name", "prompt_file", "return_type", "inputs_description", "tools"]
    base_data = {
        "name": "Test", "prompt_file": "p.txt", "return_type": "R",
        "inputs_description": "desc", "tools": []
    }
    for field in required_fields:
        data = base_data.copy()
        del data[field]
        with pytest.raises(ValidationError):
            AgentConfig(**data)

def test_agent_config_incorrect_data_types():
    # Test tools not a list
    with pytest.raises(ValidationError):
        AgentConfig(name="N", prompt_file="p.txt", return_type="R", inputs_description="d", tools="not_a_list")
    # Test name not a string
    with pytest.raises(ValidationError):
        AgentConfig(name=123, prompt_file="p.txt", return_type="R", inputs_description="d", tools=[])
    # Test model not a string (if provided)
    with pytest.raises(ValidationError):
        AgentConfig(name="N", prompt_file="p.txt", return_type="R", inputs_description="d", tools=[], model=123)
    # Test strategy_name not a string (if provided)
    with pytest.raises(ValidationError):
        AgentConfig(name="N", prompt_file="p.txt", return_type="R", inputs_description="d", tools=[], strategy_name=456)


def test_agent_config_default_strategy_name():
    data = {
        "name": "DefaultStrategyAgent",
        "prompt_file": "prompt.txt",
        "return_type": "Return",
        "inputs_description": "Input desc",
        "tools": []
    }
    config = AgentConfig(**data)
    assert config.strategy_name == "default"

def test_agent_config_path_attribute():
    data = {
        "name": "PathAgent", "prompt_file": "p.txt", "return_type": "R",
        "inputs_description": "d", "tools": []
    }
    config = AgentConfig(**data)
    # _path is a private attribute, usually set by discover_configs
    # We check it can exist, but its direct setting isn't part of normal construction
    assert not hasattr(config, "_path") # Should not be there by default
    config._path = Path("some/path")
    assert config._path == Path("some/path")


# --- 2. Testing discover_configs(agents_dir: Path) -> Dict[str, AgentConfig] ---

def test_discover_configs_no_agents(tmp_path: Path):
    agents_dir = tmp_path / "agents_config"
    agents_dir.mkdir()
    configs = discover_configs(agents_dir)
    assert configs == {}

def test_discover_configs_one_valid_agent(tmp_path: Path):
    agents_dir = tmp_path / "agents_data"
    agents_dir.mkdir()
    agent_a_dir = agents_dir / "agent_A"
    agent_a_dir.mkdir()
    config_data = {
        "name": "AgentA_from_file", "prompt_file": "a.txt", "return_type": "AReturn",
        "inputs_description": "A desc", "tools": []
    }
    with open(agent_a_dir / "config.json", "w") as f:
        json.dump(config_data, f)

    configs = discover_configs(agents_dir)
    assert len(configs) == 1
    assert "AgentA_from_file" in configs
    agent_config = configs["AgentA_from_file"]
    assert agent_config.name == "AgentA_from_file"
    assert agent_config._path == Path("agent_A") # Relative path to agents_dir
    assert agent_config.strategy_name == "default" # Default value check

def test_discover_configs_multiple_valid_agents(tmp_path: Path):
    agents_dir = tmp_path / "multi_agents"
    agents_dir.mkdir()
    # Agent X
    agent_x_dir = agents_dir / "agent_X"
    agent_x_dir.mkdir()
    config_x_data = {"name": "AgentX", "prompt_file": "x.txt", "return_type": "XReturn", "inputs_description": "X", "tools": []}
    with open(agent_x_dir / "config.json", "w") as f:
        json.dump(config_x_data, f)
    # Agent Y
    agent_y_dir = agents_dir / "agent_Y"
    agent_y_dir.mkdir()
    config_y_data = {"name": "AgentY", "prompt_file": "y.txt", "return_type": "YReturn", "inputs_description": "Y", "tools": ["AgentX"], "strategy_name": "special"}
    with open(agent_y_dir / "config.json", "w") as f:
        json.dump(config_y_data, f)

    configs = discover_configs(agents_dir)
    assert len(configs) == 2
    assert "AgentX" in configs
    assert "AgentY" in configs
    assert configs["AgentX"]._path == Path("agent_X")
    assert configs["AgentY"]._path == Path("agent_Y")
    assert configs["AgentY"].strategy_name == "special"

def test_discover_configs_agent_with_missing_config_json(tmp_path: Path):
    agents_dir = tmp_path / "no_json_agents"
    agents_dir.mkdir()
    agent_b_dir = agents_dir / "agent_B" # No config.json here
    agent_b_dir.mkdir()
    configs = discover_configs(agents_dir)
    assert configs == {}

def test_discover_configs_agent_with_malformed_config_json(tmp_path: Path):
    agents_dir = tmp_path / "bad_json_agents"
    agents_dir.mkdir()
    agent_c_dir = agents_dir / "agent_C"
    agent_c_dir.mkdir()
    with open(agent_c_dir / "config.json", "w") as f:
        f.write("{'name': 'AgentC', 'prompt_file': 'c.txt'") # Malformed JSON

    with pytest.raises(json.JSONDecodeError):
        discover_configs(agents_dir)

def test_discover_configs_agent_with_invalid_config_data(tmp_path: Path):
    agents_dir = tmp_path / "invalid_data_agents"
    agents_dir.mkdir()
    agent_d_dir = agents_dir / "agent_D"
    agent_d_dir.mkdir()
    config_data = {"name": "AgentD"} # Missing required fields
    with open(agent_d_dir / "config.json", "w") as f:
        json.dump(config_data, f)

    with pytest.raises(ValidationError):
        discover_configs(agents_dir)

# --- 3. Testing topo_sort(configs: Dict[str, AgentConfig]) ---

def test_topo_sort_no_dependencies():
    configs = {
        "A": AgentConfig(name="A", prompt_file="p", return_type="R", inputs_description="d", tools=[]),
        "B": AgentConfig(name="B", prompt_file="p", return_type="R", inputs_description="d", tools=[]),
    }
    sorted_order = topo_sort(configs)
    assert sorted(sorted_order) == sorted(["A", "B"]) # Order can vary

def test_topo_sort_simple_linear_dependency():
    configs = {
        "A": AgentConfig(name="A", prompt_file="p", return_type="R", inputs_description="d", tools=["B"]),
        "B": AgentConfig(name="B", prompt_file="p", return_type="R", inputs_description="d", tools=[]),
    }
    sorted_order = topo_sort(configs)
    assert sorted_order == ["B", "A"]

def test_topo_sort_multiple_dependencies():
    configs = {
        "A": AgentConfig(name="A", prompt_file="p", return_type="R", inputs_description="d", tools=["B", "C"]),
        "B": AgentConfig(name="B", prompt_file="p", return_type="R", inputs_description="d", tools=[]),
        "C": AgentConfig(name="C", prompt_file="p", return_type="R", inputs_description="d", tools=[]),
    }
    sorted_order = topo_sort(configs)
    assert sorted_order[-1] == "A"
    assert "B" in sorted_order[:-1]
    assert "C" in sorted_order[:-1]
    assert len(sorted_order) == 3

def test_topo_sort_transitive_dependencies():
    configs = {
        "A": AgentConfig(name="A", prompt_file="p", return_type="R", inputs_description="d", tools=["B"]),
        "B": AgentConfig(name="B", prompt_file="p", return_type="R", inputs_description="d", tools=["C"]),
        "C": AgentConfig(name="C", prompt_file="p", return_type="R", inputs_description="d", tools=[]),
    }
    sorted_order = topo_sort(configs)
    assert sorted_order == ["C", "B", "A"]

def test_topo_sort_cyclic_dependency():
    configs = {
        "A": AgentConfig(name="A", prompt_file="p", return_type="R", inputs_description="d", tools=["B"]),
        "B": AgentConfig(name="B", prompt_file="p", return_type="R", inputs_description="d", tools=["A"]),
    }
    with pytest.raises(ValueError, match="Graph contains a cycle"):
        topo_sort(configs)

def test_topo_sort_self_dependency():
    configs = {
        "A": AgentConfig(name="A", prompt_file="p", return_type="R", inputs_description="d", tools=["A"]),
    }
    with pytest.raises(ValueError, match="Graph contains a cycle"): # Or "Agent cannot depend on itself" if specific check
        topo_sort(configs)

def test_topo_sort_dependency_on_non_existent_agent():
    # If a tool listed in "tools" does not correspond to a key in the `configs` dict,
    # it means it's a dependency on an external tool/server, not another agent from this set.
    # The current topo_sort implementation should ignore these for sorting internal agents.
    configs = {
        "A": AgentConfig(name="A", prompt_file="p", return_type="R", inputs_description="d", tools=["B", "ExternalTool"]),
        "B": AgentConfig(name="B", prompt_file="p", return_type="R", inputs_description="d", tools=[]),
    }
    sorted_order = topo_sort(configs)
    assert sorted_order == ["B", "A"]

def test_topo_sort_empty_configs():
    configs = {}
    sorted_order = topo_sort(configs)
    assert sorted_order == []

# --- 4. Testing import_module_from_path(path: Path) ---

def test_import_module_from_path_valid_module(tmp_path: Path):
    module_content = """
MY_VARIABLE = 123
def my_function():
    return "hello"
class MyClass:
    pass
"""
    dummy_module_file = tmp_path / "dummy_module.py"
    dummy_module_file.write_text(module_content)

    module = import_module_from_path(dummy_module_file)
    assert module.MY_VARIABLE == 123
    assert module.my_function() == "hello"
    assert hasattr(module, "MyClass")

def test_import_module_from_path_file_not_found(tmp_path: Path):
    non_existent_file = tmp_path / "ghost_module.py"
    with pytest.raises(FileNotFoundError): # Based on spec_from_file_location behavior
        import_module_from_path(non_existent_file)

def test_import_module_from_path_invalid_python_file(tmp_path: Path):
    invalid_module_file = tmp_path / "invalid_module.py"
    invalid_module_file.write_text("def my_func( missing_colon\n pass")

    with pytest.raises(SyntaxError):
        import_module_from_path(invalid_module_file)


# --- 5. Testing load_agents(configs, load_order, static_servers, job_queue) ---

# Mock MCPAgent for these tests
@patch('src.one_prompt_agents.agents_loader.MCPAgent', autospec=True)
def test_load_agents_one_agent_no_tools(mock_mcp_agent, tmp_path: Path):
    agents_base_dir = tmp_path / "agents_test_load"
    agents_base_dir.mkdir()
    agent_a_dir = agents_base_dir / "agent_A_load" # Path for AgentConfig._path
    agent_a_dir.mkdir()

    # Create a dummy return_type.py
    return_type_content = "from pydantic import BaseModel\nclass AgentAReturn(BaseModel):\n  res: str"
    (agent_a_dir / "return_type.py").write_text(return_type_content)
    (agent_a_dir / "prompt.txt").write_text("A prompt") # Needs to exist for path joining

    config_a = AgentConfig(
        name="AgentA", prompt_file="prompt.txt", return_type="AgentAReturn",
        inputs_description="desc A", tools=[]
    )
    config_a._path = Path("agent_A_load") # Relative to agents_base_dir

    configs = {"AgentA": config_a}
    load_order = ["AgentA"]
    static_servers = {}
    mock_job_queue = MagicMock()

    loaded_agents = load_agents(configs, load_order, static_servers, mock_job_queue, agents_base_dir)

    assert "AgentA" in loaded_agents
    mock_mcp_agent.assert_called_once()
    call_args = mock_mcp_agent.call_args[1] # Get kwargs

    assert call_args['agent_name'] == "AgentA"
    assert call_args['prompt_file'] == agents_base_dir / "agent_A_load" / "prompt.txt"
    assert call_args['return_type'].__name__ == "AgentAReturn"
    assert call_args['inputs_description'] == "desc A"
    assert call_args['tools_dict'] == {}
    assert call_args['model'] == "o4-mini" # Default model
    assert call_args['strategy_name'] == "default"
    assert call_args['job_queue'] == mock_job_queue

def test_load_agents_agent_with_specific_model(tmp_path: Path):
    with patch('src.one_prompt_agents.agents_loader.MCPAgent', autospec=True) as mock_mcp_agent_specific:
        agents_base_dir = tmp_path / "model_test"
        agents_base_dir.mkdir()
        agent_b_dir = agents_base_dir / "agent_B_model"
        agent_b_dir.mkdir()

        (agent_b_dir / "return_type.py").write_text("from pydantic import BaseModel\nclass BReturn(BaseModel):\n  data: int")
        (agent_b_dir / "b_prompt.txt").write_text("B prompt")

        config_b = AgentConfig(
            name="AgentB", prompt_file="b_prompt.txt", return_type="BReturn",
            inputs_description="desc B", tools=[], model="gpt-3.5-turbo"
        )
        config_b._path = Path("agent_B_model")

        configs = {"AgentB": config_b}
        load_order = ["AgentB"]
        loaded_agents = load_agents(configs, load_order, {}, MagicMock(), agents_base_dir)

        assert "AgentB" in loaded_agents
        mock_mcp_agent_specific.assert_called_once()
        assert mock_mcp_agent_specific.call_args[1]['model'] == "gpt-3.5-turbo"


@patch('src.one_prompt_agents.agents_loader.MCPAgent', autospec=True)
def test_load_agents_with_agent_tool(mock_mcp_agent_tool, tmp_path: Path):
    agents_base_dir = tmp_path / "tool_test"
    agents_base_dir.mkdir()

    # Tool Agent (AgentTool)
    agent_tool_dir = agents_base_dir / "agent_Tool"
    agent_tool_dir.mkdir()
    (agent_tool_dir / "return_type.py").write_text("from pydantic import BaseModel\nclass ToolReturn(BaseModel):\n  out: bool")
    (agent_tool_dir / "tool_prompt.txt").write_text("Tool prompt")
    config_tool = AgentConfig(name="AgentTool", prompt_file="tool_prompt.txt", return_type="ToolReturn", inputs_description="desc Tool", tools=[])
    config_tool._path = Path("agent_Tool")

    # Main Agent (AgentMain)
    agent_main_dir = agents_base_dir / "agent_Main"
    agent_main_dir.mkdir()
    (agent_main_dir / "return_type.py").write_text("from pydantic import BaseModel\nclass MainReturn(BaseModel):\n  final: str")
    (agent_main_dir / "main_prompt.txt").write_text("Main prompt")
    config_main = AgentConfig(name="AgentMain", prompt_file="main_prompt.txt", return_type="MainReturn", inputs_description="desc Main", tools=["AgentTool"])
    config_main._path = Path("agent_Main")

    configs = {"AgentTool": config_tool, "AgentMain": config_main}
    load_order = ["AgentTool", "AgentMain"] # AgentTool must be loaded first
    
    # Simulate MCPAgent instantiation
    mock_tool_instance = MagicMock(spec=MCPAgent) # from src.one_prompt_agents.mcp_agent import MCPAgent
    mock_main_instance = MagicMock(spec=MCPAgent)
    
    # Side effect to return the correct mock instance based on agent name
    def mcp_side_effect(**kwargs):
        if kwargs['agent_name'] == "AgentTool":
            return mock_tool_instance
        elif kwargs['agent_name'] == "AgentMain":
            return mock_main_instance
        return MagicMock() # Default mock if something unexpected

    mock_mcp_agent_tool.side_effect = mcp_side_effect

    loaded_agents = load_agents(configs, load_order, {}, MagicMock(), agents_base_dir)

    assert "AgentTool" in loaded_agents
    assert "AgentMain" in loaded_agents
    assert loaded_agents["AgentTool"] == mock_tool_instance
    assert loaded_agents["AgentMain"] == mock_main_instance
    
    # Check that AgentMain was initialized with AgentTool in its tools_dict
    main_call_kwargs = None
    for call in mock_mcp_agent_tool.call_args_list:
        if call[1]['agent_name'] == 'AgentMain':
            main_call_kwargs = call[1]
            break
    assert main_call_kwargs is not None
    assert "AgentTool" in main_call_kwargs['tools_dict']
    assert main_call_kwargs['tools_dict']["AgentTool"] == mock_tool_instance


@patch('src.one_prompt_agents.agents_loader.MCPAgent', autospec=True)
def test_load_agents_with_static_server_tool(mock_mcp_agent_static, tmp_path: Path):
    agents_base_dir = tmp_path / "static_tool_test"
    agents_base_dir.mkdir()
    agent_c_dir = agents_base_dir / "agent_C_static"
    agent_c_dir.mkdir()
    (agent_c_dir / "return_type.py").write_text("from pydantic import BaseModel\nclass CReturn(BaseModel):\n  val: float")
    (agent_c_dir / "c_prompt.txt").write_text("C prompt")

    config_c = AgentConfig(
        name="AgentC", prompt_file="c_prompt.txt", return_type="CReturn",
        inputs_description="desc C", tools=["StaticServerTool"]
    )
    config_c._path = Path("agent_C_static")
    
    configs = {"AgentC": config_c}
    load_order = ["AgentC"]
    mock_static_tool = MagicMock()
    static_servers = {"StaticServerTool": mock_static_tool}
    
    mock_c_instance = MagicMock(spec=MCPAgent)
    mock_mcp_agent_static.return_value = mock_c_instance

    loaded_agents = load_agents(configs, load_order, static_servers, MagicMock(), agents_base_dir)

    assert "AgentC" in loaded_agents
    mock_mcp_agent_static.assert_called_once()
    call_kwargs = mock_mcp_agent_static.call_args[1]
    assert "StaticServerTool" in call_kwargs['tools_dict']
    assert call_kwargs['tools_dict']["StaticServerTool"] == mock_static_tool

@patch('src.one_prompt_agents.agents_loader.MCPAgent', autospec=True)
@patch('src.one_prompt_agents.agents_loader.import_module_from_path')
def test_load_agents_return_type_file_missing(mock_import_module, mock_mcp_agent_missing_rt, tmp_path: Path):
    agents_base_dir = tmp_path / "missing_rt_test"
    agents_base_dir.mkdir()
    agent_d_dir = agents_base_dir / "agent_D_missing_rt" # No return_type.py will be created
    agent_d_dir.mkdir()
    (agent_d_dir / "d_prompt.txt").write_text("D prompt")


    config_d = AgentConfig(
        name="AgentD", prompt_file="d_prompt.txt", return_type="DReturn",
        inputs_description="desc D", tools=[]
    )
    config_d._path = Path("agent_D_missing_rt")

    configs = {"AgentD": config_d}
    load_order = ["AgentD"]
    
    # Simulate FileNotFoundError when trying to import return_type.py
    mock_import_module.side_effect = FileNotFoundError("return_type.py not found")

    with pytest.raises(FileNotFoundError, match="return_type.py not found"):
        load_agents(configs, load_order, {}, MagicMock(), agents_base_dir)
    
    mock_mcp_agent_missing_rt.assert_not_called() # Agent loading should fail before MCPAgent init

@patch('src.one_prompt_agents.agents_loader.MCPAgent', autospec=True)
def test_load_agents_tool_not_found(mock_mcp_agent_tool_nf, tmp_path: Path):
    agents_base_dir = tmp_path / "tool_nf_test"
    agents_base_dir.mkdir()
    agent_e_dir = agents_base_dir / "agent_E_tool_nf"
    agent_e_dir.mkdir()
    (agent_e_dir / "return_type.py").write_text("from pydantic import BaseModel\nclass EReturn(BaseModel):\n  res: str")
    (agent_e_dir / "e_prompt.txt").write_text("E prompt")

    config_e = AgentConfig(
        name="AgentE", prompt_file="e_prompt.txt", return_type="EReturn",
        inputs_description="desc E", tools=["NonExistentTool"] # This tool is not in loaded_agents or static_servers
    )
    config_e._path = Path("agent_E_tool_nf")
    
    configs = {"AgentE": config_e}
    load_order = ["AgentE"]
    static_servers = {} # Empty

    with pytest.raises(KeyError, match="Tool 'NonExistentTool' not found for agent 'AgentE'"):
        load_agents(configs, load_order, static_servers, MagicMock(), agents_base_dir)
    
    mock_mcp_agent_tool_nf.assert_not_called() # Should fail before MCPAgent init for AgentE

# A helper for AgentConfig to avoid repetition in topo_sort tests
def create_mock_config(name, tools=None):
    if tools is None:
        tools = []
    return AgentConfig(
        name=name,
        prompt_file=f"{name.lower()}.txt",
        return_type=f"{name}Return",
        inputs_description=f"Description for {name}",
        tools=tools
    )

# Re-check topo_sort tests to use the helper for conciseness if needed
# (The current ones are explicit which is also fine)

# Example of using the helper in a topo_sort test
def test_topo_sort_complex_case_with_helper():
    configs = {
        "A": create_mock_config("A", ["B", "C"]),
        "B": create_mock_config("B", ["D"]),
        "C": create_mock_config("C", ["D", "E"]),
        "D": create_mock_config("D"),
        "E": create_mock_config("E")
    }
    # Expected: D, E must come before B, C. B, C must come before A.
    # Possible valid orders: [D, E, B, C, A], [D, E, C, B, A], [E, D, B, C, A], [E, D, C, B, A]
    sorted_order = topo_sort(configs)
    assert len(sorted_order) == 5
    assert sorted_order[-1] == "A"
    idx_a = sorted_order.index("A")
    idx_b = sorted_order.index("B")
    idx_c = sorted_order.index("C")
    idx_d = sorted_order.index("D")
    idx_e = sorted_order.index("E")

    assert idx_d < idx_b < idx_a
    assert idx_d < idx_c < idx_a
    assert idx_e < idx_c < idx_a

# Final check on imports and mocks
# Ensure MCPAgent is mocked where necessary, especially for load_agents tests.
# The `autospec=True` in `@patch` is good for ensuring mock signatures match the real object.
# `from src.one_prompt_agents.mcp_agent import MCPAgent` would be needed if MCPAgent was not mocked
# or if we need to reference it directly (e.g. `spec=MCPAgent` in MagicMock).
# Since it's consistently mocked in load_agents tests, direct import isn't strictly necessary there.

# Consider if any other utility functions in agents_loader.py need testing.
# The plan covers the main functions.

# One last check: discover_configs and _path attribute.
# The _path attribute should be relative to the main agents_dir.
# For agent_A_dir = agents_dir / "agent_A", config._path should be Path("agent_A")
# This seems correctly handled in test_discover_configs_one_valid_agent.
# The base_agents_config_path in load_agents is then joined with this _path and prompt_file.
# (agents_base_dir / agent_config._path / agent_config.prompt_file)
# This seems correct.
