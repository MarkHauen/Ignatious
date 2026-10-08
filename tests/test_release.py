import asyncio
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError, URLError
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from mcp.server.fastmcp import FastMCP


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_data_is_not_tracked():
    result = subprocess.run([
        "git", "ls-files", "--", "*.db*", "*.sqlite*", "*.pyc", "*.pyo",
        "__pycache__/*", "**/__pycache__/*", ".env", ".vscode/mcp.json",
    ], cwd=ROOT, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "", "Runtime data must not be tracked in Git"


def test_runtime_and_local_client_files_are_ignored():
    paths = ["private.db", "private.db-wal", "private.db.bak", "private.sqlite3.bak",
             "__pycache__/app.pyc", ".env", ".venv/example", ".vscode/mcp.json"]
    result = subprocess.run(["git", "check-ignore", "-z", "--stdin"], cwd=ROOT,
                            input=("\0".join(paths) + "\0").encode(),
                            capture_output=True, check=True)
    assert result.stdout.decode().split("\0")[:-1] == paths


@pytest.fixture(scope="session")
def application(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch:
        directory = tmp_path_factory.mktemp("release")
        patch.setenv("IGNATIOUS_DATABASE_URL", f"sqlite:///{(directory / 'test.db').as_posix()}")
        patch.chdir(directory)
        app_module = importlib.import_module("app")
        database = importlib.import_module("database")
        try:
            yield app_module.app
        finally:
            database.engine.dispose()


@pytest.fixture
def client(application):
    import database

    database.Base.metadata.drop_all(database.engine)
    database.init_db()
    with TestClient(application) as test_client:
        yield test_client


def create_task(client, **fields):
    response = client.post("/api/tasks/", json={"title": "Release task", **fields})
    assert response.status_code == 200, response.text
    return response.json()


def test_portable_startup_and_static_pages(client):
    assert client.get("/", follow_redirects=False).headers["location"] == "/static/index.html"
    for page in ("index", "backlog", "task", "needed", "team"):
        response = client.get(f"/static/{page}.html")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"
    assert client.get("/team").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/api/statuses/").json() == [
        "Backlog", "Ready for Action", "In Progress", "In Review", "Complete"
    ]
    assert client.get("/api/tasks/").json() == []
    import database

    database.init_db()
    with database.SessionLocal() as session:
        assert session.query(database.Project).count() == 1


def test_task_crud_and_stale_write_protection(client):
    task = create_task(client, description="A test task")
    response = client.patch(f"/api/tasks/{task['id']}", json={
        "status": "In Progress", "expected_revision": task["revision"]
    })
    assert response.status_code == 200
    assert response.json()["revision"] == task["revision"] + 1
    stale = client.patch(f"/api/tasks/{task['id']}", json={
        "title": "Stale edit", "expected_revision": task["revision"]
    })
    assert stale.status_code == 409
    assert client.get(f"/api/tasks/{task['id']}").json()["title"] == task["title"]
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 200
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404


def test_nested_tasks_and_atomic_sprint_assignment(client):
    sprint = client.post("/api/sprints/", json={"month": "2026-10", "goal": "Release"})
    assert sprint.status_code == 201
    sprint_id = sprint.json()["id"]
    assert client.post("/api/sprints/", json={"month": "2026-10"}).status_code == 409
    root = create_task(client)
    child = create_task(client, parent_id=root["id"])
    grandchild = create_task(client, parent_id=child["id"])
    response = client.post("/api/tasks/assign-sprint", json={
        "task_ids": [root["id"]], "sprint_id": sprint_id
    })
    assert response.status_code == 200
    assert response.json()["updated_task_ids"] == [root["id"], child["id"], grandchild["id"]]
    assert all(task["sprint_id"] == sprint_id for task in client.get("/api/tasks/").json())
    assert client.get(f"/api/tasks/{grandchild['id']}/ancestors").json() == [
        {"id": root["id"], "title": root["title"]},
        {"id": child["id"], "title": child["title"]},
    ]
    assert client.patch(f"/api/tasks/{root['id']}", json={"parent_id": grandchild["id"]}).status_code == 400
    assert client.delete(f"/api/sprints/{sprint_id}").status_code == 409
    assert client.delete(f"/api/tasks/{root['id']}").status_code == 409


def test_followup_retry_and_resolution_are_independent(client):
    task = create_task(client)
    payload = {"title": "Decide release scope", "kind": "Decision", "source_key": "release-scope"}
    need = client.post(f"/api/tasks/{task['id']}/needed-tasks", json=payload)
    assert need.status_code == 200
    need_id = need.json()["id"]
    assert client.post(f"/api/tasks/{task['id']}/needed-tasks", json=payload).json()["id"] == need_id
    changed = client.post(f"/api/tasks/{task['id']}/needed-tasks", json={**payload, "title": "Different"})
    assert changed.status_code == 409
    linked = client.post(f"/api/needed-tasks/{need_id}/materialize", json={})
    assert linked.status_code == 200
    child_id = linked.json()["linked_task_id"]
    assert client.post(f"/api/needed-tasks/{need_id}/materialize", json={}).json()["linked_task_id"] == child_id
    assert client.patch(f"/api/tasks/{child_id}", json={"status": "Complete"}).status_code == 200
    assert client.get("/api/needed-tasks/?open_only=true").json()[0]["state"] == "Linked"
    assert client.patch(f"/api/needed-tasks/{need_id}", json={"state": "Resolved"}).status_code == 422
    assert client.patch(f"/api/needed-tasks/{need_id}", json={
        "state": "Resolved", "resolution": "Scope agreed", "expected_revision": linked.json()["revision"]
    }).status_code == 200
    assert client.get("/api/needed-tasks/?open_only=true").json() == []


def test_resolution_and_task_input_validation(client):
    assert client.post("/api/tasks/", json={"title": "   "}).status_code == 422
    assert client.post("/api/tasks/", json={"title": "Test", "status": "Unknown"}).status_code == 422
    assert client.post("/api/tasks/", json={"title": "Test", "resolution_state": "Resolved"}).status_code == 422
    task = create_task(client, resolution_state="Deferred", resolution="Next month")
    assert task["status"] == "Backlog"
    assert client.get("/api/tasks/?resolution_state=Deferred").json()[0]["id"] == task["id"]


def test_epic_and_assignee_endpoints(client):
    user = client.post("/api/users/add/", json={"name": "Release tester"})
    assert user.status_code == 200
    assert client.post("/api/users/add/", json={"name": "Release tester"}).status_code == 409
    assert client.put(f"/api/users/{user.json()['id']}/", json={"name": "Tester"}).status_code == 200
    epic = client.post("/api/epics/", json={"title": "Release", "color": "#48d597"})
    assert epic.status_code == 200
    task = create_task(client, epic_id=epic.json()["id"])
    assert client.delete(f"/api/epics/{epic.json()['id']}").status_code == 200
    assert client.get(f"/api/tasks/{task['id']}").json()["epic_id"] is None
    assert client.delete(f"/api/users/{user.json()['id']}/").status_code == 200


def test_mcp_tools_against_api(client, monkeypatch):
    from MCP import ignatious

    def request_api(method, path, payload=None):
        response = client.request(method, path, json=payload)
        response.raise_for_status()
        return response.json()

    monkeypatch.setattr(ignatious, "_request", request_api)
    server = FastMCP("test")
    ignatious.register_tools(server)

    async def check_tools():
        tools = await server.list_tools()
        assert len(tools) == 25
        assert {"assign_ignatious_sprint", "materialize_ignatious_needed_task"} <= {tool.name for tool in tools}
        result = await server.call_tool("create_ignatious_task", {"title": "MCP task", "description": "Clear me"})
        task = json.loads(result[0][0].text)
        updated = await server.call_tool("update_ignatious_task", {
            "task_id": task["id"], "clear_fields": ["description"], "expected_revision": task["revision"]
        })
        assert json.loads(updated[0][0].text)["description"] is None
        with pytest.raises(Exception, match="Cannot set and clear"):
            await server.call_tool("update_ignatious_task", {
                "task_id": task["id"], "description": "Conflict", "clear_fields": ["description"]
            })

    asyncio.run(check_tools())


def test_mcp_http_error_reporting(monkeypatch):
    from MCP import ignatious
    from io import BytesIO

    mocked = Mock(side_effect=HTTPError("http://localhost", 409, "Conflict", {}, BytesIO(b"stale edit")))
    monkeypatch.setattr(ignatious, "urlopen", mocked)
    with pytest.raises(RuntimeError, match="HTTP 409: stale edit"):
        ignatious._request("PATCH", "/api/tasks/1", {"title": "New"})
    mocked.side_effect = URLError("connection refused")
    with pytest.raises(RuntimeError, match="Unable to reach Ignatious"):
        ignatious._request("GET", "/api/tasks/")


def test_mcp_stdio_entrypoint():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def check_stdio():
        parameters = StdioServerParameters(
            command=sys.executable, args=[str(ROOT / "MCP" / "ignatious.py")]
        )
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) == 25

    asyncio.run(check_stdio())


def test_legacy_database_migration_is_idempotent(tmp_path):
    path = tmp_path / "legacy.db"
    environment = {**os.environ, "IGNATIOUS_DATABASE_URL": f"sqlite:///{path.as_posix()}"}
    script = """
import sqlite3
import database
connection = sqlite3.connect(database.engine.url.database)
connection.executescript('''
CREATE TABLE projects (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL);
CREATE TABLE tasks (id INTEGER PRIMARY KEY, title VARCHAR NOT NULL, description VARCHAR,
    status VARCHAR NOT NULL, assignee VARCHAR, project_id INTEGER);
CREATE TABLE subtasks (id INTEGER PRIMARY KEY, title VARCHAR NOT NULL,
    is_complete BOOLEAN, task_id INTEGER);
INSERT INTO projects VALUES (1, 'Legacy');
INSERT INTO tasks VALUES (1, 'Parent', NULL, 'BACKLOG', NULL, 1);
INSERT INTO subtasks VALUES (1, 'Legacy child', 1, 1);
''')
connection.close()
database.init_db()
database.init_db()
with database.SessionLocal() as session:
    assert session.query(database.Task).count() == 2
    child = session.query(database.Task).filter_by(legacy_subtask_id=1).one()
    assert child.parent_id == 1
    assert child.status == database.TaskStatus.COMPLETE
database.engine.dispose()
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=environment,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr