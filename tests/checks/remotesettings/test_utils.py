from unittest import mock

import pytest

from checks.remotesettings.utils import KintoClient, fetch_signed_resources
from poucave import config


async def test_fetch_signed_resources_no_signer(mock_responses):
    server_url = "http://fake.local/v1"
    mock_responses.get(server_url + "/", payload={"capabilities": {}})

    with pytest.raises(ValueError):
        await fetch_signed_resources(server_url, auth="")


async def test_fetch_signed_resources(mock_responses):
    server_url = "http://fake.local/v1"
    mock_responses.get(
        server_url + "/",
        payload={
            "capabilities": {
                "signer": {
                    "resources": [
                        {
                            "source": {"bucket": "blog-workspace", "collection": None},
                            "preview": {"bucket": "blog-preview", "collection": None},
                            "destination": {"bucket": "blog", "collection": None},
                        },
                        {
                            "source": {
                                "bucket": "security-workspace",
                                "collection": "blocklist",
                            },
                            "destination": {
                                "bucket": "security",
                                "collection": "blocklist",
                            },
                        },
                    ]
                }
            }
        },
    )
    changes_url = server_url + "/buckets/monitor/collections/changes/records"
    mock_responses.get(
        changes_url,
        payload={
            "data": [
                {
                    "id": "abc",
                    "bucket": "blog",
                    "collection": "articles",
                    "last_modified": 42,
                },
                {
                    "id": "def",
                    "bucket": "security",
                    "collection": "blocklist",
                    "last_modified": 41,
                },
                {
                    "id": "ghi",
                    "bucket": "blog-preview",
                    "collection": "articles",
                    "last_modified": 40,
                },
            ]
        },
    )

    resources = await fetch_signed_resources(server_url, auth="")

    assert resources == [
        {
            "last_modified": 42,
            "source": {"bucket": "blog-workspace", "collection": "articles"},
            "preview": {"bucket": "blog-preview", "collection": "articles"},
            "destination": {"bucket": "blog", "collection": "articles"},
        },
        {
            "last_modified": 41,
            "source": {"bucket": "security-workspace", "collection": "blocklist"},
            "destination": {"bucket": "security", "collection": "blocklist"},
        },
    ]


async def test_fetch_signed_resources_unknown_collection(mock_responses):
    server_url = "http://fake.local/v1"
    mock_responses.get(
        server_url + "/", payload={"capabilities": {"signer": {"resources": []}}}
    )
    changes_url = server_url + "/buckets/monitor/collections/changes/records"
    mock_responses.get(
        changes_url,
        payload={
            "data": [
                {
                    "id": "abc",
                    "bucket": "blog",
                    "collection": "articles",
                    "last_modified": 42,
                }
            ]
        },
    )

    with pytest.raises(ValueError):
        await fetch_signed_resources(server_url, auth="")


def test_kinto_auth():
    client = KintoClient(server_url="http://server/v1", auth="Bearer token")

    assert client._client.session.auth.type == "Bearer"
    assert client._client.session.auth.token == "token"


async def test_client_extra_headers(mock_responses):
    server_url = "http://fake.local/v1"
    mock_responses.get(server_url + "/", payload={})

    with mock.patch.dict(config.DEFAULT_REQUEST_HEADERS, {"Extra": "header"}):
        client = KintoClient(server_url=server_url)
        await client.server_info()

    sent_request = mock_responses.calls[0].request
    assert "Extra" in sent_request.headers


async def test_user_agent(mock_responses):
    server_url = "http://fake.local/v1"
    mock_responses.get(server_url + "/", payload={})

    client = KintoClient(server_url=server_url)
    await client.server_info()

    user_agent = mock_responses.calls[0].request.headers["User-Agent"]
    assert "poucave" in user_agent
    assert "kinto_http" in user_agent
