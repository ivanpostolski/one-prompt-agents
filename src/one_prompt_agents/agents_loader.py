# Usage:
# configs = discover_configs(Path("agents"))
# load_order = topo_sort(configs)
import json, importlib, sys
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict
from pydantic import BaseModel,  PrivateAttr
from one_prompt_agents.mcp_agent import MCPAgent

import logging
logger = logging.getLogger(__name__) 

class AgentConfig(BaseModel):
    name: str
    prompt_file: str
    return_type: str
    inputs_description: str
    tools: List[str]
    _path: Path = PrivateAttr()
    model: str | None = None

def discover_configs(agents_dir: Path) -> Dict[str, AgentConfig]:
    configs = {}
    for folder in agents_dir.iterdir():
        cfg_path = folder / "config.json"
        if cfg_path.exists():
            data = json.loads(cfg_path.read_text())
            configs[data["name"]] = AgentConfig(**data)
            configs[data["name"]]._path = folder.name
    return configs

def topo_sort(configs: Dict[str, AgentConfig]) -> List[str]:
    graph = defaultdict(list)
    for name, cfg in configs.items():
        for dep in cfg.tools:
            if dep in configs:
                graph[dep].append(name)
    visited, temp, order = set(), set(), []
    def dfs(node):
        if node in temp:
            raise ValueError(f"Cyclic dependency at {node}")
        if node not in visited:
            temp.add(node)
            for nei in graph[node]:
                dfs(nei)
            temp.remove(node); visited.add(node); order.append(node)
    for node in configs:
        dfs(node)
    order.reverse()  # reverse to get the correct order
    logger.info(f"Load order: {order}")
    return order  # dependencies first

def import_module_from_path(path: Path):
    """Import a .py file as an opaque module object."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module        # supports intra-module imports
    spec.loader.exec_module(module)        # run the code
    return module

def load_agents(configs, load_order, static_servers, job_queue):
    loaded = {}
    for name in load_order:
        cfg = configs[name]
        folder = Path("agents_config") / cfg._path 
        
        return_type = folder / "return_type.py"

        # load return_type model
        mod = import_module_from_path(return_type)
        ReturnType = getattr(mod, cfg.return_type)

        # resolve tool list: either static or other agents
        tools = []
        for t in cfg.tools:
            if t in static_servers:
                tools.append(static_servers[t])
            else:
                tools.append(loaded[t])

        mcp_agent = MCPAgent(
            name           = cfg.name,
            prompt_file    = str(folder / cfg.prompt_file),
            return_type     = ReturnType,
            inputs_description   = cfg.inputs_description,
            mcp_servers    = tools,
            job_queue  = job_queue,
            model= cfg.model if cfg.model is not None else "o4-mini", 
        )
        loaded[name] = mcp_agent
    return loaded
