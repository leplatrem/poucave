from datetime import timedelta
from unittest import mock

from checks.remotesettings.certificates_expiration import run
from poucave.utils import utcnow
from tests.utils import patch_async


CERT = """-----BEGIN CERTIFICATE-----
MIIDBTCCAougAwIBAgIIFcbkDrCrHAkwCgYIKoZIzj0EAwMwgaMxCzAJBgNVBAYT
AlVTMRwwGgYDVQQKExNNb3ppbGxhIENvcnBvcmF0aW9uMS8wLQYDVQQLEyZNb3pp
bGxhIEFNTyBQcm9kdWN0aW9uIFNpZ25pbmcgU2VydmljZTFFMEMGA1UEAww8Q29u
dGVudCBTaWduaW5nIEludGVybWVkaWF0ZS9lbWFpbEFkZHJlc3M9Zm94c2VjQG1v
emlsbGEuY29tMB4XDTE5MDgyMzIyNDQzMVoXDTE5MTExMTIyNDQzMVowgakxCzAJ
BgNVBAYTAlVTMRMwEQYDVQQIEwpDYWxpZm9ybmlhMRYwFAYDVQQHEw1Nb3VudGFp
biBWaWV3MRwwGgYDVQQKExNNb3ppbGxhIENvcnBvcmF0aW9uMRcwFQYDVQQLEw5D
bG91ZCBTZXJ2aWNlczE2MDQGA1UEAxMtcGlubmluZy1wcmVsb2FkLmNvbnRlbnQt
c2lnbmF0dXJlLm1vemlsbGEub3JnMHYwEAYHKoZIzj0CAQYFK4EEACIDYgAEX6Zd
vZ32rj9rDdRInp0kckbMtAdxOQxJ7EVAEZB2KOLUyotQL6A/9YWrMB4Msb4hfvxj
Nw05CS5/J4qUmsTkKLXQskjRe9x96uOXxprWiVwR4OLYagkJJR7YG1mTXmFzo4GD
MIGAMA4GA1UdDwEB/wQEAwIHgDATBgNVHSUEDDAKBggrBgEFBQcDAzAfBgNVHSME
GDAWgBSgHUoXT4zCKzVF8WPx2nBwp8744TA4BgNVHREEMTAvgi1waW5uaW5nLXBy
ZWxvYWQuY29udGVudC1zaWduYXR1cmUubW96aWxsYS5vcmcwCgYIKoZIzj0EAwMD
aAAwZQIxAOi2Eusi6MtEPOARiU+kZIi1vPnzTI71cA2ZIpzZ9aYg740eoJml8Guz
3oC6yXiIDAIwSy4Eylf+/nSMA73DUclcCjZc2yfRYIogII+krXBxoLkbPJcGaitx
qvRy6gQ1oC/z
-----END CERTIFICATE-----
"""


def mock_http_calls(mock_responses, server_url):
    changes_url = server_url + "/buckets/monitor/collections/changes/records"
    mock_responses.get(
        changes_url,
        payload={
            "data": [
                {"id": "abc", "bucket": "bid", "collection": "cid", "last_modified": 42}
            ]
        },
    )

    metadata_url = server_url + "/buckets/bid/collections/cid"
    mock_responses.get(
        metadata_url, payload={"data": {"signature": {"x5u": "http://fake-x5u"}}}
    )


async def test_positive(mock_responses):
    server_url = "http://fake.local/v1"
    mock_http_calls(mock_responses, server_url)

    next_month = utcnow() + timedelta(days=30)
    fake_cert = mock.MagicMock(not_valid_after=next_month)

    module = "checks.remotesettings.certificates_expiration"
    with patch_async(f"{module}.fetch_cert", return_value=fake_cert) as mocked:
        status, data = await run(server_url, min_remaining_days=29)
        mocked.assert_called_with("http://fake-x5u")

    assert status is True
    assert data == {}


async def test_negative(mock_responses):
    server_url = "http://fake.local/v1"

    mock_http_calls(mock_responses, server_url)

    module = "checks.remotesettings.certificates_expiration"
    with patch_async(f"{module}.fetch_text", return_value=CERT) as mocked:
        status, data = await run(server_url, min_remaining_days=30)
        mocked.assert_called_with("http://fake-x5u")

    assert status is False
    assert data == {
        "bid/cid": {"x5u": "http://fake-x5u", "expires": "2019-11-11T22:44:31+00:00"}
    }
