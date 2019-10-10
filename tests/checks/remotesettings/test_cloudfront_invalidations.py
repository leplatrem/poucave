from checks.remotesettings.cloudfront_invalidations import run

COLLECTION_URL = "/buckets/{}/collections/{}"
RECORDS_URL = COLLECTION_URL + "/records"


async def test_positive(mock_responses):
    server_url = "http://fake.local/v1"
    changes_url = server_url + RECORDS_URL.format("monitor", "changes")
    mock_responses.get(
        changes_url,
        payload={
            "data": [
                {"id": "abc", "bucket": "bid", "collection": "cid", "last_modified": 42}
            ]
        },
    )
    cdn_url = "http://cdn.local/v1"

    collection_url = COLLECTION_URL.format("bid", "cid")
    mock_responses.get(
        server_url + collection_url, payload={"data": {"last_modified": 123}}
    )
    mock_responses.get(
        cdn_url + collection_url, payload={"data": {"last_modified": 123}}
    )

    records_url = RECORDS_URL.format("bid", "cid")
    mock_responses.head(server_url + records_url, headers={"ETag": '"42"'})
    mock_responses.head(cdn_url + records_url, headers={"ETag": '"42"'})

    status, data = await run(server_url, cdn_url)

    assert status is True
    assert data == {}


async def test_negative(mock_responses):
    server_url = "http://fake.local/v1"
    changes_url = server_url + RECORDS_URL.format("monitor", "changes")
    mock_responses.get(
        changes_url,
        payload={
            "data": [
                {"id": "abc", "bucket": "bid", "collection": "cid", "last_modified": 42}
            ]
        },
    )
    cdn_url = "http://cdn.local/v1"

    collection_url = COLLECTION_URL.format("bid", "cid")
    mock_responses.get(
        server_url + collection_url, payload={"data": {"last_modified": 456}}
    )
    mock_responses.get(
        cdn_url + collection_url, payload={"data": {"last_modified": 123}}
    )

    records_url = RECORDS_URL.format("bid", "cid")
    mock_responses.head(server_url + records_url, headers={"ETag": '"40"'})
    mock_responses.head(cdn_url + records_url, headers={"ETag": '"42"'})

    status, data = await run(server_url, cdn_url)

    assert status is False
    assert data == {
        "bid/cid": {
            "cdn": {"collection": 123, "records": "42"},
            "source": {"collection": 456, "records": "40"},
        }
    }
