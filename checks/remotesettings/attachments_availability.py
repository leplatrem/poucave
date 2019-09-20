"""
Every attachment in every collection should be avaailable.

The URLs of unreachable attachments is returned along with the number of checked records.
"""
import aiohttp

from poucave.typings import CheckResult
from poucave.utils import fetch_head, run_parallel

from .utils import KintoClient


async def test_url(url):
    try:
        status, _ = await fetch_head(url)
        return status == 200
    except aiohttp.client_exceptions.ClientError:
        return False


async def run(server: str) -> CheckResult:
    client = KintoClient(server_url=server, bucket="monitor", collection="changes")

    info = await client.server_info()
    base_url = info["capabilities"]["attachments"]["base_url"]

    # Fetch collections records in parallel.
    entries = await client.get_records()
    futures = [
        client.get_records(
            bucket=entry["bucket"],
            collection=entry["collection"],
            _expected=entry["last_modified"],
        )
        for entry in entries
        if "preview" not in entry["bucket"]
    ]
    results = await run_parallel(*futures)

    # For each record that has an attachment, send a HEAD request to its url.
    urls = []
    for (entry, records) in zip(entries, results):
        for record in records:
            if "attachment" not in record:
                continue
            url = base_url + record["attachment"]["location"]
            urls.append(url)
    futures = [test_url(url) for url in urls]
    results = await run_parallel(*futures)
    missing = [url for url, success in zip(urls, results) if not success]

    return len(missing) == 0, {"missing": missing, "checked": len(urls)}
