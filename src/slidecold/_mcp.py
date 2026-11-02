"""MCP server exposing one tool per SlideCold API operation (requires the `mcp` extra)."""

import json
import os
from typing import Any, Dict, List, Optional

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from ._client import AsyncSlideCold
from ._exceptions import SlideColdError
from ._operations import OPERATIONS, Operation
from ._version import __version__

INSTRUCTIONS = (
    "Tools for the SlideCold API (Instagram cold-DM outreach). Each tool needs the API key scope named in its "
    "description; a 403 means the key lacks that scope or a plan limit was hit. Login jobs (create_account, "
    "relogin_account, check_account_session) return a jobId to poll with get_login_status."
)


def tool_schema(op: Operation) -> Dict[str, Any]:
    props: Dict[str, Any] = {}
    required: List[str] = []
    for p in (*op.path_params, *op.query_params):
        props[p.name] = {**p.schema, **({"description": p.description} if p.description else {})}
        if p.required:
            required.append(p.name)
    if op.body_schema is not None:
        if op.body_flat:
            props.update(op.body_schema.get("properties", {}))
            if op.body_required:
                required += op.body_schema.get("required", [])
        else:
            props["body"] = op.body_schema
            if op.body_required and not op.file_field:
                required.append("body")
    if op.file_field:
        props["file_path"] = {
            "type": "string",
            "description": f"Path to a local file to upload as `{op.file_field}`.",
        }
        if op.body == "multipart":
            required.append("file_path")
    schema: Dict[str, Any] = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


def make_tool(op: Operation) -> types.Tool:
    description = op.summary + "."
    if op.description:
        description += "\n\n" + op.description
    description += f"\n\nRequired API key scope: {op.scope}"
    read_only = op.method == "GET"
    return types.Tool(
        name=op.tool,
        description=description,
        input_schema=tool_schema(op),
        annotations=types.ToolAnnotations(
            title=op.summary,
            read_only_hint=read_only,
            destructive_hint=None if read_only else op.destructive,
        ),
    )


TOOLS = {op.tool: (op, make_tool(op)) for op in OPERATIONS.values()}


def _text(text: str, error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=error)


def build_server(client: Optional[AsyncSlideCold] = None) -> Server:
    """Build the server. Without `client`, one is created on the first tool call from env/config."""
    state: Dict[str, AsyncSlideCold] = {"client": client} if client else {}

    async def list_tools(ctx: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[tool for _, tool in TOOLS.values()])

    async def call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        if params.name not in TOOLS:
            return _text(f"Unknown tool: {params.name}", error=True)
        op = TOOLS[params.name][0]
        args = dict(params.arguments or {})
        try:
            if "client" not in state:
                state["client"] = AsyncSlideCold()
            file_path = args.pop("file_path", None)
            path = {p.name: args.pop(p.name, None) for p in op.path_params}
            query = {q.name: args.pop(q.name, None) for q in op.query_params}
            body = (args or None) if op.body_flat else args.pop("body", None)
            result = await state["client"].request(
                op.id,
                path=path,
                query=query,
                body=body,
                file=os.path.expanduser(file_path) if file_path else None,
            )
        except (SlideColdError, ValueError, OSError) as e:
            return _text(str(e), error=True)
        if result is None:
            return _text("OK")
        return _text(result if isinstance(result, str) else json.dumps(result, indent=2, ensure_ascii=False))

    return Server(
        "slidecold",
        version=__version__,
        instructions=INSTRUCTIONS,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


async def serve_stdio() -> None:
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
