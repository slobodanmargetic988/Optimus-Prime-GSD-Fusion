# Linear MCP

## Purpose
Connect Codex to Linear workspace data (issues, projects, comments, statuses).

## Prerequisites
- Linear workspace access
- MCP server configured in Codex MCP config
- Valid Linear API auth configured in environment

## Setup Notes
- Use environment variables for credentials.
- Validate the authenticated user/workspace before issue edits.
- Restart Codex after adding or changing MCP server config.

## Validation
- Query current user identity.
- List a small issue set in the expected workspace/team.
- Confirm read access before write operations.

## Common Failure Modes
- Token lacks required workspace scope
- Wrong team/workspace identifiers
- Stale runtime after config edits (restart required)
