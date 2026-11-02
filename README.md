# SlideCold Python SDK, CLI and MCP server

The official Python client for the [SlideCold](https://slidecold.com) API (Instagram cold-DM outreach).
One package gives you:

- **SDK**: `SlideCold` and `AsyncSlideCold` clients with typed methods for every API operation.
- **CLI**: `slidecold campaigns list`, `slidecold audiences export <id>`, and so on.
- **MCP server**: `slidecold-mcp`, which gives Claude, Cursor and other MCP clients one tool per API operation.

Everything is generated from the [OpenAPI spec](openapi.yaml), so the SDK, the CLI and the MCP tools always match the API.

## Install

```bash
pip install slidecold            # SDK and CLI (Python 3.9+, the only dependency is httpx)
pip install 'slidecold[mcp]'     # also the MCP server (Python 3.10+)
```

Create an API key at <https://slidecold.com/settings>. Keys look like `cs_...`.

## Authentication

The API key is resolved in this order:

1. the `api_key=` argument (or `--api-key` on the CLI)
2. the `SLIDECOLD_API_KEY` environment variable
3. the config file written by `slidecold login`: `~/.config/slidecold/config.json`
   (`$XDG_CONFIG_HOME/slidecold/config.json` if set, `%APPDATA%\slidecold\config.json` on Windows)

The base URL follows the same order (`base_url=`, `SLIDECOLD_BASE_URL`, config `baseUrl`), then defaults to
`https://slidecold.com/api/v1`. The config file is `{"apiKey": "cs_...", "baseUrl": "..."}`, the same format
the SlideCold Node and Go CLIs use.

## SDK quickstart

```python
from slidecold import SlideCold

with SlideCold() as client:  # or SlideCold(api_key="cs_...")
    for campaign in client.campaigns.list():
        print(campaign["id"], campaign["name"], campaign["status"])

    campaign = client.campaigns.create(
        name="Spring outreach",
        audienceIds=["aud_123"],
        accountIds=["acc_456"],
        templates=[{"body": "Hey, quick question about your page"}],
    )
    print(client.campaigns.stats(campaign["id"]))

    csv_text = client.audiences.export("aud_123")  # str
    members = client.audiences.list_members("aud_123", min_followers=1000, limit=50)
    client.conversations.send_reply("conv_789", message="Thanks, sending details now")
    client.conversations.send_photo("conv_789", file="offer.jpg")
```

Request bodies use the API's field names. Pass them as keyword arguments, as a dict, or both:
`client.campaigns.update(id, {"status": "ACTIVE"})` is the same as `client.campaigns.update(id, status="ACTIVE")`.
Path parameters are positional and query parameters are snake_case keyword arguments. Every method's
docstring lists the scope it needs. Responses are plain dicts and lists, typed with the TypedDicts in
`slidecold.types`.

### Async

```python
import asyncio
from slidecold import AsyncSlideCold


async def main():
    async with AsyncSlideCold() as client:
        accounts, campaigns = await asyncio.gather(client.accounts.list(), client.campaigns.list())


asyncio.run(main())
```

### Instagram login jobs

Adding an account, re-logging in and session checks run in the background and return `{"jobId": ...}`.
`wait_for_login_job` polls `accounts.login_status` until the job finishes:

```python
job = client.accounts.create(username="mybrand", password="...", proxyId="prx_1")
status = client.wait_for_login_job(job["jobId"], interval=2, timeout=120)
if status["state"] == "failed":
    print(status.get("error"))
```

It returns the final status (`completed`, `failed` or `unknown`) and raises `TimeoutError` after `timeout` seconds.
`AsyncSlideCold.wait_for_login_job` is the async version.

### Options

`SlideCold(api_key=None, base_url=None, timeout=30, max_retries=2)`. GET requests are retried on 429, 5xx and
connection errors with exponential backoff (honouring `Retry-After`). Other methods are never retried, so a
DM is never sent twice. `client.request("operationId", path=..., query=..., body=...)` calls any operation by
its OpenAPI `operationId`.

## Scopes

Each API key has scopes of the form `<resource>:<read|write>` for `accounts`, `audiences`, `campaigns` and
`conversations`. A `:write` scope also grants `:read`. Proxies use the `accounts` scopes. The scope for each
operation is shown in method docstrings, in `slidecold <resource> <action> --help`, and in each MCP tool's
description.

## Errors

All errors derive from `slidecold.SlideColdError` and carry `status`, `message` (the API's `error` string)
and `body` (the parsed response).

| Exception | When |
| --- | --- |
| `AuthenticationError` | 401: the key is missing or invalid |
| `PermissionDeniedError` | 403: the key lacks a scope (`This API key is missing the campaigns:write scope`) or a plan limit was hit |
| `NotFoundError` | 404 |
| `RateLimitError` | 429 |
| `APIError` | any other error status (base class of the four above) |
| `APIConnectionError` | no response: DNS, connection or timeout |

```python
from slidecold import PermissionDeniedError

try:
    client.campaigns.delete("cmp_1")
except PermissionDeniedError as e:
    print(e.status, e.message)
```

## Webhooks

SlideCold signs each webhook with an `X-SlideCold-Signature` header: the hex HMAC-SHA256 of the raw JSON
body, keyed with the endpoint secret (`whsec_...`). Verify it against the raw bytes, before parsing:

```python
from slidecold import verify_webhook_signature


@app.post("/webhooks/slidecold")  # Flask
def slidecold_webhook():
    if not verify_webhook_signature(
        request.get_data(), request.headers.get("X-SlideCold-Signature", ""), WHSEC
    ):
        abort(401)
    event = request.get_json()
    ...
```

## CLI

```bash
slidecold login                      # prompts for the key, checks it, saves it (0600)
slidecold login --key cs_...         # non-interactive
slidecold logout

slidecold campaigns list
slidecold campaigns list --archived true
slidecold campaigns get cmp_123
slidecold campaigns stats cmp_123
slidecold campaigns create --data '{"name": "Spring", "audienceIds": ["aud_1"], "accountIds": ["acc_1"], "templates": [{"body": "Hi!"}]}'
slidecold campaigns update cmp_123 --data @patch.json
slidecold audiences list-members aud_1 --min-followers 1000 --limit 50
slidecold audiences export aud_1 > members.csv
slidecold audiences import-members aud_1 --file members.csv
slidecold conversations send-photo conv_1 --file offer.jpg
slidecold accounts login-status --job-id job_1
```

The shape is `slidecold <resource> <action> [ids] [--param value] [--data JSON | --data @file.json] [--file path]`.
Run `slidecold --help`, `slidecold campaigns --help` or `slidecold campaigns create --help` (which shows the
required scope). Output is pretty-printed JSON, or raw CSV for exports. Errors go to stderr with exit code 1.
`--api-key` and `--base-url` override the key and URL for one command.

## MCP server

`slidecold-mcp` is a stdio MCP server with one tool per API operation (`list_campaigns`,
`get_campaign_stats`, `send_conversation_reply`, ...). Read-only tools are marked `readOnlyHint`, and deletes
and DM sends are marked `destructiveHint`. Upload tools take a local `file_path`.

**Claude Code**

```bash
claude mcp add slidecold -e SLIDECOLD_API_KEY=cs_... -- uvx --from 'slidecold[mcp]' slidecold-mcp
```

**Claude Desktop** (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "slidecold": {
      "command": "uvx",
      "args": ["--from", "slidecold[mcp]", "slidecold-mcp"],
      "env": { "SLIDECOLD_API_KEY": "cs_..." }
    }
  }
}
```

**Cursor** (`~/.cursor/mcp.json` or `.cursor/mcp.json` in a project) uses the same `mcpServers` block as
Claude Desktop.

If you ran `slidecold login`, you can leave out `SLIDECOLD_API_KEY` and the server will use the saved key.
Give the server a key with only the scopes you want the assistant to have, for example `campaigns:read` and
`conversations:read` for a read-only assistant.

## Development

```bash
uv sync --all-extras
uv run python scripts/generate.py          # regenerate from openapi.yaml
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
```

`src/slidecold/_operations.py`, `_resources.py` and `types.py` are generated from `openapi.yaml` and committed.
CI fails if they are stale.

## License

MIT
