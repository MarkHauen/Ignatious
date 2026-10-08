# Security

## Intended Deployment

Ignatious is a personal, local-first tool. It currently has **no login, authentication, authorization, or user isolation**. Assignees are labels, not accounts. All reachable API routes are available to anyone who can connect, including write and delete operations.

- Bind to `127.0.0.1` by default. Do not expose the service directly to the public internet.
- For remote access, prefer an SSH tunnel. A private network is not an authentication mechanism: every permitted peer must be trusted.
- If using a reverse proxy, provide authentication, HTTPS, and appropriate request-origin/CSRF protections there. None are supplied by this application.
- Keep the database and backups private and outside the web-served `static` directory. SQLite data is not encrypted by the application.
- Run under an unprivileged account and restrict database file permissions.
- Treat MCP clients as privileged API users. Agents can change or delete data, and client/model providers may receive task contents. Require approval for mutating tools where supported.
- Keep dependencies updated and back up before applying upgrades.

The application is not intended as a public multi-tenant service. Internet deployment requires additional security design, not merely changing the listener address.

## Reporting Vulnerabilities

Use GitHub's private vulnerability reporting feature in the repository's Security tab when enabled. If it is unavailable, ask the maintainer for a private reporting channel without posting exploit details or sensitive data in a public issue.

Include affected versions, reproduction steps using synthetic data, and the likely impact. Do not include live credentials, databases, or personal tasks. Security fixes target the latest source revision; older releases have no promised backport support.