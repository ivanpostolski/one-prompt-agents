import asyncio
import os
import json
import uuid
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastmcp import FastMCP
from agents.mcp import MCPServerSse

logger = logging.getLogger(__name__)
PORT = 9001
# Define the MCPSSE instance for this server
testing_mcp_server = MCPServerSse(
    params={
        "url": f"http://127.0.0.1:{PORT}/sse",
        "timeout": 8,
        "sse_read_timeout": 100,
    },
    cache_tools_list=True,
    client_session_timeout_seconds=180,
    name="testing_mcp_server",
)

# In-memory stores
_test_scenarios_db: Dict[str, dict] = {}
_test_results_db: Dict[str, dict] = {}
_scenario_queue: List[str] = []
_scenario_queue_lock = asyncio.Lock()

mcp = FastMCP(
    name="TestingMCPServer",
    version="0.2.0",
    description="MCP server for managing and reporting test scenarios for the agent framework. Loads scenarios dynamically from agents_config/test_*/test_scenario_*.json files.",
)

# -------------------- Scenario/Result Models --------------------
class TestScenario(BaseModel):
    scenario_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    steps: List[str]
    acceptance_criteria: List[str]
    required_agents: List[Dict[str, Any]]

class TestResult(BaseModel):
    scenario_id: str
    status: str # "SUCCESS", "FAILURE"
    details: str = ""
    reason_for_failure: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None

class TestReport(BaseModel):
    total_scenarios_loaded: int
    total_scenarios_run: int
    successful: int
    failed: int
    results: List[TestResult]

# -------------------- Tool Implementations --------------------

def get_agents_config_path() -> str:
    here = os.path.dirname(__file__)
    config_path = os.path.abspath(os.path.join(here, "..", "agents_config"))
    return config_path

@mcp.tool(name="load_scenarios_from_disk", description="Scans agent_config folders for test_* agents and loads their scenario JSON files.")
async def load_scenarios_from_disk() -> dict:
    agents_config_path = get_agents_config_path()
    loaded_scenarios_count = 0
    scenarios_found_for_loading = []
    errors = []
    
    if not os.path.isdir(agents_config_path):
        msg = f"Agents config path not found: {agents_config_path}"
        logger.error(msg)
        return {"message": msg, "loaded_count": 0, "errors": [msg]}

    for agent_folder_name in os.listdir(agents_config_path):
        if agent_folder_name.startswith("test_"):
            agent_folder_path = os.path.join(agents_config_path, agent_folder_name)
            if os.path.isdir(agent_folder_path):
                for item_name in os.listdir(agent_folder_path):
                    if item_name.startswith("test_scenario_") and item_name.endswith(".json"):
                        scenario_file_path = os.path.join(agent_folder_path, item_name)
                        try:
                            with open(scenario_file_path, 'r') as f:
                                scenario_data = json.load(f)
                                if 'scenario_id' not in scenario_data:
                                    scenario_data['scenario_id'] = str(uuid.uuid4())
                                scenario = TestScenario(**scenario_data)
                                scenarios_found_for_loading.append(scenario)
                                logger.info(f"Found scenario file: {scenario_file_path} for agent {agent_folder_name}")
                        except json.JSONDecodeError as e:
                            err_msg = f"Error decoding JSON from {scenario_file_path}: {e}"
                            logger.error(err_msg)
                            errors.append(err_msg)
                        except Exception as e:
                            err_msg = f"Error processing scenario file {scenario_file_path}: {e}"
                            logger.error(err_msg)
                            errors.append(err_msg)
    loaded_ids = []
    for scenario in scenarios_found_for_loading:
        _test_scenarios_db[scenario.scenario_id] = scenario.dict()
        if scenario.scenario_id not in _test_results_db and scenario.scenario_id not in _scenario_queue:
            _scenario_queue.append(scenario.scenario_id)
        loaded_ids.append(scenario.scenario_id)
    loaded_scenarios_count = len(loaded_ids)
    return {
        "message": f"Disk scan complete. Found and attempted to load {len(scenarios_found_for_loading)} scenarios. Successfully loaded: {loaded_scenarios_count}.",
        "loaded_count": loaded_scenarios_count,
        "loaded_scenario_ids": loaded_ids,
        "errors": errors
    }

@mcp.tool(name="next_testing_scenario", description="Retrieves the next available test scenario from the queue. Returns status 'exhausted' if none remain.")
async def next_testing_scenario() -> dict:
    async with _scenario_queue_lock:
        if not _scenario_queue:
            if not _test_scenarios_db:
                logger.info("Scenario queue is empty and no scenarios in DB. Attempting to load from disk.")
                await load_scenarios_from_disk()
            if not _scenario_queue:
                logger.info("Scenario queue is still empty after attempting disk load.")
                return {"status": "exhausted"}
        scenario_id = _scenario_queue.pop(0)
        scenario = _test_scenarios_db.get(scenario_id)
        if not scenario:
            logger.warning(f"Scenario ID {scenario_id} was in queue but not found in DB. This shouldn't happen.")
            return await next_testing_scenario()
        return {"status": "ok", "scenario": scenario}

@mcp.tool(name="report_test_success", description="Reports a successful test scenario outcome.")
async def report_test_success(scenario_id: str, details: str = "Test passed.", metrics: Optional[dict] = None) -> dict:
    if scenario_id not in _test_scenarios_db:
        return {"error": f"Scenario ID {scenario_id} not found."}
    result = TestResult(
        scenario_id=scenario_id,
        status="SUCCESS",
        details=details,
        metrics=metrics
    )
    _test_results_db[scenario_id] = result.dict()
    logger.info(f"Test SUCCEEDED: {_test_scenarios_db[scenario_id]['name']} (ID: {scenario_id}). Details: {details}")
    return {"message": "Test success reported.", "scenario_id": scenario_id}

@mcp.tool(name="report_test_failure", description="Reports a failed test scenario outcome with reasons.")
async def report_test_failure(scenario_id: str, what_failed: str, why: str, details: str = "", metrics: Optional[dict] = None) -> dict:
    if scenario_id not in _test_scenarios_db:
        return {"error": f"Scenario ID {scenario_id} not found."}
    result = TestResult(
        scenario_id=scenario_id,
        status="FAILURE",
        details=details or what_failed,
        reason_for_failure=why,
        metrics=metrics
    )
    _test_results_db[scenario_id] = result.dict()
    logger.error(f"Test FAILED: {_test_scenarios_db[scenario_id]['name']} (ID: {scenario_id}). Reason: {why}. What failed: {what_failed}")
    return {"message": "Test failure reported.", "scenario_id": scenario_id}

@mcp.tool(name="get_report", description="Retrieves a summary report of all executed test scenarios.")
async def get_report() -> dict:
    successful_count = 0
    failed_count = 0
    all_results = list(_test_results_db.values())
    for result in all_results:
        if result["status"] == "SUCCESS":
            successful_count += 1
        elif result["status"] == "FAILURE":
            failed_count += 1
    report = TestReport(
        total_scenarios_loaded=len(_test_scenarios_db),
        total_scenarios_run=len(all_results),
        successful=successful_count,
        failed=failed_count,
        results=[TestResult(**r) for r in all_results]
    )
    return report.dict()

@mcp.tool(name="send_report", description="Sends the test report (simulated - prints to console).")
async def send_report(recipient_email: str, report_override: Optional[dict] = None) -> dict:
    report_to_send = report_override if report_override else await get_report()
    report_str = f"Test Report for {recipient_email}:\n"
    report_str += f"Total Scenarios Loaded: {report_to_send['total_scenarios_loaded']}\n"
    report_str += f"Total Scenarios Run: {report_to_send['total_scenarios_run']}\n"
    report_str += f"Successful: {report_to_send['successful']}\n"
    report_str += f"Failed: {report_to_send['failed']}\n\n"
    report_str += "Details of Run Scenarios:\n"
    if not report_to_send['results']:
        report_str += "  No scenarios have been run yet.\n"
    for res in report_to_send['results']:
        scenario_name = _test_scenarios_db.get(res['scenario_id'], {}).get('name', 'Unknown Scenario')
        report_str += f"  Scenario: {scenario_name} (ID: {res['scenario_id']}) - Status: {res['status']}\n"
        if res['status'] == "FAILURE":
            report_str += f"    Reason: {res.get('reason_for_failure', '')}\n"
            report_str += f"    Details: {res.get('details', '')}\n"
        if res.get('metrics'):
            report_str += f"    Metrics: {json.dumps(res['metrics'])}\n"
        report_str += "\n"
    print("---BEGIN SIMULATED EMAIL REPORT---")
    print(f"To: {recipient_email}")
    print("Subject: Automated Test Report")
    print(report_str)
    print("---END SIMULATED EMAIL REPORT---")
    logger.info(f"Simulated sending report to {recipient_email}")
    return {"message": f"Report (simulated) sent to {recipient_email}."}

@mcp.tool(
    name="wait",
    description="Wait for a specified number of seconds (max 120). Use for test synchronization or delays."
)
async def wait_tool(seconds: int) -> str:
    """
    Waits for up to 120 seconds (2 minutes) asynchronously.
    Args:
        seconds (int): Number of seconds to wait.
    Returns:
        str: Confirmation message.
    """
    max_wait = 120
    if seconds > max_wait:
        seconds = max_wait
    if seconds < 0:
        seconds = 0
    await asyncio.sleep(seconds)
    return f"Waited for {seconds} seconds."

# -------------------- Main Entrypoint --------------------
def main():
    loop = asyncio.get_event_loop()
    task = loop.create_task(
        mcp.run_sse_async(
            host='127.0.0.1',
            port=PORT,
            log_level='debug'
        )
    )
    return task
