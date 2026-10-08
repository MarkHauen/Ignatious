"""MCP tools for the Ignatious Kanban FastAPI service."""

import json
import os
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mcp.server.fastmcp import FastMCP


IGNATIOUS_URL = os.environ.get("IGNATIOUS_URL", "http://127.0.0.1:8000").rstrip("/")


def _request(
	method: str, path: str, payload: Optional[dict[str, Any]] = None
) -> Any:
	data = json.dumps(payload).encode("utf-8") if payload is not None else None
	request = Request(
		f"{IGNATIOUS_URL}{path}",
		data=data,
		method=method,
		headers={"Content-Type": "application/json"} if data else {},
	)
	try:
		with urlopen(request, timeout=10) as response:
			return json.loads(response.read().decode("utf-8"))
	except HTTPError as error:
		detail = error.read().decode("utf-8", errors="replace")
		raise RuntimeError(f"Ignatious returned HTTP {error.code}: {detail}") from error
	except URLError as error:
		raise RuntimeError(f"Unable to reach Ignatious at {IGNATIOUS_URL}: {error.reason}") from error


def register_tools(mcp: FastMCP) -> None:
	"""Register task-management tools on an MCP server."""

	@mcp.tool(description="List tasks. Use roots_only for a monthly board, parent_id for a nested board, sprint_id for a month, or unscheduled for unplanned work.")
	def list_ignatious_tasks(
		status: Optional[str] = None, epic_id: Optional[int] = None,
		sprint_id: Optional[int] = None, parent_id: Optional[int] = None,
		roots_only: bool = False, unscheduled: bool = False,
		project_id: Optional[int] = None,
		resolution_state: Optional[str] = None, needs_attention: bool = False,
	) -> list[dict[str, Any]]:
		from urllib.parse import urlencode

		params = {}
		if status:
			params["status"] = status
		if epic_id is not None:
			params["epic_id"] = epic_id
		for key, value in {"sprint_id": sprint_id, "parent_id": parent_id, "project_id": project_id}.items():
			if value is not None:
				params[key] = value
		if resolution_state is not None:
			params["resolution_state"] = resolution_state
		if needs_attention:
			params["needs_attention"] = "true"
		if roots_only:
			params["roots_only"] = "true"
		if unscheduled:
			params["unscheduled"] = "true"
		path = "/api/tasks/"
		if params:
			path = f"{path}?{urlencode(params)}"
		return _request("GET", path)

	@mcp.tool(description="Get an Ignatious Kanban task by its numeric ID.")
	def get_ignatious_task(task_id: int) -> dict[str, Any]:
		return _request("GET", f"/api/tasks/{task_id}")

	@mcp.tool(description="Create an Ignatious Kanban task. Status must be an Ignatious status label.")
	def create_ignatious_task(
		title: str,
		description: Optional[str] = None,
		assignee: Optional[str] = None,
		status: Optional[str] = None,
		project_id: int = 1,
		epic_id: Optional[int] = None,
		parent_id: Optional[int] = None,
		sprint_id: Optional[int] = None,
		resolution: Optional[str] = None, resolution_state: str = "Unresolved",
		review_notes: Optional[str] = None,
	) -> dict[str, Any]:
		payload: dict[str, Any] = {"title": title, "project_id": project_id}
		if description is not None:
			payload["description"] = description
		if assignee is not None:
			payload["assignee"] = assignee
		if status is not None:
			payload["status"] = status
		if epic_id is not None:
			payload["epic_id"] = epic_id
		if parent_id is not None:
			payload["parent_id"] = parent_id
		if sprint_id is not None:
			payload["sprint_id"] = sprint_id
		payload.update(resolution=resolution, resolution_state=resolution_state, review_notes=review_notes)
		return _request("POST", "/api/tasks/", payload)

	@mcp.tool(description="Update a task. Children inherit sprint from their parent. Resolution state (Unresolved, Partially resolved, Resolved, Deferred) is independent of task status. Pass expected_revision from the last read to reject stale edits. Use clear_fields to clear description, resolution, review_notes, assignee, epic_id, parent_id or sprint_id.")
	def update_ignatious_task(
		task_id: int,
		title: Optional[str] = None,
		description: Optional[str] = None,
		assignee: Optional[str] = None,
		status: Optional[str] = None,
		epic_id: Optional[int] = None,
		parent_id: Optional[int] = None,
		sprint_id: Optional[int] = None,
		resolution: Optional[str] = None, resolution_state: Optional[str] = None,
		review_notes: Optional[str] = None, expected_revision: Optional[int] = None,
		clear_fields: Optional[list[str]] = None,
	) -> dict[str, Any]:
		payload = {
			field: value
			for field, value in {
				"resolution": resolution, "resolution_state": resolution_state,
				"review_notes": review_notes, "expected_revision": expected_revision,
				"title": title,
				"description": description,
				"assignee": assignee,
				"status": status,
				"epic_id": epic_id,
				"parent_id": parent_id,
				"sprint_id": sprint_id,
			}.items()
			if value is not None
		}
		for field in clear_fields or []:
			if field not in {"description", "assignee", "epic_id", "parent_id", "sprint_id", "resolution", "review_notes"}:
				raise ValueError(f"Cannot clear {field}")
			if field in payload:
				raise ValueError(f"Cannot set and clear {field} in the same request")
			payload[field] = None
		if not payload:
			raise ValueError("Provide at least one field to update.")
		return _request("PATCH", f"/api/tasks/{task_id}", payload)

	@mcp.tool(description="Delete an Ignatious Kanban task by its numeric ID.")
	def delete_ignatious_task(task_id: int) -> dict[str, Any]:
		return _request("DELETE", f"/api/tasks/{task_id}")

	@mcp.tool(description="List Ignatious Kanban epics.")
	def list_ignatious_epics() -> list[dict[str, Any]]:
		return _request("GET", "/api/epics/")

	@mcp.tool(description="Get an Ignatious Kanban epic by its numeric ID.")
	def get_ignatious_epic(epic_id: int) -> dict[str, Any]:
		return _request("GET", f"/api/epics/{epic_id}")

	@mcp.tool(description="Create an Ignatious Kanban epic.")
	def create_ignatious_epic(
		title: str,
		description: Optional[str] = None,
		color: Optional[str] = None,
		project_id: int = 1,
	) -> dict[str, Any]:
		payload: dict[str, Any] = {"title": title, "project_id": project_id}
		if description is not None:
			payload["description"] = description
		if color is not None:
			payload["color"] = color
		return _request("POST", "/api/epics/", payload)

	@mcp.tool(description="Update selected fields of an Ignatious Kanban epic.")
	def update_ignatious_epic(
		epic_id: int,
		title: Optional[str] = None,
		description: Optional[str] = None,
		color: Optional[str] = None,
	) -> dict[str, Any]:
		payload = {
			field: value
			for field, value in {
				"title": title,
				"description": description,
				"color": color,
			}.items()
			if value is not None
		}
		if not payload:
			raise ValueError("Provide at least one field to update.")
		return _request("PATCH", f"/api/epics/{epic_id}", payload)

	@mcp.tool(description="Delete an Ignatious Kanban epic by its numeric ID. Tasks in the epic are unassigned, not deleted.")
	def delete_ignatious_epic(epic_id: int) -> dict[str, Any]:
		return _request("DELETE", f"/api/epics/{epic_id}")

	@mcp.tool(description="List available Ignatious Kanban assignees.")
	def list_ignatious_users() -> list[dict[str, Any]]:
		return _request("GET", "/api/users/")

	@mcp.tool(description="Add a new Ignatious Kanban assignee.")
	def add_ignatious_user(name: str) -> dict[str, Any]:
		return _request("POST", "/api/users/add/", {"name": name})

	@mcp.tool(description="Rename an existing Ignatious Kanban assignee.")
	def update_ignatious_user(user_id: int, name: str) -> dict[str, Any]:
		return _request("PUT", f"/api/users/{user_id}/", {"name": name})

	@mcp.tool(description="Delete an Ignatious Kanban assignee by its numeric ID.")
	def delete_ignatious_user(user_id: int) -> dict[str, Any]:
		return _request("DELETE", f"/api/users/{user_id}/")

	@mcp.tool(description="List valid Ignatious Kanban task status labels.")
	def list_ignatious_statuses() -> list[str]:
		return _request("GET", "/api/statuses/")

	@mcp.tool(description="List monthly sprints, their goals, and top-level completion counts.")
	def list_ignatious_sprints(project_id: int = 1) -> list[dict[str, Any]]:
		return _request("GET", f"/api/sprints/?project_id={project_id}")

	@mcp.tool(description="Create a monthly sprint. Month must be YYYY-MM; one sprint per project per month.")
	def create_ignatious_sprint(month: str, goal: str = "", project_id: int = 1) -> dict[str, Any]:
		return _request("POST", "/api/sprints/", {"month": month, "goal": goal, "project_id": project_id})

	@mcp.tool(description="Update the goal of a monthly sprint.")
	def update_ignatious_sprint(sprint_id: int, goal: str) -> dict[str, Any]:
		return _request("PATCH", f"/api/sprints/{sprint_id}", {"goal": goal})

	@mcp.tool(description="Delete an empty sprint. Move its tasks first; nonempty sprints cannot be deleted.")
	def delete_ignatious_sprint(sprint_id: int) -> dict[str, Any]:
		return _request("DELETE", f"/api/sprints/{sprint_id}")

	@mcp.tool(description="Move top-level tasks and all their descendants into a sprint. Omit sprint_id to unschedule them. The operation is atomic.")
	def assign_ignatious_sprint(task_ids: list[int], sprint_id: Optional[int] = None) -> dict[str, Any]:
		return _request("POST", "/api/tasks/assign-sprint", {"task_ids": task_ids, "sprint_id": sprint_id})

	@mcp.tool(description="Get the ordered ancestor trail of a task, for navigating nested boards.")
	def get_ignatious_task_ancestors(task_id: int) -> list[dict[str, Any]]:
		return _request("GET", f"/api/tasks/{task_id}/ancestors")


	@mcp.tool(description="List needed decisions, investigations and actions across all nesting levels. open_only includes Open and Linked; linked work is not automatically resolved when its task completes.")
	def list_ignatious_needed_tasks(task_id: Optional[int] = None, project_id: Optional[int] = None,
		epic_id: Optional[int] = None, state: Optional[str] = None, kind: Optional[str] = None,
		open_only: bool = False) -> list[dict[str, Any]]:
		from urllib.parse import urlencode
		params = {k:v for k,v in dict(task_id=task_id, project_id=project_id, epic_id=epic_id, state=state, kind=kind).items() if v is not None}
		if open_only: params['open_only'] = 'true'
		return _request('GET', '/api/needed-tasks/?' + urlencode(params))

	@mcp.tool(description="Record a needed Decision, Investigation or Action on a task. Reuse a stable source_key for retry-safe suggestion imports. Does not create executable work until materialized.")
	def create_ignatious_needed_task(task_id: int, title: str, description: Optional[str] = None,
		kind: str = 'Action', source_key: Optional[str] = None) -> dict[str, Any]:
		return _request('POST', f'/api/tasks/{task_id}/needed-tasks', dict(title=title, description=description, kind=kind, source_key=source_key))

	@mcp.tool(description="Review a needed item. States: Open, Linked, Resolved, Dismissed. Resolved/Dismissed require an outcome in resolution. Reopen linked items as Linked. Task completion is independent. Use expected_revision for stale-write protection.")
	def update_ignatious_needed_task(need_id: int, title: Optional[str] = None, description: Optional[str] = None,
		kind: Optional[str] = None, state: Optional[str] = None, resolution: Optional[str] = None,
		expected_revision: Optional[int] = None) -> dict[str, Any]:
		payload = {k:v for k,v in dict(title=title, description=description, kind=kind, state=state, resolution=resolution, expected_revision=expected_revision).items() if v is not None}
		return _request('PATCH', f'/api/needed-tasks/{need_id}', payload)

	@mcp.tool(description="Turn a needed item into a subtask atomically, inheriting project/epic/sprint; repeat calls return the existing link. Or pass existing_task_id to reuse same-project work without creating a duplicate. Never executes the work or completes the source task.")
	def materialize_ignatious_needed_task(need_id: int, existing_task_id: Optional[int] = None,
		assignee: Optional[str] = None, status: str = 'Backlog') -> dict[str, Any]:
		return _request('POST', f'/api/needed-tasks/{need_id}/materialize', dict(existing_task_id=existing_task_id, assignee=assignee, status=status))


def main() -> None:
	server = FastMCP("Ignatious")
	register_tools(server)
	server.run(transport="stdio")


if __name__ == "__main__":
	main()
