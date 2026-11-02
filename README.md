# SlideCold Python SDK

The official Python client for the [SlideCold](https://slidecold.com) API (Instagram cold-DM outreach):
`SlideCold` and `AsyncSlideCold` clients with typed methods for every API operation, generated from the
[OpenAPI spec](openapi.yaml).

Looking for a command line or an MCP server? They live in their own repos:

- **CLI**: [slidecold/slidecold-cli](https://github.com/slidecold/slidecold-cli) (`slidecold login`, `slidecold campaigns list`, ...)
- **MCP server**: [slidecold/slidecold-mcp](https://github.com/slidecold/slidecold-mcp) (`npx -y slidecold-mcp`)

## Install

```bash
pip install slidecold    # Python 3.9+, the only dependency is httpx
```

Create an API key at <https://slidecold.com/settings>. Keys look like `cs_...`.

## Authentication

The API key is resolved in this order:

1. the `api_key=` argument
2. the `SLIDECOLD_API_KEY` environment variable
3. the config file written by `slidecold login` from [slidecold-cli](https://github.com/slidecold/slidecold-cli):
   `~/.config/slidecold/config.json`
   (`$XDG_CONFIG_HOME/slidecold/config.json` if set, `%APPDATA%\slidecold\config.json` on Windows)

The base URL follows the same order (`base_url=`, `SLIDECOLD_BASE_URL`, config `baseUrl`), then defaults to
`https://slidecold.com/api/v1`. The config file is `{"apiKey": "cs_...", "baseUrl": "..."}`. The SDK only reads
it; it never writes it.

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
operation is shown in its method docstring.

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

## Development

```bash
uv sync
uv run python scripts/generate.py          # regenerate from openapi.yaml
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
```

`src/slidecold/_operations.py`, `_resources.py` and `types.py` are generated from `openapi.yaml` and committed.
CI fails if they are stale.

## License

MIT
