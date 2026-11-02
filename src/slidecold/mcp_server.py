"""Entry point for `slidecold-mcp`, a stdio MCP server for the SlideCold API."""

import sys

INSTALL_HINT = (
    "slidecold-mcp needs the optional MCP dependencies (Python 3.10+). Install them with:\n"
    "    pip install 'slidecold[mcp]'\n"
    "or run it without installing:\n"
    "    uvx --from 'slidecold[mcp]' slidecold-mcp"
)


def main() -> None:
    try:
        import anyio

        from ._mcp import serve_stdio
    except ImportError:
        print(INSTALL_HINT, file=sys.stderr)
        sys.exit(1)
    anyio.run(serve_stdio)


if __name__ == "__main__":
    main()
