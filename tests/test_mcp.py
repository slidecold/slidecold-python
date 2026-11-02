import json

import pytest
import respx

pytest.importorskip("mcp")

from mcp import Client  # noqa: E402

from slidecold import AsyncSlideCold  # noqa: E402
from slidecold._mcp import build_server  # noqa: E402

from .conftest import BASE  # noqa: E402

pytestmark = pytest.mark.anyio


async def test_lists_one_tool_per_operation():
    async with Client(build_server()) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert len(tools) == 49
    stats = tools["get_campaign_stats"]
    assert "campaigns:read" in stats.description
    assert stats.annotations.read_only_hint is True
    assert stats.input_schema["required"] == ["id"]
    assert tools["delete_campaign"].annotations.destructive_hint is True
    assert tools["send_conversation_reply"].annotations.destructive_hint is True
    assert tools["create_campaign"].annotations.destructive_hint is False
    assert "templates" in tools["create_campaign"].input_schema["required"]
    assert "file_path" in tools["send_conversation_photo"].input_schema["required"]


@respx.mock
async def test_call_tool_success_and_error():
    respx.get(f"{BASE}/campaigns/c1/stats").respond(json={"totalSent": 7})
    respx.post(f"{BASE}/campaigns").respond(
        403, json={"error": "This API key is missing the campaigns:write scope"}
    )
    server = build_server(AsyncSlideCold(api_key="cs_mcp", base_url=BASE))
    async with Client(server) as client:
        ok = await client.call_tool("get_campaign_stats", {"id": "c1"})
        assert not ok.is_error and json.loads(ok.content[0].text) == {"totalSent": 7}
        err = await client.call_tool("create_campaign", {"name": "x", "audienceIds": ["a"]})
        assert err.is_error and "missing the campaigns:write scope" in err.content[0].text
    assert respx.calls.last.request.read() == b'{"name":"x","audienceIds":["a"]}'
