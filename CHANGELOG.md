# Changelog

## 0.1.0

Initial release.

- `SlideCold` and `AsyncSlideCold` clients covering all 49 operations of the SlideCold API v1, grouped by
  resource (`campaigns`, `audiences`, `conversations`, `accounts`, `proxies`, `folders`), generated from
  `openapi.yaml`, with TypedDicts for models and request bodies.
- Typed errors (`AuthenticationError`, `PermissionDeniedError`, `NotFoundError`, `RateLimitError`, `APIError`,
  `APIConnectionError`), GET retries with exponential backoff, `wait_for_login_job`.
- `verify_webhook_signature` for `X-SlideCold-Signature`.
- `slidecold` CLI with `login` / `logout` and one command per operation.
- `slidecold-mcp` stdio MCP server (`pip install 'slidecold[mcp]'`) with one tool per operation.
