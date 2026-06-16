---
name: commit-history
description: Показывает последние git-коммиты связанные с сессиями агента, с фильтрацией по ветке или репо. Используй когда пользователь спрашивает "покажи коммиты агента", "что агент отправил", или хочет список коммитов с контекстом сессий.
argument-hint: "[branch=... repo=... limit=...]"
user-invocable: true
---

The user wants a list of agent-linked commits. Filter args: $ARGUMENTS

Parse `$ARGUMENTS` for optional `branch=<name>`, `repo=<url-or-fragment>`, and `limit=<n>` tokens. A bare numeric token becomes the limit. Defaults: no branch filter, no repo filter, limit 100, max 500.

Call the `memory_commits` MCP tool with the parsed filters. If the MCP tool is unavailable, fall back to HTTP: build `GET $AGENTMEMORY_URL/agentmemory/commits` and append each filter as a URL-encoded query parameter (use `URLSearchParams` or `encodeURIComponent` on `branch`, `repo`, and `limit`) so values containing `?`, `&`, or `#` cannot corrupt the request. Include `Authorization: Bearer $AGENTMEMORY_SECRET` when set.

Render the result as a reverse-chronological list:
- Short SHA, branch, authored timestamp
- Commit message first line
- Linked session id(s) (first 8 chars each) and observation counts where present
- File count when `files` is provided

If the result is empty, tell the user the filter matched no commits and suggest dropping the branch/repo filter. Do not invent commits.
