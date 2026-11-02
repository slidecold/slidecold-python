import httpx
import pytest
import respx

import slidecold
from slidecold import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    SlideCold,
)
from slidecold._operations import OPERATIONS

from .conftest import BASE


@pytest.fixture
def client():
    with SlideCold(api_key="cs_test", base_url=BASE) as c:
        yield c


@respx.mock
def test_auth_and_user_agent_headers(client):
    route = respx.get(f"{BASE}/campaigns").respond(json=[{"id": "c1"}])
    assert client.campaigns.list() == [{"id": "c1"}]
    req = route.calls.last.request
    assert req.headers["authorization"] == "Bearer cs_test"
    assert req.headers["user-agent"] == f"slidecold-python/{slidecold.__version__}"


@pytest.mark.parametrize(
    "status,cls",
    [
        (401, AuthenticationError),
        (403, PermissionDeniedError),
        (404, NotFoundError),
        (429, RateLimitError),
        (400, APIError),
        (500, APIError),
    ],
)
@respx.mock
def test_error_mapping(client, status, cls):
    respx.post(f"{BASE}/campaigns").respond(status, json={"error": "nope", "field": "x"})
    with pytest.raises(cls) as exc:
        client.campaigns.create(name="x")
    assert exc.value.status == status
    assert exc.value.body == {"error": "nope", "field": "x"}
    assert exc.value.message.startswith("nope")
    assert isinstance(exc.value, slidecold.SlideColdError)


@respx.mock
def test_401_points_to_settings(client):
    respx.get(f"{BASE}/campaigns").respond(401, json={"error": "Invalid API key"})
    with pytest.raises(AuthenticationError, match="https://slidecold.com/settings"):
        client.campaigns.list()


@respx.mock
def test_403_scope_message(client):
    msg = "This API key is missing the campaigns:write scope"
    respx.post(f"{BASE}/campaigns/c1/retry").respond(403, json={"error": msg})
    with pytest.raises(PermissionDeniedError) as exc:
        client.campaigns.retry("c1")
    assert exc.value.message == msg


@respx.mock
def test_get_is_retried_on_5xx_and_429(client):
    route = respx.get(f"{BASE}/campaigns/c1/stats").mock(
        side_effect=[httpx.Response(503), httpx.Response(429), httpx.Response(200, json={"totalSent": 1})]
    )
    assert client.campaigns.stats("c1") == {"totalSent": 1}
    assert route.call_count == 3


@respx.mock
def test_get_gives_up_after_max_retries(client):
    route = respx.get(f"{BASE}/campaigns").respond(500, json={"error": "boom"})
    with pytest.raises(APIError, match="boom"):
        client.campaigns.list()
    assert route.call_count == 3  # 1 + max_retries


@respx.mock
def test_post_is_never_retried(client):
    route = respx.post(f"{BASE}/campaigns").respond(503)
    with pytest.raises(APIError):
        client.campaigns.create(name="x")
    assert route.call_count == 1


@respx.mock
def test_connection_errors_retried_for_get_only(client):
    get = respx.get(f"{BASE}/folders").mock(
        side_effect=[httpx.ConnectError("down"), httpx.Response(200, json=[])]
    )
    assert client.folders.list() == []
    assert get.call_count == 2
    post = respx.post(f"{BASE}/folders").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(APIConnectionError):
        client.folders.create(name="f", type="CAMPAIGN")
    assert post.call_count == 1


@respx.mock
def test_params_body_and_path_encoding(client):
    route = respx.get(f"{BASE}/campaigns").respond(json=[])
    client.campaigns.list(archived=True, folder_id=None)
    assert dict(route.calls.last.request.url.params) == {"archived": "true"}

    patch = respx.patch(f"{BASE}/campaigns/a%2Fb").respond(json={"id": "a/b"})
    client.campaigns.update("a/b", {"name": "n"}, dailyLimit=5)
    assert patch.calls.last.request.read() == b'{"name":"n","dailyLimit":5}'

    route = respx.get(f"{BASE}/accounts/login-status").respond(json={"state": "active"})
    client.accounts.login_status("job1")
    assert route.calls.last.request.url.params["jobId"] == "job1"


@respx.mock
def test_export_returns_csv_text(client):
    respx.get(f"{BASE}/audiences/a1/export").respond(
        text="username\nalice\n", headers={"content-type": "text/csv"}
    )
    assert client.audiences.export("a1") == "username\nalice\n"


@respx.mock
def test_multipart_upload(client, tmp_path):
    photo = tmp_path / "pic.jpg"
    photo.write_bytes(b"\xff\xd8jpeg")
    route = respx.post(f"{BASE}/conversations/c1/photo").respond(202, json={"jobId": "j1"})
    assert client.conversations.send_photo("c1", file=photo) == {"jobId": "j1"}
    req = route.calls.last.request
    assert req.headers["content-type"].startswith("multipart/form-data")
    body = req.read()
    assert b'name="photo"; filename="pic.jpg"' in body and b"\xff\xd8jpeg" in body

    imp = respx.post(f"{BASE}/audiences/a1/import").respond(json={"imported": 1, "skipped": 0, "total": 1})
    client.audiences.import_members("a1", file=("members.csv", b"username\nalice\n"))
    assert b'name="file"; filename="members.csv"' in imp.calls.last.request.read()
    client.audiences.import_members("a1", usernames=["bob"])
    assert imp.calls.last.request.read() == b'{"usernames":["bob"]}'


@respx.mock
def test_wait_for_login_job(client):
    respx.get(f"{BASE}/accounts/login-status").mock(
        side_effect=[
            httpx.Response(200, json={"state": "active"}),
            httpx.Response(200, json={"state": "completed"}),
        ]
    )
    assert client.wait_for_login_job("j1", interval=0)["state"] == "completed"
    respx.get(f"{BASE}/accounts/login-status").respond(json={"state": "waiting"})
    with pytest.raises(TimeoutError):
        client.wait_for_login_job("j1", interval=1, timeout=0)


def test_missing_key_raises():
    with pytest.raises(AuthenticationError, match="slidecold login"):
        SlideCold()


def test_every_operation_has_a_method(client):
    for op in OPERATIONS.values():
        assert callable(getattr(getattr(client, op.resource), op.name)), op.id
    assert len(OPERATIONS) == 49
