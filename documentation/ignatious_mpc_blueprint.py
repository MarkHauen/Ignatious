# Ignatious/mcp_tools.py
import json
import httpx

# Load tool definitions from JSON string or file
TOOLS_JSON = """{ ... paste the JSON above here ... }"""

def get_ignatious_tools():
    return json.loads(TOOLS_JSON)

async def execute_tool(tool_name: str, arguments: dict):
    """
    Helper to execute tools against your FastAPI backend.
    """
    base_url = "http://localhost:8000" # Replace with your actual server URL
    
    if tool_name == "get_tasks":
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/api/tasks/", params=arguments)
            return response.json()
            
    elif tool_name == "create_task":
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{base_url}/api/tasks/", json=arguments)
            return response.json()
            
    elif tool_name == "update_task_status":
        task_id = arguments.pop("task_id")
        # Map the argument structure to your API's PATCH request if needed.
        # Your current PATCH /api/tasks/{task_id} accepts a TaskUpdate object.
        payload = {"status": arguments["status"]}
        async with httpx.AsyncClient() as client:
            response = await client.patch(f"{base_url}/api/tasks/{task_id}", json=payload)
            return response.json()

    elif tool_name == "get_users":
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/api/users/")
            return response.json()

    elif tool_name == "delete_task":
        task_id = arguments["task_id"]
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{base_url}/api/tasks/{task_id}")
            return response.json()
            
    else:
        raise ValueError(f"Unknown tool: {tool_name}")