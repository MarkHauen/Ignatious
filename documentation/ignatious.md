Ignatious Kanban API Documentation
Base URL: /api

1. Get Tasks
Endpoint: GET /api/tasks/
Query Params:
status (optional): Filter by status (Ready for Action, In Progress, In Review, Complete).
Response: List of Task objects.
2. Create Task
Endpoint: POST /api/tasks/
Body:

Apply
{
  "title": "New Feature",
  "description": "Implement login page",
  "assignee": "agent_01",
  "status": "Ready for Action",
  "project_id": 1
}
3. Update Task (Status Change)
Endpoint: PATCH /api/tasks/{task_id}
Body:

Apply
{
  "status": "In Progress"
}
Note: This is the primary method for moving tasks in the Kanban board.
4. Get Users
Endpoint: GET /api/users/
Response: List of User objects (ID and Name).
Usage: Useful for resolving agent names or human user IDs during task assignment.
5. Delete Task
Endpoint: DELETE /api/tasks/{task_id}
Response: Success message.
Next Steps for Implementation
Install Dependencies: Ensure httpx is installed if using the Python helper above.
MCP Integration: If you are using a specific MCP framework (like mcp-server-fastapi), register these tools directly using the decorator pattern provided by that library.
Error Handling: The current API returns HTTP status codes (404 for not found). Ensure your MCP client handles these gracefully to inform the agent of invalid task IDs or missing projects.