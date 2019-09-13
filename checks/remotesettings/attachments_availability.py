"""
Every attachment in every collection should be avaailable.

The URLs of unreachable attachments is returned along with the number of checked records.
"""
import asyncio
import requests

from poucave.typings import CheckResult

from .utils import KintoClient as Client


def get_records(client, bucket, collection, timestamp):
    return client.get_records(bucket=bucket, collection=collection, _expected=timestamp)


def test_url(url):
    try:
        resp = requests.head(url)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        pass
    return False


async def run(server: str) -> CheckResult:
    loop = asyncio.get_event_loop()

    client = Client(server_url=server, bucket="monitor", collection="changes")

    info = client.server_info()
    base_url = info["capabilities"]["attachments"]["base_url"]

    # Fetch collections records in parallel.
    entries = client.get_records()
    futures = [
        loop.run_in_executor(
            None,
            get_records,
            client,
            entry["bucket"],
            entry["collection"],
            entry["last_modified"],
        )
        for entry in entries
        if "preview" not in entry["bucket"]
    ]
    results = await asyncio.gather(*futures)

    # For each record that has an attachment, send a HEAD request to its url.
    urls = []
    for (entry, records) in zip(entries, results):
        for record in records:
            if "attachment" not in record:
                continue
            url = base_url + record["attachment"]["location"]
            urls.append(url)

    futures = [loop.run_in_executor(None, test_url, url) for url in urls]
    results = await asyncio.gather(*futures)

    # Check if there's any missing.
    missing = [url for success, url in zip(results, urls) if not success]
    return len(missing) == 0, {"missing": missing, "checked": len(results)}
