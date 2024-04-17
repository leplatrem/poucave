"""
Every attachment in every collection has the right size and hash.

The URLs of invalid attachments is returned along with the number of checked records.
"""

import hashlib

import aiohttp

from telescope.typings import CheckResult
from telescope.utils import ClientSession, run_parallel

from .utils import KintoClient


async def test_attachment(session, attachment):
    url = attachment["location"]
    try:
        async with session.get(url) as response:
            binary = await response.read()
    except aiohttp.client_exceptions.ClientError as exc:
        return {"url": url, "error": str(exc)}, False

    if (bz := len(binary)) != (az := attachment["size"]):
        return {"url": url, "error": f"size differ ({bz}!={az})"}, False

    h = hashlib.sha256(binary)
    if (bh := h.hexdigest()) != (ah := attachment["hash"]):
        return {"url": url, "error": f"hash differ ({bh}!={ah})"}, False

    return {}, True


async def run(server: str) -> CheckResult:
    client = KintoClient(server_url=server)

    info = await client.server_info()
    base_url = info["capabilities"]["attachments"]["base_url"]

    # Fetch collections records in parallel.
    entries = await client.get_monitor_changes()
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

    # For each record that has an attachment, check the attachment content.
    attachments = []
    for entry, records in zip(entries, results):
        for record in records:
            if "attachment" not in record:
                continue
            attachment = record["attachment"]
            attachment["location"] = base_url + attachment["location"]
            attachments.append(attachment)

    async with ClientSession() as session:
        futures = [test_attachment(session, attachment) for attachment in attachments]
        results = await run_parallel(*futures)
    bad = [result for result, success in results if not success]
    return len(bad) == 0, {"bad": bad, "checked": len(attachments)}
