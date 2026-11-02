import httpx
import pytest
import respx

from slidecold import APIError, AsyncSlideCold, PermissionDeniedError

from .conftest import BASE

pytestmark = pytest.mark.anyio


@respx.mock
async def test_async_client():
    route = respx.get(f"{BASE}/campaigns/c1/stats").mock(
        side_effect=[httpx.Response(502), httpx.Response(200, json={"totalSent": 3})]
    )
    async with AsyncSlideCold(api_key="cs_async", base_url=BASE) as client:
        assert await client.campaigns.stats("c1") == {"totalSent": 3}
        assert route.calls.last.request.headers["authorization"] == "Bearer cs_async"

        post = respx.post(f"{BASE}/conversations/c1/reply").respond(500)
        with pytest.raises(APIError):
            await client.conversations.send_reply("c1", message="hi")
        assert post.call_count == 1

        respx.delete(f"{BASE}/audiences/a1").respond(403, json={"error": "missing audiences:write"})
        with pytest.raises(PermissionDeniedError, match="audiences:write"):
            await client.audiences.delete("a1")

        respx.get(f"{BASE}/accounts/login-status").respond(json={"state": "failed", "error": "bad password"})
        assert (await client.wait_for_login_job("j1"))["error"] == "bad password"
