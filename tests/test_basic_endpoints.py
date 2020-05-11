import re
import tempfile
from unittest import mock

from poucave import config


async def test_hello(cli):
    response = await cli.get("/")
    assert response.status == 200
    body = await response.json()
    assert body["hello"] == "poucave"


async def test_hello_html_redirect(cli):
    response = await cli.get(
        "/",
        headers={"Accept": "text/html,application/xml;q=0.9,image/webp,*/*;q=0.8"},
        allow_redirects=False,
    )
    assert response.status == 302
    assert response.headers["Location"] == "html/index.html"


async def test_lbheartbeat(cli):
    response = await cli.get("/__lbheartbeat__")
    assert response.status == 200


async def test_heartbeat(cli):
    response = await cli.get("/__heartbeat__")
    assert response.status == 200


async def test_version(cli):
    response = await cli.get("/__version__")
    assert response.status == 200
    body = await response.json()
    assert body["name"] == "poucave"

    # Raises if file is missing
    config.VERSION_FILE = "missing.json"
    response = await cli.get("/__version__")
    assert response.status == 500


# /checks


async def test_checks(cli):
    response = await cli.get("/checks")
    assert response.status == 200
    body = await response.json()
    assert len(body) >= 1
    assert body[:1] == [
        {
            "name": "hb",
            "project": "testproject",
            "module": "checks.core.heartbeat",
            "description": "Test HB",
            "documentation": "URL should return a 200 response.\n\nThe remote response is returned.",
            "url": "/checks/testproject/hb",
            "tags": ["ops", "test"],
            "ttl": 60,
            "troubleshooting": (
                "https://mana.mozilla.org/wiki/pages/viewpage.action?pageId=109984139"
                "#TroubleshootingRemoteSettings&Normandy-testproject/hb"
            ),
            "parameters": {"url": "http://server.local/__heartbeat__"},
        }
    ]


# /checks/{project}


async def test_project_unknown(cli):
    response = await cli.get("/checks/unknown")
    assert response.status == 404


async def test_project_unsupported_accept(cli):
    response = await cli.get(
        "/checks/testproject", headers={"Accept": "application/xml"}
    )
    assert response.status == 406


async def test_returns_json_in_browser(mock_aioresponses, cli):
    mock_aioresponses.get("http://server.local/__heartbeat__", status=200, payload={})

    response = await cli.get(
        "/checks/testproject",
        headers={"Accept": "text/html,application/xml;q=0.9,image/webp,*/*;q=0.8"},
    )
    assert response.status == 200
    assert response.headers["Content-Type"] == "application/json; charset=utf-8"


async def test_project_returns_only_cached(mock_aioresponses, cli):
    mock_aioresponses.get("http://server.local/__heartbeat__", status=200, payload={})

    await cli.get("/checks/testproject/fake")

    response = await cli.get("/checks/testproject")
    assert response.status == 200
    body = await response.json()

    assert body[0]["project"] == "testproject"
    assert body[0]["name"] == "hb"
    assert body[0]["success"]

    assert body[1]["name"] == "fake"
    assert body[1]["success"]
    assert body[1]["data"] == {"max_age": 999, "from_conf": 100}


# /tags/{tag}


async def test_check_tag_unknown(cli):
    response = await cli.get("/checks/tags/foo")
    assert response.status == 404


async def test_check_by_tag(cli, mock_aioresponses):
    mock_aioresponses.get(
        "http://server.local/__heartbeat__", status=200, payload={"ok": True}
    )
    response = await cli.get("/checks/tags/ops")
    assert response.status == 200


async def test_check_by_tag_text_mode(cli, mock_aioresponses):
    mock_aioresponses.get(
        "http://server.local/__heartbeat__", status=500, payload={"ok": False}
    )
    response = await cli.get("/checks/tags/ops", headers={"Accept": "text/plain"})
    assert (
        await response.text()
        == """testproject  hb  False


testproject  hb
  Url:
    /checks/testproject/hb
  Description:
    Test HB
  Documentation:
    URL should return a 200 response.

    The remote response is returned.
  Parameters:
    {'url': 'http://server.local/__heartbeat__'}
  Data:
    {
      "ok": false
    }
  Troubleshooting:
    https://mana.mozilla.org/wiki/pages/viewpage.action?pageId=109984139#TroubleshootingRemoteSettings&Normandy-testproject/hb"""
    )


# /checks/{project}/{name}


async def test_check_unknown(cli):
    response = await cli.get("/checks/testproject/unknown")
    assert response.status == 404


async def test_check_run_queryparams(cli):
    response = await cli.get("/checks/testproject/fake")
    body = await response.json()
    assert body["parameters"]["max_age"] == 999
    assert body["data"] == {"max_age": 999, "from_conf": 100}


async def test_check_run_queryparams_overriden(cli):
    response = await cli.get("/checks/testproject/fake?max_age=42")
    body = await response.json()
    assert body["parameters"]["max_age"] == 42
    assert body["data"] == {"max_age": 42, "from_conf": 100}


async def test_check_run_bad_value(cli):
    response = await cli.get("/checks/testproject/fake?max_age=abc")
    assert response.status == 400


async def test_check_positive(cli, mock_aioresponses):
    mock_aioresponses.get(
        "http://server.local/__heartbeat__", status=200, payload={"ok": True}
    )

    response = await cli.get("/checks/testproject/hb")

    assert response.status == 200
    body = await response.json()
    assert re.compile("....-..-..T..:..:..\\.......+..:..").match(body["datetime"])
    assert body["duration"] > 0
    assert body["success"]
    assert body["project"] == "testproject"
    assert body["name"] == "hb"
    assert body["description"] == "Test HB"
    assert "URL should return" in body["documentation"]
    assert body["data"] == {"ok": True}


async def test_check_negative(cli, mock_aioresponses):
    mock_aioresponses.get("http://server.local/__heartbeat__", status=503)

    response = await cli.get("/checks/testproject/hb")

    assert response.status == 503
    body = await response.json()
    assert not body["success"]
    assert body["data"] is None


async def test_check_cached(cli, mock_aioresponses):
    mock_aioresponses.get(
        "http://server.local/__heartbeat__", status=200, payload={"ok": True}
    )

    await cli.get("/checks/testproject/hb")

    mock_aioresponses.clear()

    response = await cli.get("/checks/testproject/hb")

    assert response.status == 200


async def test_check_force_refresh(cli, mock_aioresponses):
    mock_aioresponses.get(
        "http://server.local/__heartbeat__", status=200, payload={"ok": True}
    )

    resp = await cli.get("/checks/testproject/hb")
    dt_before = (await resp.json())["datetime"]

    with mock.patch.object(config, "REFRESH_SECRET", "s3cr3t"):
        resp = await cli.get("/checks/testproject/hb?refresh=wrong")
        assert resp.status == 400

        resp = await cli.get("/checks/testproject/hb?refresh=s3cr3t")
        dt_refreshed = (await resp.json())["datetime"]

    assert dt_before != dt_refreshed


async def test_check_cached_by_queryparam(cli, mock_aioresponses):
    resp = await cli.get("/checks/testproject/fake")
    dt_no_params = (await resp.json())["datetime"]

    resp = await cli.get("/checks/testproject/fake?unknown=1")
    dt_unknown = (await resp.json())["datetime"]
    assert dt_no_params == dt_unknown

    resp = await cli.get("/checks/testproject/fake?max_age=2")
    dt_known = (await resp.json())["datetime"]
    resp = await cli.get("/checks/testproject/fake?max_age=2")
    dt_known_same = (await resp.json())["datetime"]
    assert dt_known == dt_known_same

    resp = await cli.get("/checks/testproject/fake?max_age=3")
    dt_different = (await resp.json())["datetime"]
    assert dt_known != dt_different


async def test_cors_enabled(cli):
    response = await cli.get("/", headers={"Origin": "http://example.org"})

    assert "Access-Control-Allow-Origin" in response.headers


async def test_sentry_event_on_negative(cli, mock_aioresponses):
    mock_aioresponses.get("http://server.local/__heartbeat__", status=503)

    with mock.patch("sentry_sdk.hub.Hub.capture_message") as mocked:
        await cli.get("/checks/testproject/hb")

    assert mocked.call_args_list[0][0][0] == "testproject/hb is failing"


async def test_served_diagram_from_config(cli):
    with tempfile.NamedTemporaryFile("w") as fp:
        with mock.patch.object(config, "DIAGRAM_FILE", fp.name):
            resp = await cli.get("/diagram.svg")
            assert resp.status == 200
            await resp.text()  # Read content.
            assert "svg" in resp.headers["Content-Type"]


async def test_served_diagram_missing(cli):
    with mock.patch.object(config, "DIAGRAM_FILE", "/path/unknown.svg"):
        resp = await cli.get("/diagram.svg")
        assert resp.status == 404
