# Ignatious

A self-hosted personal Kanban board with monthly planning, nested tasks, and an optional Model Context Protocol (MCP) server. Your board lives in a local SQLite database. The web interface needs no Node.js build step or external service.

## Features

- Backlog and Kanban views: Backlog, Ready for Action, In Progress, In Review, and Complete.
- Monthly sprints with goals and branch-wide scheduling.
- Nested task boards, ancestor navigation, and completion counts.
- Epics, assignees, and a team workload view.
- Resolution notes and review outcomes independent of task completion.
- A queue of needed decisions, investigations, and actions that can become linked tasks without duplicate work.
- Revision checks to reject stale updates.
- Light, dark, and cyber-green themes.
- An optional MCP adapter with 25 tools for managing tasks, epics, assignees, sprints, and follow-ups.

## Quick Start

Requirements: Python 3.11 or newer, Git, and a browser. Run these commands from your clone of this repository.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Linux / macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. Interactive API documentation is at <http://127.0.0.1:8000/docs>.

The first start creates `ignatious.db`, a default project (ID 1), and four sample assignees. Tasks start empty. Add, rename, or remove assignees in the team view. Assignees are labels, not login accounts.

**Security boundary:** Ignatious has no authentication or authorization. Anyone who can reach the service can read, change, or delete board data. Keep the default loopback binding. Do not expose it directly to the internet. See [SECURITY.md](SECURITY.md) before enabling remote access.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `IGNATIOUS_DATABASE_URL` | `sqlite:///./ignatious.db` | SQLite database location, relative to the server's working directory. |
| `IGNATIOUS_URL` | `http://127.0.0.1:8000` | API base URL used by the MCP adapter. |

Only SQLite is supported: several atomic operations and migrations use SQLite-specific SQL. PostgreSQL and other SQLAlchemy URLs are not supported. The database directory must already exist and be writable. Environment variables must be set in the process environment; `.env` files are not automatically loaded.

For a different database on Windows:

```powershell
$env:IGNATIOUS_DATABASE_URL = "sqlite:///C:/path/to/ignatious.db"
```

On Linux / macOS:

```sh
export IGNATIOUS_DATABASE_URL=sqlite:////absolute/path/to/ignatious.db
```

Use Uvicorn's `--host` and `--port` options to change the listener. For development, add `--reload`. Use a single worker; initialization performs schema updates at startup.

## MCP Integration

The MCP server is an optional HTTP client for the web API. Start the web service separately, then follow [MCP/README.md](MCP/README.md) to install the SDK and configure a stdio client, or register the tools with an existing `FastMCP` server.

The adapter can mutate and delete data. Use a test board when experimenting with an agent, and enable tool approval in your MCP client.

## Backups and Upgrades

1. Stop the web service and any process writing to the database.
2. Copy the SQLite file to a safe location outside the repository.
3. Update the source and reinstall dependencies with the relevant quick-start command.
4. Restart. Missing columns are added automatically; old checklist subtasks are migrated once into nested tasks.

Always back up before upgrading an existing instance. Startup migrations are not a substitute for backups. To restore, stop the service and replace the database with your backup. Do not commit databases, backups, or credentials to Git.

## Linux Service

[ignatious.service](ignatious.service) is an example, not an installer. It assumes a clone and virtual environment at `/opt/ignatious`, and a dedicated `ignatious` system user. Customize those paths before installation. The unit binds to loopback and stores its database under `/var/lib/ignatious`, which systemd creates with `StateDirectory`.

After creating the system user, installing dependencies, and ensuring that user can read the source and execute the virtual environment:

```sh
sudo install -m 644 ignatious.service /etc/systemd/system/ignatious.service
sudo systemctl daemon-reload
sudo systemctl enable --now ignatious
journalctl -u ignatious
```

Access a remote instance through an SSH tunnel rather than opening its port:

```sh
ssh -L 8000:127.0.0.1:8000 user@your-host
```

## Development

Install `requirements-dev.txt` into your virtual environment, then run:

```sh
python -m pytest tests -q
```

Use the virtual environment's Python executable if it is not activated. Tests use temporary SQLite databases and do not read or modify your board. CI runs the checks on Windows and Linux across the declared Python versions.

See [CONTRIBUTING.md](CONTRIBUTING.md), [API notes](documentation/ignatious.md), and the [release checklist](documentation/releasing.md).

## License

MIT. See [LICENSE](LICENSE). Contributions are provided under the same license.