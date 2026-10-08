# Release Checklist

## Before Making the Repository Public

- Review all files and **all Git history**, not only the current snapshot, for board data, secrets, hostnames, and machine-specific configuration.
- Confirm no SQLite databases, database sidecars, bytecode, virtual environments, or personal MCP configuration are tracked.
- If private data was committed, remove it from history before publication. Coordinate rewritten history with existing collaborators; do not merge the old history back in.
- Keep any pre-cleanup Git bundles or backups private and outside this repository. They may still contain personal data.
- Rotate any credentials that were exposed. History cleanup does not revoke secrets or remove copies from existing clones or remote caches.
- Confirm you have permission to release the code and assets under the MIT license.
- Verify the README instructions in a fresh clone and check the MCP client paths on your platform.
- Run `python -m pytest tests -q` in a virtual environment with `requirements-dev.txt` installed.

## GitHub Setup

- Create or configure the destination repository and check its visibility before uploading history.
- Enable private vulnerability reporting, Dependabot alerts, and available secret-scanning protections.
- Require the CI checks on your default branch and enable pull-request review protections as appropriate.
- Set a repository description and topics such as `kanban`, `self-hosted`, `fastapi`, `sqlite`, and `mcp`.
- Verify both Windows and Linux CI jobs before tagging the first release.
- Choose a version tag, write release notes describing features and known limitations, and explicitly state that the service has no built-in authentication.

Publishing, pushing rewritten history, and creating tags or GitHub releases are maintainer actions. Never force-push rewritten history without coordinating existing remote branches and clones.