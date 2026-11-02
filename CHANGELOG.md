# Changelog

## 0.2.0

This package is now the SDK only.

- The `slidecold` CLI moved to [slidecold-cli](https://github.com/slidecold/slidecold-cli) (Go). Its
  `slidecold login` writes the same `~/.config/slidecold/config.json`, which the SDK still reads.
- The `slidecold-mcp` MCP server moved to [slidecold-mcp](https://github.com/slidecold/slidecold-mcp)
  (TypeScript, `npx -y slidecold-mcp`). The `[mcp]` extra is gone; `pip install 'slidecold[mcp]'` now installs
  only the SDK.
- Removed the `slidecold` and `slidecold-mcp` console scripts and the internal `_config.save_config`.

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
