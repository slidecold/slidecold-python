import json
import os
import stat

import pytest
import respx

from slidecold import _config
from slidecold.cli import build_parser, main

from .conftest import BASE


def run(capsys, *argv):
    code = main(["--base-url", BASE, *argv])
    out, err = capsys.readouterr()
    return code, out, err


def test_parsing():
    args = build_parser().parse_args(
        [
            "audiences",
            "list-members",
            "a1",
            "--min-followers",
            "100",
            "--search",
            "coach",
            "--api-key",
            "cs_x",
        ]
    )
    assert (args.operation, args.id, args.min_followers, args.search, args.api_key) == (
        "listAudienceMembers",
        "a1",
        100,
        "coach",
        "cs_x",
    )
    args = build_parser().parse_args(["conversations", "delete-message", "c1", "m1"])
    assert (args.id, args.message_id) == ("c1", "m1")
    with pytest.raises(SystemExit):
        build_parser().parse_args(["accounts", "login-status"])  # --job-id is required


def test_help_shows_scope(capsys):
    with pytest.raises(SystemExit):
        main(["campaigns", "create", "--help"])
    assert "Scope: campaigns:write" in capsys.readouterr().out


@respx.mock
def test_end_to_end_json_and_data_file(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("SLIDECOLD_API_KEY", "cs_env")
    route = respx.post(f"{BASE}/campaigns").respond(201, json={"id": "c1", "name": "Spring"})
    body = tmp_path / "body.json"
    body.write_text('{"name": "Spring"}')
    code, out, _ = run(capsys, "campaigns", "create", "--data", f"@{body}")
    assert code == 0 and json.loads(out) == {"id": "c1", "name": "Spring"}
    assert route.calls.last.request.read() == b'{"name":"Spring"}'
    assert route.calls.last.request.headers["authorization"] == "Bearer cs_env"


@respx.mock
def test_end_to_end_csv_and_errors(capsys):
    respx.get(f"{BASE}/audiences/a1/export").respond(
        text="username\nalice", headers={"content-type": "text/csv"}
    )
    code, out, _ = run(capsys, "--api-key", "cs_x", "audiences", "export", "a1")
    assert (code, out) == (0, "username\nalice\n")

    respx.get(f"{BASE}/campaigns").respond(
        403, json={"error": "This API key is missing the campaigns:read scope"}
    )
    code, out, err = run(capsys, "campaigns", "list", "--api-key", "cs_x")
    assert code == 1 and out == "" and "missing the campaigns:read scope" in err

    code, _, err = run(capsys, "campaigns", "create", "--api-key", "cs_x", "--data", "{bad")
    assert code == 1 and "not valid JSON" in err


def test_missing_key(capsys):
    code, _, err = run(capsys, "campaigns", "list")
    assert code == 1 and "slidecold login" in err


@respx.mock
def test_login_and_logout(capsys):
    respx.get(f"{BASE}/campaigns").respond(401, json={"error": "Invalid API key"})
    code, _, err = run(capsys, "login", "--key", "cs_bad")
    assert code == 1 and "invalid API key" in err
    assert not _config.config_path().exists()

    respx.get(f"{BASE}/campaigns").respond(403, json={"error": "missing scope"})
    code, out, _ = run(capsys, "login", "--key", "cs_scoped")
    assert code == 0 and "lacks campaigns:read" in out
    path = _config.config_path()
    assert json.loads(path.read_text()) == {"apiKey": "cs_scoped", "baseUrl": BASE}
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    code, _, _ = run(capsys, "logout")
    assert code == 0 and json.loads(path.read_text()) == {"baseUrl": BASE}
