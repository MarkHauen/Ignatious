# Ignatious MCP Server

This optional adapter exposes 25 tools using the official Python MCP SDK. It forwards requests to the Ignatious HTTP API; it does not start the web app or access SQLite directly.

## Install and Run

Start Ignatious using the root [README](../README.md), then install the optional SDK from the repository root:

```sh
python -m pip install -r MCP/requirements.txt
python MCP/ignatious.py
```

Use your virtual environment's Python executable. The second command starts a **stdio** MCP server and waits for a client; it is not an interactive command-line interface. No additional network listener is opened.

`IGNATIOUS_URL` defaults to `http://127.0.0.1:8000`. Set it in the MCP process environment if your API uses another address. Requests time out after 10 seconds; HTTP and connection errors are reported to the client. The adapter provides no authentication layer.

## Client Configuration

For clients that accept an `mcpServers` configuration, replace the executable and script paths with absolute paths to your clone:

```json
{
  "mcpServers": {
    "ignatious": {
      "command": "/absolute/path/to/Ignatious/.venv/bin/python",
      "args": ["/absolute/path/to/Ignatious/MCP/ignatious.py"],
      "env": {
        "IGNATIOUS_URL": "http://127.0.0.1:8000"
      }
    }
  }
}
```

On Windows, use `.venv/Scripts/python.exe` and Windows absolute paths with forward slashes, or escape backslashes in JSON. For VS Code's `.vscode/mcp.json`, use `servers` instead of `mcpServers` and add `"type": "stdio"` to the server entry. Keep machine-specific client configuration out of the repository.

## Existing Server

To add the tools to your existing official `FastMCP` server, make the repository root importable and register them before running your server:

```python
from mcp.server.fastmcp import FastMCP
from MCP.ignatious import register_tools

server = FastMCP("My local tools")
register_tools(server)
server.run(transport="stdio")
```

Other MCP frameworks must support the same `tool` decorator contract; they are not tested by this repository. `mcp.server.MCPServer` is not the official SDK registration API used here.

## Tool Behavior

- Discover valid status labels with `list_ignatious_statuses`.
- New tasks default to Backlog and project 1.
- Child tasks inherit their parent's sprint. Move an entire branch with `assign_ignatious_sprint`.
- Send the last-read `expected_revision` when updating tasks or needed items to reject stale edits.
- `update_ignatious_task` supports `clear_fields` for nullable fields. Do not set and clear a field in the same request.
- Use a stable `source_key` when importing needed items so retries do not duplicate suggestions.
- Materialization creates or links work; completing that work does not automatically resolve its originating needed item.
- Resolution, review, and task completion are distinct states. Non-unresolved resolutions require an explanation.
- Deletion may be refused to preserve nested tasks or follow-up audit trails.

Approve mutating tools deliberately. Do not connect an agent to a board containing sensitive data unless you trust the client, model provider, and tool permissions.